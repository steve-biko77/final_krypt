from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from ...adapters.orm.django_user_repository import DjangoORMUserRepository
from ...adapters.services.django_auth_service import DjangoAuthService
from ...domain.entities import User
from ...domain.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from ...models import UserModel
from ...use_cases.get_current_user import GetCurrentUserUseCase
from ...use_cases.login_user import LoginUserInput, LoginUserUseCase
from ...use_cases.register_user import RegisterUserInput, RegisterUserUseCase
from .serializers import LoginSerializer, RegisterSerializer


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "is_kyc_verified": user.is_kyc_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _make_tokens(user_model: UserModel) -> dict:
    refresh = RefreshToken.for_user(user_model)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        use_case = RegisterUserUseCase(
            user_repo=DjangoORMUserRepository(),
            auth_service=DjangoAuthService(),
        )
        try:
            user = use_case.execute(RegisterUserInput(**data))
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
        data = serializer.validated_data

        use_case = LoginUserUseCase(
            user_repo=DjangoORMUserRepository(),
            auth_service=DjangoAuthService(),
        )
        try:
            user = use_case.execute(LoginUserInput(**data))
        except InvalidCredentialsError:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_model = UserModel.objects.get(pk=user.id)
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
