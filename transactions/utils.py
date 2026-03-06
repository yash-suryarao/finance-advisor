# transactions/utils.py
from .models import alerts, Budget, Transaction
from django.db.models import Sum
import joblib
import os
import csv
from django.conf import settings

def check_budget_alert(user):
    budgets = Budget.objects.filter(user=user)
    for budget in budgets:
        spent = Transaction.objects.filter(
            user=user, category=budget.category, category_type='expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        usage_percentage = (spent / budget.monthly_limit) * 100 if budget.monthly_limit > 0 else 0
        
        if usage_percentage >= 80:
            alerts.objects.create(
                user=user,
                message=f"You have used {usage_percentage:.2f}% of your budget for {budget.category.name}. Consider reviewing your spending."
            )



# Load the model and vectorizer at startup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(BASE_DIR, "transaction_classifier.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "transaction_vectorizer.pkl")

classifier = joblib.load(MODEL_PATH)
vectorizer = joblib.load(VECTORIZER_PATH)


def categorize_transaction(description):
    """Predicts category for a given transaction description"""
    X_new = vectorizer.transform([description])
    predicted_category = classifier.predict(X_new)[0]
    return predicted_category


def export_all_transactions_to_csv():
    """
    Exports all transactions across the entire platform to a single unified CSV file.
    Runs asynchronously via a debounced Django signal whenever any transaction is modified.
    """
    dataset_dir = os.path.join(settings.BASE_DIR, 'media', 'datasets')
    os.makedirs(dataset_dir, exist_ok=True)
    
    file_path = os.path.join(dataset_dir, 'all_transactions.csv')
    
    # Fetch all transactions across the entire database
    transactions = Transaction.objects.all().select_related('category', 'user').order_by('date', 'created_at')
    
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # Write header with user_id to separate context cleanly
        writer.writerow(['user_id', 'date', 'amount', 'category', 'type', 'description'])
        
        # Write data
        for t in transactions:
            category_name = t.category.name if t.category else 'Other'
            writer.writerow([
                str(t.user.id),
                t.date.isoformat(),
                float(t.amount),
                category_name,
                t.category_type.capitalize(),
                t.description or ''
            ])
    
    return file_path
