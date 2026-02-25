from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from transactions.models import Transaction, Category
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class TransactionIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='pw')
        refresh = RefreshToken.for_user(self.user)
        self.auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'}
        self.category = Category.objects.create(user=self.user, name='Food')
        
    def test_create_transaction_api(self):
        payload = {
            'amount': 150.50,
            'description': 'Lunch at cafe',
            'category': 'Food',
            'transaction_type': 'expense',
            'currency': 'USD'
        }
        res = self.client.post(
            reverse('confirm_voice_transaction'), 
            data=payload, 
            content_type='application/json',
            **self.auth_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Transaction.objects.filter(user=self.user, amount=150.50).exists())

    def test_auto_categorization(self):
        # TransactionListCreateView handles auto classification if category ID missing
        payload = {
            'amount': '50.00',
            'description': 'Netflix subscription',
            'date': '2023-10-01',
            'currency': 'USD'
        }
        res = self.client.post(
            reverse('transaction_list_create'), 
            data=payload, 
            content_type='application/json',
            **self.auth_headers
        )
        self.assertEqual(res.status_code, 201)
        t = Transaction.objects.get(description='Netflix subscription')
        self.assertIsNotNone(t.category)

    def test_delete_transaction(self):
        t = Transaction.objects.create(
            user=self.user, amount=100, category=self.category, date='2023-10-01'
        )
        res = self.client.delete(
            reverse('transaction_detail', args=[t.id]),
            **self.auth_headers
        )
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Transaction.objects.filter(id=t.id).exists())
