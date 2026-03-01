from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from datetime import timedelta
from .models import Transaction, Budget, BudgetHistory, Category
from .nlp_processing import process_voice_transaction
from rest_framework import generics, filters, serializers
from rest_framework.pagination import PageNumberPagination
import csv
from .serializers import TransactionSerializer
import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import Profile
from .serializers import BudgetSerializer, BudgetHistorySerializer, CategorySerializer
import pytesseract
from PIL import Image
import re
import io

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_voice_entry(request):
    """
    Processes voice input and returns structured transaction details for user confirmation.
    """
    voice_text = request.data.get("voice_text", "")
    if not voice_text:
        return Response({"error": "No voice input received"}, status=400)

    transaction_data = process_voice_transaction(voice_text)
    return Response(transaction_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_receipt(request):
    """
    Extracts transaction details from an uploaded receipt image using Tesseract OCR.
    """
    if 'receipt' not in request.FILES:
        return Response({"error": "No receipt image uploaded"}, status=400)

    receipt_file = request.FILES['receipt']
    
    try:
        image = Image.open(receipt_file)
        extracted_text = pytesseract.image_to_string(image)
        
        # Simple heuristic to find amount: look for currency symbols or "Total"
        amount = 0
        amount_matches = re.findall(r'(\$|₹|Rs\.?|INR)?\s*(\d+(?:\.\d{2})?)', extracted_text)
        if amount_matches:
            # Try to find the largest amount which is typically the total
            amounts = [float(match[1]) for match in amount_matches if match[1]]
            if amounts:
                amount = max(amounts)

        # Default category
        category = "Other"
        
        # basic keyword search in text
        text_lower = extracted_text.lower()
        if "food" in text_lower or "restaurant" in text_lower:
            category = "Food"
        elif "grocery" in text_lower or "supermarket" in text_lower or "mart" in text_lower:
            category = "Groceries"
        elif "fuel" in text_lower or "petrol" in text_lower or "gas" in text_lower:
            category = "Transport"
            
    except Exception as e:
        return Response({"error": f"Failed to process image: {str(e)}"}, status=500)

    return Response({
        "amount": amount,
        "transaction_type": "expense",
        "category": category,
        "extracted_text_preview": extracted_text[:200]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_voice_transaction(request):
    """
    Saves user-confirmed transaction to the database.
    """
    user = request.user
    amount = request.data.get("amount")
    transaction_type = request.data.get("transaction_type")
    category_name = request.data.get("category", "Other")

    if not amount or not transaction_type or not category_name:
        return Response({"error": "Missing transaction details"}, status=400)

    # Convert string to Category instance
    category_obj, created = Category.objects.get_or_create(user=user, name=category_name)

    transaction = Transaction.objects.create(
        user=user,
        amount=amount,
        category_type=transaction_type,
        category=category_obj,
        date=now().date()
    )

    return Response({"message": "Transaction saved successfully!", "transaction_id": transaction.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).select_related('category').order_by('-date')[:10]  # Fetch latest 10 transactions

    data = [
        {
            "id": t.id,
            "category_name": t.category.name if t.category else "Other",  # Fetch category name
            "category_type": t.category_type,  # Income or Expense
            "description": t.description,
            "amount": float(t.amount),
            "date": t.date.isoformat(),  # Convert date to JSON format
        }
        for t in transactions
    ]
    
    return JsonResponse(data, safe=False)






@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_bills(request):
    """
    Fetch upcoming recurring payments for the user.
    """
    user = request.user
    today = now().date()
    upcoming_payments = RecurringPayment.objects.filter(
        user=user, 
        next_payment_date__gte=today,  # Payments due today or later
        status="active"
    ).order_by('next_payment_date')

    bills_list = [
        {
            "id": payment.id,
            "name": payment.name,
            "amount": float(payment.amount),
            "category": payment.category,
            "frequency": payment.frequency,
            "days_remaining": (payment.next_payment_date - today).days,
            "next_payment_date": payment.next_payment_date.strftime("%Y-%m-%d")
        } for payment in upcoming_payments
    ]

    return Response(bills_list)


def track_budget_history(user):
    """
    Stores historical budget data and calculates suggested budget.
    """
    current_month = now().month
    current_year = now().year

    budgets = Budget.objects.filter(user=user)

    for budget in budgets:
        category = budget.category
        prev_limit = budget.monthly_limit

        # Get total spending for this category in the last month
        last_month = (now() - timedelta(days=30)).month
        total_spent = Transaction.objects.filter(
            user=user, category_id=category, date__month=last_month
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        # AI Logic to Suggest Budget Adjustment
        suggested_limit = prev_limit
        if total_spent > prev_limit:
            suggested_limit = prev_limit * 1.1  # Increase budget by 10% if overspending
        elif total_spent < (prev_limit * 0.7):
            suggested_limit = prev_limit * 0.9  # Decrease budget by 10% if underused

        # Save to BudgetHistory Table
        BudgetHistory.objects.update_or_create(
            user=user,
            category=category,
            month=current_month,
            year=current_year,
            defaults={
                "previous_limit": prev_limit,
                "actual_spent": total_spent,
                "suggested_limit": suggested_limit,
            }
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_transactions_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Date', 'Category', 'Amount', 'Description'])

    transactions = Transaction.objects.all().values_list('id', 'date', 'category__name', 'amount', 'description')
    for transaction in transactions:
        writer.writerow(transaction)

    return response


# Pagination class for handling multiple transactions
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  # Show 10 transactions per page
    page_size_query_param = 'page_size'
    max_page_size = 100


# View for listing and creating transactions
class TransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description']
    ordering_fields = ['date', 'amount']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(user_id=user.id).order_by('-date')
        category = self.request.query_params.get('category', None)
        min_amount = self.request.query_params.get('min_amount', None)
        date = self.request.query_params.get('date', None)

        if category:
            queryset = queryset.filter(category__id=category)
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        if date:
            queryset = queryset.filter(date=date)

        return queryset

    def perform_create(self, serializer):
        # Auto-categorize if description is provided but category is missing
        instance = serializer.validated_data
        if 'description' in instance and not instance.get('category'):
            try:
                from .categorizer import categorize_transaction
                predicted_cat_name = categorize_transaction(instance['description'])
                cat, _ = Category.objects.get_or_create(user=self.request.user, name=predicted_cat_name)
                serializer.save(user=self.request.user, category=cat)
                return
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to auto-categorize: {e}")
        serializer.save(user=self.request.user)




class TransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)



class CategoryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.filter(user=self.request.user)
        if not queryset.exists():
            default_categories = ['Food', 'Transport', 'Shopping', 'Bills', 'Salary', 'Entertainment', 'Other']
            for name in default_categories:
                Category.objects.create(user=self.request.user, name=name)
            queryset = Category.objects.filter(user=self.request.user)
        return queryset



class CurrencyConverter(APIView):
    def get(self, request):
        base_currency = request.query_params.get('base', 'USD')
        target_currency = request.query_params.get('target', 'INR')

        api_url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        response = requests.get(api_url)

        if response.status_code != 200:
            return Response({"error": "Failed to fetch exchange rates"}, status=500)

        data = response.json()
        conversion_rate = data["rates"].get(target_currency, None)

        if conversion_rate:
            return Response({"rate": conversion_rate}, status=200)
        else:
            return Response({"error": "Invalid currency"}, status=400)

class BudgetView(generics.ListCreateAPIView):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)


class BudgetHistoryView(generics.ListAPIView):
    serializer_class = BudgetHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BudgetHistory.objects.filter(
            user=self.request.user, 
            month=self.request.query_params.get('month'), 
            year=self.request.query_params.get('year')
        )

