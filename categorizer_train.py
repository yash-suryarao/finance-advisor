import os
import django
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib

# Setup Django environment to access Models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from transactions.models import Transaction

try:
    # Load dataset
    df_csv = pd.read_csv("transactions_dataset.csv")

    # Ensure correct column names
    if "Transaction" not in df_csv.columns or "Category" not in df_csv.columns:
        raise KeyError("CSV must have 'Transaction' and 'Category' columns.")
except Exception as e:
    print(f"Warning: Could not load transactions_dataset.csv: {e}")
    df_csv = pd.DataFrame(columns=["Transaction", "Category"])

# Fetch DB transactions that have been categorized
print("Fetching real user transactions from database...")
db_transactions = Transaction.objects.exclude(description__isnull=True).exclude(description__exact='').select_related('category')

db_data = []
for t in db_transactions:
    cat_name = t.category.name if t.category else 'Other'
    db_data.append({"Transaction": t.description, "Category": cat_name})

df_db = pd.DataFrame(db_data)
if not df_db.empty:
    print(f"Found {len(df_db)} labeled transactions in the database.")
else:
    print("No labeled transactions found in database.")

# Combine datasets
if not df_db.empty and not df_csv.empty:
    df = pd.concat([df_csv, df_db], ignore_index=True)
elif not df_db.empty:
    df = df_db
else:
    df = df_csv

if df.empty:
    print("Error: No training data available!")
    exit(1)

# Feature (Transaction description) and target (Category)
X = df["Transaction"]  # Transaction descriptions
y = df["Category"]     # Categories

# Convert text into numerical features using TF-IDF Vectorizer
# Added ngram_range to capture multi-word patterns (e.g., "Amazon Prime")
vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
X_transformed = vectorizer.fit_transform(X)

# Train a Naive Bayes classifier
classifier = MultinomialNB()
classifier.fit(X_transformed, y)

# Save model and vectorizer
base_dir = os.path.dirname(os.path.abspath(__file__))
joblib.dump(classifier, os.path.join(base_dir, "transaction_classifier.pkl"))
joblib.dump(vectorizer, os.path.join(base_dir, "transaction_vectorizer.pkl"))

print(f"✅ Model trained successfully on {len(df)} records and saved!")
