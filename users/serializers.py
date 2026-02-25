from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, FinancialData

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields =  '__all__'
class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    full_name = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password', 'phone_no']

    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        phone_no = validated_data.pop('phone_no', None)
        password = validated_data.pop('password')
        email = validated_data.pop('email')
        
        # Split full_name
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        
        # Generate a valid unique username from email
        username = email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create user with generated username and parsed names
        user = User.objects.create_user(
            email=email, 
            username=username, 
            password=password, 
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            **validated_data
        )
        if phone_no is not None:
            user.phone_no = phone_no
        user.save()
        return user





class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'

class FinancialDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialData
        fields = '__all__'
