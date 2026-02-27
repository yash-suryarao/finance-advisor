from rest_framework import generics, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate, login
from django.contrib.auth import get_user_model, authenticate, login, logout
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, SignupSerializer, ProfileSerializer, FinancialDataSerializer
from .models import Profile, FinancialData
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.timezone import now
from notifications.models import Notification
from django.db.models.functions import ExtractMonth
from django.shortcuts import get_object_or_404
from django.db.models import Sum


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_data(request):
    user = request.user  # Get the logged-in user
    serializer = UserSerializer(user)  # Convert user object to JSON
    return Response(serializer.data)  # Return JSON response

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_avatar(request):
    user = request.user
    if 'avatar' in request.FILES:
        user.avatar = request.FILES['avatar']
        user.save()
        return Response({"message": "Avatar updated successfully!", "avatar": user.avatar.url})
    return Response({"error": "No file uploaded"}, status=400)



class SignupView(APIView):
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Log the user in (session) and issue JWT tokens
            login(request, user)
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "User created successfully",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user_id": user.id,
                "username": user.username,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class LoginView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        # Fallback check if user sends email instead of username
        user = authenticate(username=username, password=password)
        if not user:
            # Let's check if the username provided is actually the email
            try:
                user_obj = get_user_model().objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except get_user_model().DoesNotExist:
                pass
                
        if user:
            # Proper session-based login if session auth is partly relied upon (from project description)
            login(request, user)
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "message": "Login successful",
                "user_id": user.id,
                "username": user.username
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid Credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Ensure session is also cleared
            logout(request)
            return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Invalid token or token already blacklisted"}, status=status.HTTP_400_BAD_REQUEST)




class ProfileSetupView(generics.RetrieveUpdateAPIView):
    """Handles Profile Setup"""
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return Profile.objects.get_or_create(user=self.request.user)[0]

class FinancialInputView(generics.RetrieveUpdateAPIView):
    """Handles Financial Inputs"""
    queryset = FinancialData.objects.all()
    serializer_class = FinancialDataSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return FinancialData.objects.get_or_create(user=self.request.user)[0]

class FinancialDataView(generics.RetrieveAPIView):
    serializer_class = FinancialDataSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        data = get_object_or_404(FinancialData, user=user_id)
        return Response(self.get_serializer(data).data)



### 🚀 User Profile API ###
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Fetch user profile details including avatar and username.
    """
    user = request.user  # Get logged-in user
    profile = getattr(user, 'profile', None)
    
    full_name = f"{user.first_name} {user.last_name}".strip()
    display_name = full_name if full_name else user.username

    # Safely retrieve avatar URL
    avatar_url = "https://via.placeholder.com/100"
    if profile and hasattr(profile, 'avatar') and profile.avatar and profile.avatar.name:
        avatar_url = request.build_absolute_uri(profile.avatar.url)

    profile_data = {
        "id": user.id,
        "username": display_name,
        "avatar": avatar_url
    }
    return JsonResponse(profile_data)

### 🚀 User Notifications API ###
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_notifications(request):
    """
    - If recipient is 'all', fetch for all users.
    - If recipient is a specific user, fetch only for that user.
    """
    user = request.user

    notifications = Notification.objects.filter(
        recipients__in=["all", str(user.id)]
    ).order_by('-timestamp')

    notifications_list = [
        {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "status": notification.status,
            "timestamp": notification.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        } for notification in notifications
    ]

    return JsonResponse(notifications_list, safe=False)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid token or logout failed."}, status=status.HTTP_400_BAD_REQUEST)
