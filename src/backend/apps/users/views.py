from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.conf import settings
from django.contrib.auth import authenticate
from .models import User
from .serializers import UserSerializer, UserCreateSerializer, UserUpdateSerializer, UserPasswordResetSerializer
from .permissions import IsAdmin


def _cookie_options(max_age):
    return {
        'max_age': int(max_age.total_seconds()),
        'httponly': True,
        'secure': not settings.DEBUG,
        'samesite': settings.JWT_COOKIE_SAMESITE,
        'path': '/',
    }


def _set_token_cookies(response, access_token, refresh_token=None):
    response.set_cookie(
        'access_token',
        str(access_token),
        **_cookie_options(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']),
    )
    if refresh_token is not None:
        response.set_cookie(
            'refresh_token',
            str(refresh_token),
            **_cookie_options(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']),
        )


def _clear_token_cookies(response):
    response.delete_cookie('access_token', path='/', samesite=settings.JWT_COOKIE_SAMESITE)
    response.delete_cookie('refresh_token', path='/', samesite=settings.JWT_COOKIE_SAMESITE)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        if not username or not password:
            return Response(
                {'detail': 'Username and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(username=username, password=password)

        if not user or not user.is_active:
            return Response(
                {'detail': 'Invalid credentials or inactive account.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        response = Response({'user': UserSerializer(user).data})
        _set_token_cookies(response, refresh.access_token, refresh)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh') or request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            response = Response({'detail': 'Logged out successfully.'})
            _clear_token_cookies(response)
            return response
        except Exception:
            response = Response({'detail': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)
            _clear_token_cookies(response)
            return response


class CookieTokenRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refresh') or request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        serializer.is_valid(raise_exception=True)
        response = Response({'detail': 'Token refreshed.'})
        _set_token_cookies(
            response,
            serializer.validated_data['access'],
            serializer.validated_data.get('refresh'),
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('full_name')
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UserCreateSerializer
        return UserSerializer


class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserSerializer


class UserPasswordResetView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)
        serializer = UserPasswordResetSerializer(data=request.data, context={'user': user})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'detail': 'Password updated successfully.'})
