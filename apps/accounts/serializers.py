import re

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Role, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        choices=[(Role.EMPLOYER, "Employer"), (Role.CANDIDATE, "Candidate")])

    class Meta:
        model = User
        fields = ["id", "email", "phone", "role", "password"]

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_phone(self, value):
        if not value:
            return value
        value = re.sub(r"[\s\-()]", "", value)             # allow 98765 43210 or 98765-43210
        if not re.fullmatch(r"\+?[0-9]{7,15}", value):
            raise serializers.ValidationError(
                "Enter a valid phone number: 7 to 15 digits, with an optional + at the start.")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def validate_password(self, value):
        validate_password(value)      # Django's built-in strength rules
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "phone", "role", "is_verified", "created_at"]


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role          # the role travels inside the token
        return token

    def validate(self, attrs):
        # emails are stored in lower case, so Manu@x.com and manu@x.com are the same login
        email = (attrs.get("email") or "").strip()
        match = User.objects.filter(email__iexact=email).first()
        if match:
            attrs["email"] = match.email
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data