from django.urls import path
from .views import SignupView, LoginView, LogoutView, get_user_data, update_avatar, ProfileSetupView, FinancialInputView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import FinancialDataView
from .views import user_profile, user_notifications

urlpatterns = [
    # ==========================================
    # 1. CORE AUTHENTICATION
    # ==========================================
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ==========================================
    # 2. USER PROFILE & SETTINGS
    # ==========================================
    path('profile/', ProfileSetupView.as_view(), name='profile'),
    path('user-data/', get_user_data, name='get_user_data'),
    path('update-avatar/', update_avatar, name='update_avatar'),
    path('api/user-profile/', user_profile, name='user-profile'),

    # ==========================================
    # 3. FINANCIAL CONFIGURATIONS
    # ==========================================
    path('financial-input/', FinancialInputView.as_view(), name='financial_input'),
    path('financial-data/<uuid:user_id>/', FinancialDataView.as_view(), name='financial-data'),

    # ==========================================
    # 4. NOTIFICATIONS
    # ==========================================
    path('api/user-notifications/', user_notifications, name='user-notifications'),
]


