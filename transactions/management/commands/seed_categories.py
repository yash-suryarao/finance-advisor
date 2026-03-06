from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from transactions.models import Category

User = get_user_model()

DEFAULT_CATEGORIES = [
    # Expenses
    "Food & Dining", "Transport", "Shopping", "Bills & Utilities",
    "Entertainment", "Health & Medical", "Education", "Rent & Housing",
    "Personal Care", "Travel", "EMI & Loans", "Investments",
    "Gifts & Donations", "Subscriptions", "Miscellaneous",
    # Income
    "Salary", "Freelance", "Business", "Investment Returns",
    "Rental Income", "Bonus", "Other Income",
]


class Command(BaseCommand):
    help = "Seeds all users with the expanded default categories (idempotent — never duplicates)."

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        total_created = 0

        for user in users:
            existing = set(Category.objects.filter(user=user).values_list('name', flat=True))
            created = 0
            for name in DEFAULT_CATEGORIES:
                if name not in existing:
                    Category.objects.create(user=user, name=name)
                    created += 1
            total_created += created
            if created:
                self.stdout.write(f"  ✅ {user.username}: added {created} new categories")
            else:
                self.stdout.write(f"  ⏭  {user.username}: already up to date")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! {total_created} categories added across {users.count()} users."
            )
        )
