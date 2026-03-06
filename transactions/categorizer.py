import joblib
import logging
import os
import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Expanded category list (22 categories) ─────────────────────────────────
AVAILABLE_CATEGORIES = [
    # Expenses
    "Food & Dining", "Transport", "Shopping", "Bills & Utilities",
    "Entertainment", "Health & Medical", "Education", "Rent & Housing",
    "Personal Care", "Travel", "EMI & Loans", "Investments",
    "Gifts & Donations", "Subscriptions", "Miscellaneous",
    # Income
    "Salary", "Freelance", "Business", "Investment Returns",
    "Rental Income", "Bonus", "Other Income",
]

# ── Load Naive Bayes fallback model ────────────────────────────────────────
try:
    classifier = joblib.load(os.path.join(settings.BASE_DIR, "transaction_classifier.pkl"))
    vectorizer = joblib.load(os.path.join(settings.BASE_DIR, "transaction_vectorizer.pkl"))
    logger.info("Naive Bayes categorizer loaded successfully.")
except Exception as e:
    classifier = None
    vectorizer = None
    logger.warning(f"Failed to load Naive Bayes model: {e}")


def _gemini_categorize(description: str) -> str | None:
    """
    Calls Gemini API to classify a transaction description.
    Returns a category string if successful, None otherwise.
    """
    try:
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        categories_str = ", ".join(AVAILABLE_CATEGORIES)
        prompt = (
            f"You are a financial transaction categorizer.\n"
            f"Classify this transaction description into exactly ONE of these categories:\n"
            f"{categories_str}\n\n"
            f"Transaction: \"{description}\"\n\n"
            f"Reply with ONLY the category name, nothing else."
        )

        response = model.generate_content(prompt)
        predicted = response.text.strip().strip('"').strip("'")

        # Validate that Gemini returned a known category
        if predicted in AVAILABLE_CATEGORIES:
            logger.info(f"[GEMINI CATEGORIZER] '{description}' → '{predicted}'")
            return predicted

        # Try case-insensitive match
        for cat in AVAILABLE_CATEGORIES:
            if cat.lower() == predicted.lower():
                return cat

        logger.warning(f"[GEMINI CATEGORIZER] Unknown category returned: '{predicted}'")
        return None

    except Exception as e:
        logger.warning(f"[GEMINI CATEGORIZER] Failed (falling back to Naive Bayes): {e}")
        return None


def _naive_bayes_categorize(description: str) -> str | None:
    """Uses the trained Naive Bayes + TF-IDF model."""
    if vectorizer and classifier:
        try:
            X_new = vectorizer.transform([description])
            return classifier.predict(X_new)[0]
        except Exception as e:
            logger.error(f"[NAIVE BAYES] Prediction failed: {e}")
    return None


def categorize_transaction(description: str) -> str:
    """
    Main entry point.
    Priority: Gemini API → Naive Bayes → 'Other'
    """
    if not description or not description.strip():
        return "Other"

    # 1. Try Gemini (fast, no retry — immediate fallback on any error)
    result = _gemini_categorize(description)
    if result:
        return result

    # 2. Fall back to Naive Bayes
    result = _naive_bayes_categorize(description)
    if result:
        return result

    # 3. Default
    return "Other"
