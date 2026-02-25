import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from insights.models import BudgetInsight, SavingsGoal
from transactions.models import Transaction, Category, Budget as TransactionsBudget, BudgetHistory
from datetime import datetime
from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal

User = get_user_model()

class InsightsViewLogicalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        
        # Use simplejwt TokenAuth since views use @permission_classes([IsAuthenticated]) under DRF
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
        
        # Setup categories
        self.cat_food = Category.objects.create(user=self.user, name="Food")
        self.cat_rent = Category.objects.create(user=self.user, name="Rent")
        
        # Setup TransactionsBudget
        TransactionsBudget.objects.create(user=self.user, category="Food", monthly_limit=500.00)
        TransactionsBudget.objects.create(user=self.user, category="Rent", monthly_limit=1000.00)
        
        # Log some historical budgets for projection data
        current_year = now().year
        BudgetHistory.objects.create(
            user=self.user, category="Food", month=1, year=current_year,
            previous_limit=500.00, actual_spent=400.00, suggested_limit=450.00
        )
        BudgetHistory.objects.create(
            user=self.user, category="Rent", month=1, year=current_year,
            previous_limit=1000.00, actual_spent=1000.00, suggested_limit=1000.00
        )

        
        # Prepare an Insights record specifically suggesting an update
        BudgetInsight.objects.create(
            user=self.user,
            category="Food",
            average_spending=450.00,
            forecasted_spending=600.00, # Expected to go over budget!
            savings_recommendation="Decrease dining out by 20% to stay under budget limit."
        )

    def test_get_savings_projections(self):
        """Test the logic of historical accrual + forward projections in get_savings_projections"""
        # Call the view via URL mapping we confirmed earlier
        response = self.client.get(reverse('savings_projections'))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Verify structure
        self.assertIn('months', data)
        self.assertIn('amounts', data)
        
        # Our single historical entry from Month 1 saved $100
        # Expected lengths: 1 historical + 12 forward = 13 entries
        self.assertEqual(len(data['months']), 13)
        self.assertEqual(len(data['amounts']), 13)
        
        # Month 1 saved should be (500-400) + (1000-1000) = 100
        self.assertEqual(data['amounts'][0], 100.00)
        
        # Forward projecting month 2 should add current_budget(1500) - avg_spend(0) to previous cumulation
        self.assertEqual(data['amounts'][1], 1600.00)

    def test_accept_suggested_budget(self):
        """Test accepting an AI limit writes properly to Database Budget limits"""
        
        # Assert initial condition
        food_budget = TransactionsBudget.objects.get(user=self.user, category='Food')
        self.assertEqual(food_budget.monthly_limit, Decimal('500.00'))

        # Perform logical test
        response = self.client.post(reverse('accept-suggested-budget'), json.dumps({
            'category': 'Food',
            'new_limit': 650.00
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        # Check database directly for the logical update
        food_budget.refresh_from_db()
        self.assertEqual(food_budget.monthly_limit, Decimal('650.00'))
