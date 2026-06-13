from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, default="")


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TwoFactorCodeSerializer(serializers.Serializer):
    # Accepts a 6-digit TOTP code or a recovery code (e.g. A3B2-F1C9-2D8E-0F7A)
    totp_code = serializers.CharField(max_length=20)


class TwoFactorLoginSerializer(serializers.Serializer):
    pre_auth_token = serializers.CharField()
    totp_code = serializers.CharField(max_length=20)
