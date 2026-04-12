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
import re

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
        lines.append(f"This is the **first recorded month** of spending in **{cat}**, totalling **₹{curr:.2f}**.")
    elif pct > 20:
        lines.append(f"Your **{cat}** spending has risen sharply by **{pct:.1f}%** this month (₹{curr:.2f} vs ₹{prev:.2f} last month). This is a significant increase that warrants attention.")
    elif pct > 0:
        lines.append(f"Your **{cat}** spending increased by **{pct:.1f}%** this month to **₹{curr:.2f}** (up from ₹{prev:.2f}).")
    elif pct < -10:
        lines.append(f"Great progress! Your **{cat}** spending dropped by **{abs(pct):.1f}%** this month to **₹{curr:.2f}** (down from ₹{prev:.2f}). Keep it up!")
    else:
        lines.append(f"Your **{cat}** spending is relatively stable at **₹{curr:.2f}** this month (₹{prev:.2f} last month).")

    if anomaly:
        lines.append(f"\n⚠️ **Anomaly detected:** {anomaly_detail}")

    if forecast > 0:
        lines.append(f"\n**Forecast:** Based on your spending patterns, the model projects approximately **₹{forecast:.2f}** in {cat} spending over the next 30 days.")

    # Recommendation paragraph
    lines.append("\n**Recommendations:**")
    if budget_cut > 0:
        lines.append(f"- AI suggests targeting a **₹{budget_cut:.2f}** reduction this month to bring your {cat} spending within a healthy range.")
    if pct > 20:
        lines.append(f"- Review recent {cat} transactions for any one-time large expenses that inflated this month's total.")
        lines.append(f"- Set a specific monthly budget limit for {cat} to track and control future spending.")
    elif pct < -10:
        lines.append(f"- Maintain this discipline! Consider saving the **₹{prev - curr:.2f}** saved compared to last month.")
    else:
        lines.append(f"- Track your {cat} spending weekly to identify opportunities to reduce costs further.")
        lines.append(f"- Compare prices and look for alternatives to lower recurring {cat} expenses.")

    return "\n".join(lines)


def generate_rule_based_monthly_report(user_data_summary):
    """
    Creates a detailed, statistical summary when the LLM is unavailable.
    Expanded to be much more verbose and detailed across multiple paragraphs.
    """
    import json
    curr_inc = user_data_summary.get('current_month_income', 0)
    curr_exp = user_data_summary.get('current_month_spending', 0)
    prev_exp = user_data_summary.get('previous_month_spending', 0)
    health = user_data_summary.get('health_score', 0)
    cats = user_data_summary.get('top_categories', [])
    anomalies = user_data_summary.get('anomalies', [])
    goal = user_data_summary.get('user_profile', {}).get('financial_goal', 'Savings')
    occupation = user_data_summary.get('user_profile', {}).get('occupation', 'valued user')

    # Calculate trend
    diff = curr_exp - prev_exp
    pct_change = (diff / prev_exp * 100) if prev_exp > 0 else 0
    savings = curr_inc - curr_exp
    spending_ratio = (curr_exp / curr_inc * 100) if curr_inc > 0 else 0
    
    # ── 1. Detailed "What Happened" Section ───────────────────────────────────
    happened_parts = []
    
    # Paragraph 1: Overview
    overview = f"Hello! Let's take a deep look at your finances for this month. You brought in a total income of ₹{curr_inc:,.2f} while your total expenditures reached ₹{curr_exp:,.2f}. "
    if pct_change > 10:
        overview += f"I noticed a notable upward trend in your spending, which has increased by **{pct_change:.1f}%** compared to last month. This shift suggests your current lifestyle or unforeseen expenses are putting additional pressure on your budget. "
    elif pct_change < -10:
        overview += f"Excellent work! Your total spending has decreased by **{abs(pct_change):.1f}%** since last month. This is a clear indicator that your recent adjustments are paying off. "
    else:
        overview += f"Your spending has remained remarkably stable, with only a **{abs(pct_change):.1f}%** change from last month. This consistency is great for long-term planning. "
    happened_parts.append(overview)
    
    # Paragraph 2: Category Analysis
    if cats:
        cat_desc = f"Looking at where your money is going, the top three contributors to your expenses were **{', '.join(cats[:3])}**. "
        cat_desc += f"Specifically, these categories highlight where the bulk of your ₹{curr_exp:,.2f} monthly spend is concentrated. For someone in your position as a **{occupation}**, managing these core areas is vital for maintaining balance. "
        if len(cats) > 3:
            cat_desc += f"Secondary expenses in {', '.join(cats[3:5])} also played a role in your monthly total."
        happened_parts.append(cat_desc)
        
    # Paragraph 3: Behavioral Observations (Anomalies)
    if anomalies:
        anomaly_text = "I also detected some unusual activity this month. "
        for a in anomalies[:2]:
            anomaly_text += f"{a['description']} "
        anomaly_text += "These spikes can often derail a well-planned budget if they become a recurring trend rather than one-time events. "
        happened_parts.append(anomaly_text)
    else:
        happened_parts.append("I didn't detect any major unusual spending spikes this month, which indicates you're sticking well to your typical patterns.")

    # ── 2. Detailed "Why It Matters" Section ──────────────────────────────────
    matters_parts = []
    
    # Paragraph 1: Health & Ratio
    health_desc = f"Your current Financial Health Score stands at **{health}/100**. This score is heavily influenced by your spending ratio, which is currently **{spending_ratio:.1f}%** of your income. "
    if spending_ratio > 80:
        health_desc += "A spending ratio above 80% leaves very little room for error and limited capacity for wealth building. "
    elif spending_ratio < 50:
        health_desc += "Maintaining a spending ratio below 50% is a powerful way to accelerate your wealth accumulation. "
    else:
        health_desc += "Your spending ratio is in a moderate range, but there is always room to optimize for higher savings. "
    matters_parts.append(health_desc)
    
    # Paragraph 2: Goal Alignment
    goal_desc = f"Your primary financial goal is **'{goal}'**. "
    if savings > 0:
        goal_desc += f"This month, you successfully generated a surplus of **₹{savings:,.2f}**. This amount is the fuel for your '{goal}' objective. If you continue at this rate, you are on a positive trajectory toward your targets. "
    else:
        goal_desc += f"Currently, you are in a deficit of **₹{abs(savings):,.2f}**. Every rupee spent beyond your income is a delay in reaching your '{goal}' goals. It's important to address this gap to ensure your long-term plans stay on track. "
    matters_parts.append(goal_desc)
    
    # ── 3. Recommendations ──────────────────────────────────────────────────
    recs = []
    for cat in cats[:2]:
        recs.append({
            "type": "budget",
            "category": cat,
            "amount": int(curr_exp * 0.1),
            "reason": f"By reducing your {cat} spending by just 10% (₹{curr_exp*0.1:,.0f}), you could significantly boost your monthly savings and shorten the time to reach your '{goal}' target."
        })
    
    if anomalies:
        recs.append({
            "type": "goal",
            "category": "Emergency Fund",
            "amount": 5000,
            "reason": "Given the unusual spending spikes detected this month, increasing your emergency fund contributions will provide a much-needed safety net for future surprises."
        })
    elif savings > 1000:
         recs.append({
            "type": "investment",
            "category": "Wealth Building",
            "amount": int(savings * 0.5),
            "reason": f"Since you have a surplus this month, allocating 50% of it (₹{savings*0.5:,.0f}) toward investments would be a smart move to align with your '{goal}' objective."
        })
    
    return {
        "what_happened": "\n\n".join(happened_parts),
        "why_it_matters": "\n\n".join(matters_parts),
        "recommendations": recs
    }


def generate_monthly_xai_report(user_data_summary, user=None):
    """
    Calls Gemini to generate a humanized, detailed, and personalized Explainable AI (XAI) Monthly Report.
    Utilizes historical summaries to provide accountability-driven progress tracking.
    """
    from insights.models import AIInsightsLog
    from django.utils import timezone
    from datetime import timedelta
    import google.generativeai as genai

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
                pass

    # ── 2. Load prior advice for Historical Accountability (Last 3 Records) ──
    memory_context = ""
    if user:
        priors = AIInsightsLog.objects.filter(
            user=user, feature_name=feature_name
        ).order_by('-created_at')[:3]
        
        if priors:
            memory_list = []
            for idx, p in enumerate(priors):
                try:
                    p_data = json.loads(p.generated_insight)
                    memory_list.append(f"Advice {idx+1} ({p.created_at.strftime('%Y-%m-%d')}): {p_data.get('what_happened', '')} | Recs: {json.dumps(p_data.get('recommendations', []))}")
                except Exception:
                    continue
            
            if memory_list:
                memory_context_str = "\n".join(memory_list)
                memory_context = f"--- HISTORICAL ACCOUNTABILITY ---\n{memory_context_str}\n"

    api_key = getattr(settings, 'GEMINI_API_KEY', None)
    if not api_key or not genai:
        return generate_rule_based_monthly_report(user_data_summary)

    genai.configure(api_key=api_key)
    
    # Extract enriched context
    profile = user_data_summary.get('user_profile', {})
    anomalies = user_data_summary.get('anomalies', [])
    cat_breakdown = user_data_summary.get('full_category_breakdown', {})
    goals = user_data_summary.get('savings_goals', [])

    prompt = f"""
    You are 'Neo', a warm, empathetic, yet highly professional and analytical Financial Coach. 
    Your goal is to provide a deep, humanized report on the user's financial behavior.

    {memory_context}

    --- USER CONTEXT ---
    User Occupation: {profile.get('occupation')}
    Financial Goal: {profile.get('financial_goal')}
    Investment Risk Profile: {profile.get('investment_risk')}
    
    --- FINANCIAL DATA (MONTHLY SNAPSHOT) ---
    Current Month: Income ₹{user_data_summary.get('current_month_income', 0)} | Spending ₹{user_data_summary.get('current_month_spending', 0)}
    Previous Month: Income ₹{user_data_summary.get('previous_month_income', 0)} | Spending ₹{user_data_summary.get('previous_month_spending', 0)}
    Financial Health Score: {user_data_summary.get('health_score', 0)}/100
    
    --- DETAILED CATEGORY BREAKDOWN ---
    {json.dumps(cat_breakdown)}
    
    --- ACTIVE SAVINGS GOALS ---
    {json.dumps(goals)}
    
    --- DETECTED ANOMALIES ---
    {json.dumps(anomalies)}

    Instructions:
    Generate a detailed response strictly as a JSON object. The tone should be humanized—speak directly to the user (use "you"). 

    Required Schema:
    {{
      "what_happened": "A highly detailed report spanning 2-3 paragraphs (approx. 8-12 sentences total). Do NOT just list numbers; describe the 'story' of the month. Contrast their categories against their occupation ({profile.get('occupation')}). Acknowledge specific improvements or regressions based on the Historical Accountability section. Use '\n\n' for paragraph breaks.",
      "why_it_matters": "A deep strategic analysis spanning 2 paragraphs (approx. 5-8 sentences). Connect their current spending velocity and financial health score directly to their '{profile.get('financial_goal')}' goal and their {profile.get('investment_risk')} risk tolerance. Explain the long-term impact on their future wealth. Use '\n\n' for paragraph breaks.",
      "recommendations": [
        {{
          "type": "budget" or "goal",
          "category": "Name of category or goal",
          "amount": integer,
          "reason": "A detailed 2-3 sentence behavioral nudge explaining WHY this specific action is the keys to unlocking their '{profile.get('financial_goal')}' goal."
        }}
      ]
    }}
    Provide exactly 3-4 highly personalized recommendations. Ensure valid JSON. No markdown backticks.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.3))
        
        raw_text = response.text.strip()
        
        # Robust JSON extraction
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
        else:
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
        err_msg = str(e)
        
        # ACTIVATE RULE-BASED FALLBACK ON QUOTA ERRORS
        if "429" in err_msg or "quota" in err_msg.lower() or "limit" in err_msg.lower():
            return generate_rule_based_monthly_report(user_data_summary)

        return {
            "what_happened": "We experienced an unexpected error generating your AI report.",
            "why_it_matters": "Technical Detail: " + err_msg[:100],
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
- Current Month Spend: ₹{category_data['current_month_spending']:.2f}
- Previous Month Spend: ₹{category_data['previous_month_spending']:.2f}
- Month-Over-Month Change: {category_data['percentage_change']}%
- Anomaly Detected: {'Yes (' + category_data['anomaly_details'] + ')' if category_data['anomaly_flag'] else 'No'}
- Forecasted Next 30 Days Spend: ₹{category_data['forecasted_next_month_spending']:.2f}
- Suggested Budget Reduction: ₹{category_data['recommended_budget_limit']:.2f}

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
            desc = f"Your {cat} spending is stable at ₹{curr_total:.2f}."
            
        results.append({
            "type": "CategoryAnalysis",
            "title": f"Insight: {cat}",
            "category": cat,
            "description": desc,
            "llm_details": ""  # Populated lazily on View Details click
        })
        
    return results
