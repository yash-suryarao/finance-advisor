import joblib
import pandas as pd
import logging
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# Load trained classifier & vectorizer
try:
    classifier = joblib.load(os.path.join(settings.BASE_DIR, "transaction_classifier.pkl"))
    vectorizer = joblib.load(os.path.join(settings.BASE_DIR, "transaction_vectorizer.pkl"))
except Exception as e:
    classifier_path = os.path.join(settings.BASE_DIR, "transaction_classifier.pkl")
    classifier = None
    vectorizer = None
    logger.warning(f"Failed to load sklearn model from {classifier_path}: {e}")

# Try loading HuggingFace pipeline for Zero-Shot Classification (Smart Category)
try:
    from transformers import pipeline
    # We use a zero-shot model that is fast and capable of accurately classifying financial descriptions
    zero_shot_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    AVAILABLE_CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Insurance", "Loans", "Salary", "Entertainment", "Travel", "Groceries", "Other"]
except Exception as e:
    logger.warning(f"Failed to load HuggingFace Transformers pipeline: {e}")
    zero_shot_classifier = None


def categorize_transaction(description):
    """Categorizes a transaction description using FinBERT/Zero-shot or trained fallback."""
    if zero_shot_classifier is not None:
        try:
            # Use transformer to intelligently classify the expense
            result = zero_shot_classifier(description, candidate_labels=AVAILABLE_CATEGORIES)
            predicted_category = result["labels"][0]
            if result["scores"][0] > 0.3:
                return predicted_category
        except Exception as e:
            logger.error(f"Transformer classification failed: {e}")

    # Fallback to sklearn model
    if vectorizer and classifier:
        X_new = vectorizer.transform([description])
        return classifier.predict(X_new)[0]
    
    return "Other"

def update_category(description, correct_category):
    """Updates the model with new data if prediction is incorrect."""
    if not (vectorizer and classifier):
        return "Model not loaded; cannot update."
        
    df = pd.DataFrame([[description, correct_category]], columns=["description", "category"])
    X_train = vectorizer.transform(df["description"])
    y_train = df["category"]

    # Retrain the model with new data
    classifier.partial_fit(X_train, y_train, classes=classifier.classes_)

    # Save the updated model
    try:
        model_path = os.path.join(settings.BASE_DIR, "transaction_classifier.pkl")
        joblib.dump(classifier, model_path)
        return f"✅ Model updated with new category: {correct_category}"
    except Exception as e:
        return f"❌ Failed to save updated model: {str(e)}"
