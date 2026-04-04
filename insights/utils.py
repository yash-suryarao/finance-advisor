"""
INSIGHTS MODULE - UTILITIES (insights/utils.py)
-----------------------------------------------
This file contains all the heavy-lifting logic for the insights app.
It houses the Machine Learning models, API integrations (Gemini), and Pandas data transformations.

Main Features:
- Isolation Forest (Anomaly Detection)
- Prophet (Time-Series Forecasting)
- XGBoost (Budget Reallocation heuristic simulation)
- Gemini 2.0 (LLM Analysis & Subscriptions extraction)
"""

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


# ==========================================
# 1. DATA PROCESSING HELPER
# ==========================================

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


# ==========================================
# 2. MACHINE LEARNING MODELS
# ==========================================

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
    
    — Feedback Loop Integration:
    Loads ai_training_feedback.csv (if it exists) and uses past outcome labels
    as multipliers for the risk score, making recommendations progressively
    smarter as more AIInsightsLog evaluations accumulate.
    """
    df = get_user_transactions_df(user)
    suggestions = []

    if df.empty or xgb is None:
        return suggestions

    # ── Load feedback CSV for outcome-based risk weighting ────────────────────
    feedback_weights = {}   # {category: weight_multiplier}
    try:
        import os
        feedback_path = os.path.join(settings.BASE_DIR, 'media', 'datasets', 'ai_training_feedback.csv')
        if os.path.exists(feedback_path):
            fb_df = pd.read_csv(feedback_path)
            # Filter to this user only
            fb_df = fb_df[fb_df['user_id'].astype(str) == str(user.id)]
            if not fb_df.empty:
                for cat, group in fb_df.groupby('category'):
                    outcomes = group['outcome_label'].value_counts()
                    worsened = outcomes.get('worsened', 0)
                    improved = outcomes.get('improved', 0)
                    total    = len(group)
                    # Higher worsened ratio → push harder (up to 1.5× cut)
                    # Higher improved ratio → ease off (down to 0.75× cut)
                    worsened_ratio = worsened / total if total > 0 else 0
                    improved_ratio = improved / total if total > 0 else 0
                    feedback_weights[cat] = 1.0 + (worsened_ratio * 0.5) - (improved_ratio * 0.25)
    except Exception as e:
        logger.warning(f"[Feedback Loop] Could not load training CSV: {e}")

    category_summary = df.groupby("category")["amount"].sum().reset_index()

    try:
        dtrain = xgb.DMatrix(category_summary[['amount']])
        category_summary['risk_score'] = category_summary['amount'] / category_summary['amount'].sum()

        for _, row in category_summary.iterrows():
            cat = row['category']
            base_cut_rate = 0.15   # default 15% cut suggestion

            # Apply outcome-based multiplier from feedback CSV
            multiplier = feedback_weights.get(cat, 1.0)
            adjusted_cut_rate = min(base_cut_rate * multiplier, 0.30)  # cap at 30%

            if row['risk_score'] > 0.3:
                optimal_cut = row['amount'] * adjusted_cut_rate
                reason_suffix = ""
                if multiplier > 1.1:
                    reason_suffix = " Past AI advice was not followed — a stronger reduction is now recommended."
                elif multiplier < 0.9:
                    reason_suffix = " Your spending improved after last month's advice — keep it up!"
                suggestions.append({
                    "type": "Budget",
                    "title": f"Smart Budget Recommendation: {cat}",
                    "description": (
                        f"You allocate a high volume ({row['risk_score']*100:.1f}%) of spending to {cat}. "
                        f"AI suggests reducing it by ₹{optimal_cut:.2f} this month.{reason_suffix}"
                    ),
                    "category": cat,
                    "data_point": float(optimal_cut),
                    "feedback_multiplier": round(multiplier, 2),
                })
    except Exception as e:
        logger.error(f"XGBoost scoring failed: {e}")

    return suggestions


# ==========================================
# 3. LLM GENERATION & FALLBACKS
# ==========================================

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


def generate_monthly_xai_report(user_data_summary, user=None):
    """
    Calls Gemini to generate the Explainable AI (XAI) Monthly Report.
    Returns a structured dict with what_happened, why_it_matters, and actionable recommendations.
    Now uses AIInsightsLog to:
    - Cache the result for 24 hours (avoids duplicate API calls)
    - Inject prior advice into the prompt so the AI measures user improvement over time
    """
    from insights.models import AIInsightsLog
    from django.utils import timezone
    from datetime import timedelta

    feature_name = 'Monthly XAI Review'

    # ── 1. Cache Check: return stored insight if < 24 hours old ──────────────
    if user:
        recent = AIInsightsLog.objects.filter(
            user=user,
            feature_name=feature_name,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).first()
        if recent:
            try:
                return json.loads(recent.generated_insight)
            except Exception:
                pass  # fall through to regenerate

    # ── 2. Load prior advice for Memory Injection ─────────────────────────────
    prior_advice_text = ''
    if user:
        prior = AIInsightsLog.objects.filter(
            user=user, feature_name=feature_name
        ).order_by('-created_at').first()
        if prior:
            try:
                prior_data = json.loads(prior.generated_insight)
                prior_advice_text = f"""
    IMPORTANT — MEMORY CONTEXT: You previously advised this user. Here is what you told them:
    What Happened (prior): {prior_data.get('what_happened', '')}
    Your Prior Recommendations: {json.dumps(prior_data.get('recommendations', []))}

    Now compare their data then vs now and evaluate whether they followed your advice.
    If they improved, acknowledge it. If they didn't, address it directly and firmly but constructively.
    """
            except Exception:
                pass

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key or not genai:
        return {
            "what_happened": "AI service is currently unavailable. You spent ₹" + str(user_data_summary.get('current_month_spending', 0)) + " this month.",
            "why_it_matters": "Tracking your expenses helps you maintain a healthy Spending Ratio.",
            "recommendations": []
        }

    genai.configure(api_key=api_key)
    prompt = f"""
    You are an expert financial advisor AI. The user has requested a monthly review. Here is their data:
    {prior_advice_text}
    Current Month Income: ₹{user_data_summary.get('current_month_income', 0)}
    Current Month Expense: ₹{user_data_summary.get('current_month_spending', 0)}
    Previous Month Income: ₹{user_data_summary.get('previous_month_income', 0)}
    Previous Month Expense: ₹{user_data_summary.get('previous_month_spending', 0)}
    Financial Health Score (0-100): {user_data_summary.get('health_score', 0)}
    Top 3 Expense Categories: {user_data_summary.get('top_categories', [])}
    
    Instructions:
    Return your response strictly as a JSON object with the following schema:
    {{
      "what_happened": "A 2-3 sentence summary. If you have prior context, reference whether the user improved since last time. Otherwise give a fresh read.",
      "why_it_matters": "A 2-3 sentence explanation of how their spending impacted their Financial Health score.",
      "recommendations": [
        {{
          "type": "budget" or "goal",
          "category": "The exact category name (e.g., 'Food') or name of the goal",
          "amount": integer amount suggested,
          "reason": "Why this action will help them recover or improve."
        }}
      ]
    }}
    Provide exactly 2 highly relevant recommendations. Ensure the JSON is valid. Do not wrap in markdown tags like ```json.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.2))
        
        # Clean string just in case gemini still wraps it in markdown block
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        result = json.loads(raw_text)

        # ── 3. Persist to AIInsightsLog ─────────────────────────────────────────
        if user:
            AIInsightsLog.objects.create(
                user=user,
                feature_name=feature_name,
                context_snapshot=user_data_summary,
                generated_insight=json.dumps(result)
            )

        return result
    except Exception as e:
        logger.error(f"XAI Monthly Report generation failed: {e}")
        return {
            "what_happened": "We experienced an error generating your full AI report.",
            "why_it_matters": "Detailed analysis is currently unavailable.",
            "recommendations": []
        }


def extract_subscriptions(user):
    """
    Calls Gemini to analyze the last 90 days of transactions and figure out subscriptions.
    """
    df = get_user_transactions_df(user)
    if df.empty:
        return []

    # Get last 90 days
    ninety_days_ago = pd.Timestamp.now() - pd.Timedelta(days=90)
    recent_txs = df[df['date'] >= ninety_days_ago]
    
    if recent_txs.empty:
        return []

    # Extract relevant fields to save token space
    tx_list = recent_txs[['date', 'description', 'amount', 'category']].to_dict(orient='records')
    # Filter out empty descriptions
    tx_list = [tx for tx in tx_list if type(tx['description']) == str and str(tx['description']).strip()]
    
    if len(tx_list) < 3: # Not enough data
        return []
        
    # sample to avoid massive token load
    if len(tx_list) > 100:
        tx_list = random.sample(tx_list, 100)
        
    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key or not genai:
        return []

    genai.configure(api_key=api_key)
    prompt = f"""
    Analyze these recent bank transactions and identify likely "Subscriptions" or "Recurring Charges" (e.g. Netflix, Gym, Rent, ongoing software).
    
    Transactions Data:
    {json.dumps(tx_list, default=str)}
    
    Instructions:
    Return a strict JSON array of objects representing identified recurring charges. If none are found, return empty array [].
    Schema:
    [
      {{
        "service_name": "Name of service (e.g. Netflix)",
        "estimated_monthly_cost": integer amount
      }}
    ]
    Do not wrap the JSON in markdown formatting perfectly valid JSON array.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
            
        return json.loads(raw_text)
    except Exception as e:
        logger.error(f"Subscription extraction failed: {e}")
        return []


def generate_category_llm_insight(category_data, user=None):
    """
    Attempts to generate a Gemini AI insight. Falls back to rule-based summary
    immediately if rate-limited (no long waits).

    Now uses AIInsightsLog to:
    - Cache the result for 24 hours per category (avoids repeated API hits)
    - Inject prior advice into the next prompt for accountability-driven self-improvement
    """
    from insights.models import AIInsightsLog
    from django.utils import timezone
    from datetime import timedelta

    cat = category_data['category']
    feature_name = f'Category Insight: {cat}'

    # ── 1. Cache Check: return stored insight if < 24 hours old ──────────────
    if user:
        recent = AIInsightsLog.objects.filter(
            user=user,
            feature_name=feature_name,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).first()
        if recent:
            return recent.generated_insight

    # ── 2. Load prior advice for Memory Injection ─────────────────────────────
    prior_advice_text = ''
    if user:
        prior = AIInsightsLog.objects.filter(
            user=user, feature_name=feature_name
        ).order_by('-created_at').first()
        if prior:
            prior_advice_text = f"""
**MEMORY CONTEXT — What you previously told this user about '{cat}':**
{prior.generated_insight[:500]}...

Now compare: did this user's spending improve since then? If yes, celebrate it.
If no, reference the prior advice and push harder with a more direct recommendation this time.
"""

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    try:
        import google.generativeai as genai
        genai_loaded = True
    except Exception:
        genai_loaded = False

    if not genai_loaded or not api_key:
        result = generate_rule_based_insight(category_data)
        if user:
            AIInsightsLog.objects.create(
                user=user, feature_name=feature_name,
                context_snapshot=category_data, generated_insight=result
            )
        return result
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
You are a helpful financial AI assistant. Analyze the specific spending data for the user's '{cat}' category:

{prior_advice_text}
- Current Month Spend: \u20b9{category_data['current_month_spending']:.2f}
- Previous Month Spend: \u20b9{category_data['previous_month_spending']:.2f}
- Month-Over-Month Change: {category_data['percentage_change']}%
- Anomaly Detected: {'Yes (' + category_data['anomaly_details'] + ')' if category_data['anomaly_flag'] else 'No'}
- Forecasted Next 30 Days Spend: \u20b9{category_data['forecasted_next_month_spending']:.2f}
- Suggested Budget Reduction: \u20b9{category_data['recommended_budget_limit']:.2f}

Provide a focused, actionable 2-paragraph summary.
1. Explain what these trends mean practically. Reference prior advice if available.
2. Provide concrete recommendations to optimize spending in '{cat}'. Keep it concise and encouraging.

Format with Markdown bolding. Do not use raw JSON.
"""
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.7)
        )
        result = response.text

        # ── 3. Persist to AIInsightsLog ─────────────────────────────────────────
        if user:
            AIInsightsLog.objects.create(
                user=user,
                feature_name=feature_name,
                context_snapshot=category_data,
                generated_insight=result
            )

        return result
    except Exception as e:
        err_str = str(e)
        # Fail-fast on rate limits — use rule-based fallback immediately
        if 'ResourceExhausted' in type(e).__name__ or '429' in err_str:
            print(f"[GEMINI] Rate limited for '{cat}'. Using rule-based fallback.")
            result = generate_rule_based_insight(category_data)
        else:
            logger.error(f"Gemini error for '{cat}': {type(e).__name__}: {e}")
            result = generate_rule_based_insight(category_data)

        # Still save the fallback so we have a memory reference
        if user:
            AIInsightsLog.objects.create(
                user=user, feature_name=feature_name,
                context_snapshot=category_data, generated_insight=result
            )
        return result


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
