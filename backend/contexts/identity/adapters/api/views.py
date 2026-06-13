from datetime import timedelta

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from ...adapters.orm.django_recovery_code_repository import DjangoORMRecoveryCodeRepository
from ...adapters.orm.django_user_repository import DjangoORMUserRepository
from ...adapters.services.django_auth_service import DjangoAuthService
from ...adapters.services.pyotp_service import PyOTPService
from ...domain.entities import User
from ...domain.exceptions import (
    InvalidCredentialsError,
    TOTPAlreadyEnabledError,
    TOTPInvalidError,
    TOTPNotEnabledError,
    UserAlreadyExistsError,
)
from ...models import UserModel
from ...use_cases.complete_two_factor_login import (
    CompleteTwoFactorLoginInput,
    CompleteTwoFactorLoginUseCase,
)
from ...use_cases.disable_two_factor import DisableTwoFactorInput, DisableTwoFactorUseCase
from ...use_cases.enable_two_factor import EnableTwoFactorInput, EnableTwoFactorUseCase
from ...use_cases.get_current_user import GetCurrentUserUseCase
from ...use_cases.login_user import LoginUserInput, LoginUserUseCase
from ...use_cases.register_user import RegisterUserInput, RegisterUserUseCase
from ...use_cases.setup_two_factor import SetupTwoFactorInput, SetupTwoFactorUseCase
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    TwoFactorCodeSerializer,
    TwoFactorLoginSerializer,
)


class PreAuthToken(AccessToken):
    """Short-lived token for the 2FA intermediate step. JWTAuthentication rejects it (wrong token_type)."""
    token_type = "pre_auth"
    lifetime = timedelta(minutes=5)


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "is_kyc_verified": user.is_kyc_verified,
        "is_2fa_enabled": user.is_2fa_enabled,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _make_tokens(user_model: UserModel) -> dict:
    refresh = RefreshToken.for_user(user_model)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def _2fa_deps() -> dict:
    return {
        "user_repo": DjangoORMUserRepository(),
        "two_factor_svc": PyOTPService(),
        "recovery_repo": DjangoORMRecoveryCodeRepository(),
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = RegisterUserUseCase(
            user_repo=DjangoORMUserRepository(),
            auth_service=DjangoAuthService(),
        )
        try:
            user = use_case.execute(RegisterUserInput(**serializer.validated_data))
        except UserAlreadyExistsError:
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_model = UserModel.objects.get(pk=user.id)
        return Response(
            {"user": _user_to_dict(user), "tokens": _make_tokens(user_model)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = LoginUserUseCase(
            user_repo=DjangoORMUserRepository(),
            auth_service=DjangoAuthService(),
        )
        try:
            user = use_case.execute(LoginUserInput(**serializer.validated_data))
        except InvalidCredentialsError:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_model = UserModel.objects.get(pk=user.id)

        if user_model.is_2fa_enabled:
            pre_auth = PreAuthToken.for_user(user_model)
            return Response(
                {"requires_2fa": True, "pre_auth_token": str(pre_auth)},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"user": _user_to_dict(user), "tokens": _make_tokens(user_model)},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_case = GetCurrentUserUseCase(user_repo=DjangoORMUserRepository())
        user = use_case.execute(str(request.user.pk))
        return Response({"user": _user_to_dict(user)}, status=status.HTTP_200_OK)


class TwoFactorSetupView(APIView):
    """Generate a TOTP secret and return the QR code. Does not enable 2FA yet."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        deps = _2fa_deps()
        use_case = SetupTwoFactorUseCase(
            user_repo=deps["user_repo"],
            two_factor_svc=deps["two_factor_svc"],
        )
        try:
            result = use_case.execute(SetupTwoFactorInput(user_id=str(request.user.pk)))
        except TOTPAlreadyEnabledError:
            return Response({"error": "2FA is already enabled"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "secret": result.secret,
            "qr_uri": result.qr_uri,
            "qr_image": result.qr_image_base64,
        })


class TwoFactorVerifyView(APIView):
    """Confirm the first TOTP code to activate 2FA and receive recovery codes."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = EnableTwoFactorUseCase(**_2fa_deps())
        try:
            result = use_case.execute(EnableTwoFactorInput(
                user_id=str(request.user.pk),
                totp_code=serializer.validated_data["totp_code"],
            ))
        except TOTPAlreadyEnabledError:
            return Response({"error": "2FA is already enabled"}, status=status.HTTP_400_BAD_REQUEST)
        except TOTPInvalidError:
            return Response({"error": "Invalid TOTP code"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"recovery_codes": result.recovery_codes})


class TwoFactorDisableView(APIView):
    """Disable 2FA using a valid TOTP code or recovery code."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TwoFactorCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = DisableTwoFactorUseCase(**_2fa_deps())
        try:
            use_case.execute(DisableTwoFactorInput(
                user_id=str(request.user.pk),
                totp_code=serializer.validated_data["totp_code"],
            ))
        except TOTPNotEnabledError:
            return Response({"error": "2FA is not enabled"}, status=status.HTTP_400_BAD_REQUEST)
        except TOTPInvalidError:
            return Response({"error": "Invalid code"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "2FA disabled"})


class TwoFactorLoginView(APIView):
    """Complete a 2FA-gated login: pre_auth_token + TOTP code (or recovery code)."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TwoFactorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = PreAuthToken(serializer.validated_data["pre_auth_token"])
            user_id = str(token.payload.get("user_id"))
        except (TokenError, Exception):
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_401_UNAUTHORIZED)

        use_case = CompleteTwoFactorLoginUseCase(**_2fa_deps())
        try:
            user = use_case.execute(CompleteTwoFactorLoginInput(
                user_id=user_id,
                totp_code=serializer.validated_data["totp_code"],
            ))
        except TOTPInvalidError:
            return Response({"error": "Invalid TOTP code"}, status=status.HTTP_401_UNAUTHORIZED)
        except (TOTPNotEnabledError, ValueError):
            return Response({"error": "Invalid request"}, status=status.HTTP_400_BAD_REQUEST)

        user_model = UserModel.objects.get(pk=user.id)
        return Response(
            {"user": _user_to_dict(user), "tokens": _make_tokens(user_model)},
            status=status.HTTP_200_OK,
        )
