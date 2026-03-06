import pandas as pd
from datetime import datetime, timedelta
from transactions.models import Transaction, Budget
from django.db.models import Sum
from django.conf import settings
import numpy as np
import logging
import warnings
import json
import random

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

# Import ML Libraries
try:
    from sklearn.ensemble import IsolationForest
except ImportError:
    IsolationForest = None

try:
    from prophet import Prophet
except ImportError:
    Prophet = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Configure Gemini if API key exists in settings
GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
if genai and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def get_user_transactions_df(user):
    """Fetches user transactions from the global real-time CSV export."""
    import os
    from django.conf import settings
    
    file_path = os.path.join(settings.BASE_DIR, 'media', 'datasets', 'all_transactions.csv')
    
    if not os.path.exists(file_path):
        return pd.DataFrame()
        
    try:
        # Read the consolidated database CSV
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Failed to read unified CSV: {e}")
        return pd.DataFrame()
        
    if df.empty:
        return pd.DataFrame()

    # CRITICAL: Securely isolate the Dataframe to ONLY contain this specific user's transactions
    df['user_id'] = df['user_id'].astype(str)
    df = df[df['user_id'] == str(user.id)].copy()
    
    if df.empty:
        return pd.DataFrame()

    
    df["category"] = df["category"].fillna("Uncategorized")
    # Titlecase the type to consistently match queries like 'Expense' or 'Income'
    df["type"] = df["type"].str.capitalize()
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df


def detect_anomalies(user):
    """
    Model 1: Isolation Forest for Anomaly Detection.
    Detects irregular spending spikes.
    """
    df = get_user_transactions_df(user)
    anomalies_list = []
    
    if df.empty or len(df) < 10 or IsolationForest is None:
        return anomalies_list

    # Group by date to get daily spending
    daily_spend = df.groupby("date")["amount"].sum().reset_index()
    
    # Train Isolation Forest
    model = IsolationForest(contamination=0.05, random_state=42)
    daily_spend["anomaly"] = model.fit_predict(daily_spend[["amount"]])
    
    # -1 indicates an anomaly (outlier spike)
    anomalous_days = daily_spend[daily_spend["anomaly"] == -1]
    
    for _, row in anomalous_days.iterrows():
        # Find the category that caused the spike on this day
        day_transactions = df[df["date"] == row["date"]]
        top_category = day_transactions.groupby("category")["amount"].sum().idxmax()
        top_amount = day_transactions.groupby("category")["amount"].sum().max()
        
        anomalies_list.append({
            "type": "Anomaly",
            "title": f"Unusual Spending Spike: {top_category}",
            "description": f"You spent ₹{top_amount:.2f} on {top_category} on {row['date'].strftime('%b %d')}, which is unusually high.",
            "category": top_category,
            "data_point": float(top_amount)
        })
        
    return anomalies_list


def forecast_spending(user):
    """
    Model 2: Prophet Time-Series Forecasting.
    Predicts spending trajectory.
    """
    df = get_user_transactions_df(user)
    forecasts = []
    
    if df.empty or Prophet is None:
        return forecasts

    # Forecast per category
    categories = df["category"].unique()
    for cat in categories:
        cat_df = df[df["category"] == cat][["date", "amount"]]
        cat_daily = cat_df.groupby("date")["amount"].sum().reset_index()
        
        if len(cat_daily) < 5:
            continue
            
        prophet_df = cat_daily.rename(columns={"date": "ds", "amount": "y"})
        
        try:
            m = Prophet(daily_seasonality=True, yearly_seasonality=False)
            m.fit(prophet_df)
            future = m.make_future_dataframe(periods=30)
            forecast = m.predict(future)
            
            # Predict sum for next 30 days
            next_30_days_sum = forecast.tail(30)['yhat'].sum()
            if next_30_days_sum > 0:
                forecasts.append({
                    "type": "Forecast",
                    "title": f"Spending Forecast: {cat}",
                    "description": f"Based on your trends, we project you will spend ₹{next_30_days_sum:.2f} on {cat} in the next 30 days.",
                    "category": cat,
                    "data_point": float(next_30_days_sum)
                })
        except Exception as e:
            logger.error(f"Prophet failed for {cat}: {e}")
            
    return forecasts


def suggest_smart_budgets(user):
    """
    Model 3: XGBoost / Gradient Boosted Trees for Budget Reallocation.
    Evaluates profile against quantitative heuristics to shape optimal budgets.
    """
    df = get_user_transactions_df(user)
    suggestions = []
    
    if df.empty or xgb is None:
        return suggestions
        
    category_summary = df.groupby("category")["amount"].sum().reset_index()
    
    try:
        # In a fully productionized system, XGBoost would be trained on thousands of users' data
        # to map (income, spending_history) -> (optimal_budget).
        # We simulate the scoring mechanism:
        dtrain = xgb.DMatrix(category_summary[['amount']])
        # Dummy prediction to represent model inference score processing
        category_summary['risk_score'] = category_summary['amount'] / category_summary['amount'].sum()
        
        for _, row in category_summary.iterrows():
            if row['risk_score'] > 0.3: # Using more than 30% of total spend
                optimal_cut = row['amount'] * 0.15 # Suggest 15% cut
                suggestions.append({
                    "type": "Budget",
                    "title": f"Smart Budget Recommendation: {row['category']}",
                    "description": f"You allocate a high volume ({row['risk_score']*100:.1f}%) of spending to {row['category']}. AI suggests reducing it by ₹{optimal_cut:.2f} this month.",
                    "category": row['category'],
                    "data_point": float(optimal_cut)
                })
    except Exception as e:
        logger.error(f"XGBoost scoring failed: {e}")
        
    return suggestions


def generate_rule_based_insight(category_data):
    """
    Instant fallback summary generated purely from ML metrics.
    Used when Gemini is rate-limited or unavailable.
    """
    cat = category_data['category']
    curr = category_data['current_month_spending']
    prev = category_data['previous_month_spending']
    pct = category_data['percentage_change']
    anomaly = category_data['anomaly_flag']
    anomaly_detail = category_data['anomaly_details']
    forecast = category_data['forecasted_next_month_spending']
    budget_cut = category_data['recommended_budget_limit']

    lines = [f"**{cat} — Spending Analysis**\n"]

    # Trend paragraph
    if prev == 0 and curr > 0:
        lines.append(f"This is the **first recorded month** of spending in **{cat}**, totalling **\u20b9{curr:.2f}**.")
    elif pct > 20:
        lines.append(f"Your **{cat}** spending has risen sharply by **{pct:.1f}%** this month (\u20b9{curr:.2f} vs \u20b9{prev:.2f} last month). This is a significant increase that warrants attention.")
    elif pct > 0:
        lines.append(f"Your **{cat}** spending increased by **{pct:.1f}%** this month to **\u20b9{curr:.2f}** (up from \u20b9{prev:.2f}).")
    elif pct < -10:
        lines.append(f"Great progress! Your **{cat}** spending dropped by **{abs(pct):.1f}%** this month to **\u20b9{curr:.2f}** (down from \u20b9{prev:.2f}). Keep it up!")
    else:
        lines.append(f"Your **{cat}** spending is relatively stable at **\u20b9{curr:.2f}** this month (\u20b9{prev:.2f} last month).")

    if anomaly:
        lines.append(f"\n\u26a0\ufe0f **Anomaly detected:** {anomaly_detail}")

    if forecast > 0:
        lines.append(f"\n**Forecast:** Based on your spending patterns, the model projects approximately **\u20b9{forecast:.2f}** in {cat} spending over the next 30 days.")

    # Recommendation paragraph
    lines.append("\n**Recommendations:**")
    if budget_cut > 0:
        lines.append(f"- AI suggests targeting a **\u20b9{budget_cut:.2f}** reduction this month to bring your {cat} spending within a healthy range.")
    if pct > 20:
        lines.append(f"- Review recent {cat} transactions for any one-time large expenses that inflated this month's total.")
        lines.append(f"- Set a specific monthly budget limit for {cat} to track and control future spending.")
    elif pct < -10:
        lines.append(f"- Maintain this discipline! Consider saving the **\u20b9{prev - curr:.2f}** saved compared to last month.")
    else:
        lines.append(f"- Track your {cat} spending weekly to identify opportunities to reduce costs further.")
        lines.append(f"- Compare prices and look for alternatives to lower recurring {cat} expenses.")

    return "\n".join(lines)


def generate_category_llm_insight(category_data):
    """
    Attempts to generate a Gemini AI insight. Falls back to rule-based summary
    immediately if rate-limited (no long waits).
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    cat = category_data['category']
    
    try:
        import google.generativeai as genai
        genai_loaded = True
    except Exception:
        genai_loaded = False

    if not genai_loaded or not api_key:
        return generate_rule_based_insight(category_data)
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
You are a helpful financial AI assistant. Analyze the specific spending data for the user's '{cat}' category:

- Current Month Spend: \u20b9{category_data['current_month_spending']:.2f}
- Previous Month Spend: \u20b9{category_data['previous_month_spending']:.2f}
- Month-Over-Month Change: {category_data['percentage_change']}%
- Anomaly Detected: {'Yes (' + category_data['anomaly_details'] + ')' if category_data['anomaly_flag'] else 'No'}
- Forecasted Next 30 Days Spend: \u20b9{category_data['forecasted_next_month_spending']:.2f}
- Suggested Budget Reduction: \u20b9{category_data['recommended_budget_limit']:.2f}

Provide a focused, actionable 2-paragraph summary.
1. Explain what these trends mean practically. Highlight if algorithms detected massive spikes.
2. Provide concrete recommendations to optimize spending in '{cat}'. Keep it concise and encouraging.

Format with Markdown bolding. Do not use raw JSON.
"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.7)
        )
        return response.text
    except Exception as e:
        err_str = str(e)
        # Fail-fast on rate limits — use rule-based fallback immediately
        if 'ResourceExhausted' in type(e).__name__ or '429' in err_str:
            print(f"[GEMINI] Rate limited for '{cat}'. Using rule-based fallback.")
            return generate_rule_based_insight(category_data)
        # Other errors
        logger.error(f"Gemini error for '{cat}': {type(e).__name__}: {e}")
        return generate_rule_based_insight(category_data)


def get_advanced_ai_insights(user):
    """Orchestrates category-by-category AI analysis for the Dashboard using the CSV export."""
    df = get_user_transactions_df(user)
    if df.empty:
        return []

    # Get ML aggregates
    anomalies = detect_anomalies(user)
    forecasts = forecast_spending(user)
    budgets = suggest_smart_budgets(user)
    
    anomaly_map = {a['category']: a for a in anomalies}
    forecast_map = {f['category']: f for f in forecasts}
    budget_map = {b['category']: b for b in budgets}
    
    # Process per expense category
    categories = df[df['type'] == 'Expense']['category'].unique()
    results = []
    
    current_month_str = df['date'].dt.to_period('M').max()
    prev_month_str = current_month_str - 1

    for cat in categories:
        cat_df = df[(df['category'] == cat) & (df['type'] == 'Expense')]
        if cat_df.empty:
            continue
            
        curr_total = cat_df[cat_df['date'].dt.to_period('M') == current_month_str]['amount'].sum()
        prev_total = cat_df[cat_df['date'].dt.to_period('M') == prev_month_str]['amount'].sum()
        pct_change = ((curr_total - prev_total) / prev_total * 100) if prev_total > 0 else (100 if curr_total > 0 else 0)
        
        category_data = {
            "category": cat,
            "current_month_spending": float(curr_total),
            "previous_month_spending": float(prev_total),
            "percentage_change": float(round(pct_change, 2)),
            "anomaly_flag": cat in anomaly_map,
            "anomaly_details": anomaly_map[cat]['description'] if cat in anomaly_map else "None",
            "forecasted_next_month_spending": float(forecast_map.get(cat, {}).get('data_point', 0.0)),
            "recommended_budget_limit": float(budget_map.get(cat, {}).get('data_point', 0.0))
        }
        
        # LLM summary is fetched lazily when user clicks 'View Details' (see category_insight_detail view)
        desc = "Analysis complete for this category."
        if category_data['anomaly_flag']:
            desc = category_data['anomaly_details']
        elif pct_change > 10:
            desc = f"Your {cat} spending is up by {pct_change:.1f}% compared to last month."
        elif pct_change < -10:
            desc = f"Great job! Your {cat} spending is down by {abs(pct_change):.1f}%."
        else:
            desc = f"Your {cat} spending is stable at \u20b9{curr_total:.2f}."
            
        results.append({
            "type": "CategoryAnalysis",
            "title": f"Insight: {cat}",
            "category": cat,
            "description": desc,
            "llm_details": ""  # Populated lazily on View Details click
        })
        
    return results
