"""
DRF views / ViewSets for the Task Management System.

Every endpoint is documented with ``@extend_schema`` for drf-spectacular.
"""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
import random
from django.core.cache import cache

from .models import Channel, Feedback, Message, Project, Task, Notification, Document
from .permissions import IsProjectMember, IsPM
from .serializers import (
    ChannelSerializer,
    DashboardSerializer,
    FeedbackSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    LoginSerializer,
    GoogleLoginSerializer,
    MessageSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    RegisterSerializer,
    TaskApproveSerializer,
    TaskMoveSerializer,
    TaskSerializer,
    UserSerializer,
    UserUpdateSerializer,
    PasswordChangeSerializer,
    EmployeeSerializer,
    EmployeeDetailSerializer,
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
    GlobalSearchResponseSerializer,
    NotificationSerializer,
    DocumentSerializer,
)

User = get_user_model()


def _set_auth_cookies(response: Response, refresh: RefreshToken) -> Response:
    """Attach ``access_token`` and ``refresh_token`` HttpOnly cookies."""
    jwt_cfg = settings.SIMPLE_JWT

    response.set_cookie(
        key=jwt_cfg.get("AUTH_COOKIE", "access_token"),
        value=str(refresh.access_token),
        httponly=jwt_cfg.get("AUTH_COOKIE_HTTP_ONLY", True),
        samesite=jwt_cfg.get("AUTH_COOKIE_SAMESITE", "Lax"),
        secure=jwt_cfg.get("AUTH_COOKIE_SECURE", False),
        max_age=int(jwt_cfg["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        path=jwt_cfg.get("AUTH_COOKIE_PATH", "/"),
    )
    response.set_cookie(
        key=jwt_cfg.get("AUTH_COOKIE_REFRESH", "refresh_token"),
        value=str(refresh),
        httponly=jwt_cfg.get("AUTH_COOKIE_HTTP_ONLY", True),
        samesite=jwt_cfg.get("AUTH_COOKIE_SAMESITE", "Lax"),
        secure=jwt_cfg.get("AUTH_COOKIE_SECURE", False),
        max_age=int(jwt_cfg["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=jwt_cfg.get("AUTH_COOKIE_PATH", "/"),
    )
    return response


def _clear_auth_cookies(response: Response) -> Response:
    """Delete auth cookies."""
    jwt_cfg = settings.SIMPLE_JWT
    response.delete_cookie(jwt_cfg.get("AUTH_COOKIE", "access_token"))
    response.delete_cookie(jwt_cfg.get("AUTH_COOKIE_REFRESH", "refresh_token"))
    return response


class RegisterView(generics.CreateAPIView):
    """Register a new user account."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register",
        description="Create a new user account.",
        responses={201: UserSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        profile = getattr(user, 'profile', None)
        refresh['role'] = profile.role if profile else 'USER'

        
        data = UserSerializer(user).data
        data['accessToken'] = str(refresh.access_token)
        data['refreshToken'] = str(refresh)
        
        response = Response(data, status=status.HTTP_201_CREATED)
        return _set_auth_cookies(response, refresh)


class LoginView(APIView):
    """Authenticate and receive JWT in HttpOnly cookies."""

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        summary="Login",
        description="Authenticate with username/password. JWT tokens are set as HttpOnly cookies.",
        request=LoginSerializer,
        responses={200: UserSerializer, 401: OpenApiResponse(description="Invalid credentials")},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        profile = getattr(user, 'profile', None)
        refresh['role'] = profile.role if profile else 'USER'


        data = UserSerializer(user).data
        data['accessToken'] = str(refresh.access_token)
        data['refreshToken'] = str(refresh)

        response = Response(data)
        return _set_auth_cookies(response, refresh)


class GoogleLoginView(APIView):
    """Authenticate via Google ID Token and receive JWT."""

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    @extend_schema(
        summary="Google Login",
        description="Authenticate using Google id_token. The user must be pre-registered by an admin. JWT tokens are set as HttpOnly cookies.",
        request=GoogleLoginSerializer,
        responses={200: UserSerializer, 401: OpenApiResponse(description="Unregistered user or invalid token.")},
        tags=["auth"]
    )
    def post(self, request):
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        try:
            client_id = getattr(settings, 'GOOGLE_CLIENT_ID', None)
            
            # Agar client_id konfiguratsiya qilinmagan bo'lsa (bo'sh string), shunchaki imzoni tekshiramiz.
            # Lekin xavfsizlik uchun `.env` faylida GOOGLE_CLIENT_ID beringanligi afzal.
            if client_id:
                idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), audience=client_id)
            else:
                # Audience tekshiruvisiz
                idinfo = id_token.verify_oauth2_token(token, google_requests.Request())
            
            email = idinfo.get("email")
            if not email:
                return Response({"detail": "Token tarkibida email topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        except ValueError as e:
            return Response({"detail": "Yaroqsiz Google tokeni."}, status=status.HTTP_401_UNAUTHORIZED)
        
        user = User.objects.filter(email=email).first()
        
        if not user:
            return Response(
                {"detail": "Kechirasiz, sizning hisobingiz tizimda mavjud emas. Iltimos, admin bilan bog'laning."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"detail": "Sizning hisobingiz bloklangan."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.profile.role

        data = UserSerializer(user).data
        data['accessToken'] = str(refresh.access_token)
        data['refreshToken'] = str(refresh)

        response = Response(data)
        return _set_auth_cookies(response, refresh)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(response=dict, description="Kod generatsiya qilindi"),
            400: OpenApiResponse(response=dict, description="Validatsiya xatosi (masalan: email formati noto'g'ri)"),
            404: OpenApiResponse(response=dict, description="Foydalanuvchi topilmadi"),
            429: OpenApiResponse(response=dict, description="Ko'p so'rov yuborildi (Rate Limit)")
        },
        tags=["auth"]
    )
    def post(self, request):
        import time
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            if not User.objects.filter(email=email).exists():
                return Response(
                    {"detail": "Ushbu email bilan foydalanuvchi topilmadi."}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            retry_key = f"password_reset_retry_{email}"
            retry_timestamp = cache.get(retry_key)
            
            if retry_timestamp:
                time_passed = time.time() - retry_timestamp
                time_left = int(60 - time_passed)
                if time_left > 0:
                    return Response(
                        {"detail": f"Iltimos, qayta urinish uchun {time_left} soniya kuting."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS
                    )

            # Yangi kodni generatsiya qilish
            code = f"{random.randint(100000, 999999)}"
            
            # Keshda 5 daqiqaga (300 soniya) saqlash
            cache.set(f"password_reset_{email}", code, timeout=300)
            
            # Cheklov kalitini 60 soniyaga saqlash
            cache.set(retry_key, time.time(), timeout=60)
            
            return Response(
                {
                    "code": code, 
                    "retry_timeout": 60,
                    "message": "Kod generatsiya qilindi va 5 daqiqa davomida faol bo'ladi."
                }, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(response=dict, description="Kod to'g'ri"),
            400: OpenApiResponse(response=dict, description="Noto'g'ri kod, yoki validatsiya xatosi"),
        },
        tags=["auth"]
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            return Response(
                {"message": "Kod muvaffaqiyatli tasdiqlandi!"}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(response=dict, description="Parol muvaffaqiyatli yangilandi"),
            400: OpenApiResponse(response=dict, description="Noto'g'ri kod, yoki validatsiya xatosi"),
            404: OpenApiResponse(response=dict, description="Foydalanuvchi topilmadi")
        },
        tags=["auth"]
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            new_password = serializer.validated_data['new_password']
                
            try:
                user = User.objects.filter(email=email).first()
                if not user:
                    return Response({"detail": "Foydalanuvchi topilmadi."}, status=status.HTTP_404_NOT_FOUND)
                user.set_password(new_password)
                user.save()
                
                # Kod ishlatilgandan so'ng keshdan o'chirish
                cache.delete(f"password_reset_{email}")
                cache.delete(f"password_reset_retry_{email}")
                
                return Response(
                    {"message": "Parol muvaffaqiyatli yangilandi."}, 
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                import traceback
                return Response(
                    {"detail": "Vay! Serverda qandaydir kutilmagan blok xatosi.", "error": str(e), "trace": traceback.format_exc()}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenRefreshView(APIView):
    """Refresh the access token using the refresh cookie."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Refresh Token",
        description="Read the refresh_token cookie and return a fresh access_token cookie.",
        responses={200: OpenApiResponse(description="Token refreshed"), 401: OpenApiResponse(description="Invalid or missing refresh token")},
    )
    def post(self, request):
        jwt_cfg = settings.SIMPLE_JWT
        # Try finding token in cookies first, then in the request body
        raw_refresh = request.COOKIES.get(
            jwt_cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        ) or request.data.get("refreshToken") or request.data.get("refresh")

        if not raw_refresh:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw_refresh)
            
            # Add role to refreshed token as well
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=refresh['user_id'])
                refresh['role'] = user.profile.role
            except Exception:
                pass

            data = {
                "detail": "Token refreshed.",
                "accessToken": str(refresh.access_token),
                "refreshToken": str(refresh)
            }
            response = Response(data)
            return _set_auth_cookies(response, refresh)
        except Exception:
            return Response(
                {"detail": "Invalid refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class LogoutView(APIView):
    """Clear JWT cookies."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout",
        description="Clear HttpOnly JWT cookies.",
        responses={200: OpenApiResponse(description="Logged out")},
    )
    def post(self, request):
        response = Response({"detail": "Logged out."})
        return _clear_auth_cookies(response)


class MeView(generics.RetrieveUpdateAPIView):
    """Get or update the currently authenticated user profile."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    @extend_schema(summary="Get Current User", responses={200: UserSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Update Current User Profile", request=UserUpdateSerializer, responses={200: UserSerializer})
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Current User Profile", request=UserUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

class PasswordChangeView(generics.GenericAPIView):
    """Change the password for the current user."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer
    
    @extend_schema(
        summary="Change Password (Profile)",
        description="Profil sahifasidan parol almashtirish. Eski parol, yangi parol va tasdiqlash talab qilinadi.",
        request=PasswordChangeSerializer,
        responses={
            200: OpenApiResponse(description="Parol muvaffaqiyatli almashtirildi"),
            400: OpenApiResponse(description="Validatsiya xatosi (eski parol noto'g'ri, parollar mos kelmadi, va h.k.)"),
        },
        tags=["auth"]
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data.get("old_password")):
            return Response({"old_password": ["Eski parol noto'g'ri."]}, status=status.HTTP_400_BAD_REQUEST)
            
        user.set_password(serializer.validated_data.get("new_password"))
        user.save()
        
        return Response({"detail": "Parol muvaffaqiyatli almashtirildi."}, status=status.HTTP_200_OK)

class TeamManagementViewSet(viewsets.ModelViewSet):
    """Admin/PM operatsiyalari — foydalanuvchilarni boshqarish."""
    
    permission_classes = [IsAuthenticated, IsPM]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        """Action'ga qarab faol yoki bloklangan user'larni qaytaradi."""
        base_qs = (
            User.objects.filter(profile__role='USER')
            .exclude(is_superuser=True)
            .exclude(id=self.request.user.id)
            .select_related("profile")
            .order_by("-date_joined")
        )
        # restore va permanent-delete uchun bloklangan user'larni ham ko'rsatish
        if self.action in ["restore", "permanent_delete", "blocked"]:
            return base_qs
        # Asosiy ro'yxat — faqat faol user'lar
        return base_qs.filter(is_active=True)

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return EmployeeUpdateSerializer
        elif self.action == "retrieve":
            return EmployeeDetailSerializer
        return EmployeeSerializer

    @extend_schema(summary="Faol xodimlar ro'yxati (PM Only)")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Yangi xodim qo'shish (PM Only)")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Xodim ma'lumotlari (PM Only)",
        responses={200: EmployeeDetailSerializer}
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Xodimni tahrirlash (PM Only)")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Xodimni qisman tahrirlash (PM Only)")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Xodimni bloklash (PM Only)",
        description="Xodimni o'chirmaydi, faqat is_active=False qiladi."
    )
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response(
            {"detail": "Xodim bloklandi."},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Bloklangan xodimlar ro'yxati (PM Only)",
        responses={200: EmployeeSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="blocked")
    def blocked(self, request):
        """Bloklangan (is_active=False) USER'lar ro'yxati."""
        blocked_users = (
            User.objects.filter(profile__role='USER', is_active=False)
            .exclude(is_superuser=True)
            .exclude(id=request.user.id)
            .select_related("profile")
            .order_by("-date_joined")
        )
        serializer = EmployeeSerializer(blocked_users, many=True, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Xodimni qayta faollashtirish (PM Only)",
        responses={200: EmployeeSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="restore")
    def restore(self, request, pk=None):
        """Bloklangan xodimni qayta faollashtiradi (is_active=True)."""
        user = self.get_object()
        user.is_active = True
        user.save()
        serializer = EmployeeSerializer(user, context={"request": request})
        return Response(serializer.data)

    @extend_schema(
        summary="Xodimni butunlay o'chirish (PM Only)",
        description="Xodimni bazadan butunlay o'chiradi. Bu amalni qaytarib bo'lmaydi!",
    )
    @action(detail=True, methods=["delete"], url_path="permanent-delete")
    def permanent_delete(self, request, pk=None):
        """Xodimni bazadan butunlay o'chiradi."""
        user = self.get_object()
        user.delete()
        return Response(
            {"detail": "Xodim butunlay o'chirildi."},
            status=status.HTTP_204_NO_CONTENT
        )



class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD for projects + dashboard analytics + member management."""

    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Project.objects.filter(Q(owner=user) | Q(members=user))
            .distinct()
            .select_related("owner")
            .prefetch_related("members")
        )

    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user)
        project.members.add(self.request.user)

    @extend_schema(summary="List Projects")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create Project")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get Project")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update Project")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Project")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete Project")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


    @extend_schema(
        summary="Project Dashboard",
        description="Analytics: task counts by status/priority, progress percentage.",
        responses={200: DashboardSerializer},
    )
    @action(detail=True, methods=["get"], url_path="dashboard")
    def dashboard(self, request, pk=None):
        project = self.get_object()
        tasks = project.tasks.all()
        total = tasks.count()
        completed = tasks.filter(status=Task.Status.DONE).count()
        in_progress = tasks.filter(status=Task.Status.IN_PROGRESS).count()
        review = tasks.filter(status=Task.Status.REVIEW).count()
        todo = tasks.filter(status=Task.Status.TODO).count()
        approved = tasks.filter(is_approved=True).count()

        by_priority = {}
        for choice_val, choice_label in Task.Priority.choices:
            by_priority[choice_val] = tasks.filter(priority=choice_val).count()

        recent = tasks.order_by("-created_at")[:5]

        data = {
            "total_tasks": total,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "review_tasks": review,
            "todo_tasks": todo,
            "approved_tasks": approved,
            "progress_percentage": round((completed / total) * 100, 2) if total else 0.0,
            "tasks_by_priority": by_priority,
            "recent_tasks": TaskSerializer(recent, many=True).data,
        }
        return Response(DashboardSerializer(data).data)


    @extend_schema(
        summary="List Project Members",
        responses={200: UserSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="members")
    def list_members(self, request, pk=None):
        project = self.get_object()
        members = project.members.all()
        return Response(UserSerializer(members, many=True).data)

    @extend_schema(
        summary="Add Project Members",
        description="Add users to the project by IDs.",
        request=ProjectMemberSerializer,
        responses={200: UserSerializer(many=True)},
    )
    @action(detail=True, methods=["post"], url_path="members/add")
    def add_members(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        users = User.objects.filter(id__in=serializer.validated_data["user_ids"])
        project.members.add(*users)
        return Response(UserSerializer(project.members.all(), many=True).data)

    @extend_schema(
        summary="Remove Project Members",
        description="Remove users from the project by IDs.",
        request=ProjectMemberSerializer,
        responses={200: UserSerializer(many=True)},
    )
    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_members(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        users = User.objects.filter(id__in=serializer.validated_data["user_ids"])
        project.members.remove(*users)
        return Response(UserSerializer(project.members.all(), many=True).data)


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD for tasks + Kanban move + approve actions."""

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Task.objects.filter(
                Q(project__owner=user) | Q(project__members=user)
            )
            .distinct()
            .select_related("project", "assignee", "created_by")
        )
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        task_status = self.request.query_params.get("status")
        if task_status:
            qs = qs.filter(status=task_status)
        assignee = self.request.query_params.get("assignee")
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        return qs

    def perform_create(self, serializer):
        project = serializer.validated_data.get('project')
        if project.owner != self.request.user and not project.members.filter(id=self.request.user.id).exists():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You are not a member of this project.")
        serializer.save(created_by=self.request.user)

    @extend_schema(summary="List Tasks", description="Filterable by `project`, `status`, `assignee` query params.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create Task")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get Task")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update Task")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Task")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete Task")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


    @extend_schema(
        summary="Move Task (Kanban)",
        description="Change the task status. Triggers a `task_moved` WebSocket event.",
        request=TaskMoveSerializer,
        responses={200: TaskSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="move")
    def move(self, request, pk=None):
        task = self.get_object()
        serializer = TaskMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task.status = serializer.validated_data["status"]
        task.save()  
        return Response(TaskSerializer(task).data)


    @extend_schema(
        summary="Approve Task",
        description="Approve a completed task. Triggers a `notification_received` WebSocket event.",
        request=TaskApproveSerializer,
        responses={200: TaskSerializer},
    )
    @action(detail=True, methods=["patch"], url_path="approve")
    def approve(self, request, pk=None):
        task = self.get_object()
        if task.status != Task.Status.DONE:
            return Response(
                {"detail": "Only tasks with status DONE can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TaskApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task.is_approved = serializer.validated_data["is_approved"]
        task.save()  
        return Response(TaskSerializer(task).data)


class ChannelViewSet(viewsets.ModelViewSet):
    """CRUD for chat channels + nested messages endpoint."""

    serializer_class = ChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Channel.objects.filter(
                Q(project__owner=user) | Q(project__members=user)
            )
            .distinct()
            .select_related("project")
            .prefetch_related("members")
        )
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @extend_schema(summary="List Channels", description="Filterable by `project` query param.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Create Channel")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Get Channel")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Update Channel")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Channel")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(summary="Delete Channel")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


    @extend_schema(
        summary="List Channel Messages",
        responses={200: MessageSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="messages")
    def list_messages(self, request, pk=None):
        channel = self.get_object()
        messages = channel.messages.select_related("sender").all()

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = MessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Send Message to Channel",
        description="Create a new message in this channel (also broadcast via WebSocket).",
        request=MessageSerializer,
        responses={201: MessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="messages/send")
    def send_message(self, request, pk=None):
        channel = self.get_object()
        serializer = MessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(sender=request.user, channel=channel)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class FeedbackViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Anonymous feedback.
    """

    serializer_class = FeedbackSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Feedback.objects.select_related("project").all()
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @extend_schema(
        summary="Submit Feedback",
        description="Feedback yuborish. `is_anonymous: true` bo'lsa anonim, `false` bo'lsa foydalanuvchi ma'lumotlari saqlanadi.",
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Agar foydalanuvchi login qilgan va anonim emas bo'lsa — userni saqlaymiz
        user = None
        if request.user and request.user.is_authenticated and not serializer.validated_data.get("is_anonymous", True):
            user = request.user

        serializer.save(user=user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="List Feedback",
        description="Filterable by `project` query param. Requires authentication.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Get Feedback")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

class GlobalSearchView(APIView):
    """
    Search across Tasks, Projects, and Users via a single endpoint.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Global Search",
        description="Search through Tasks, Projects, and Users based on keyword 'q'. If q is empty or not provided, returns empty arrays.",
        parameters=[
            OpenApiParameter(name="q", description="Search keyword", required=False, type=str),
        ],
        responses={200: GlobalSearchResponseSerializer}
    )
    def get(self, request, *args, **kwargs):
        q = request.query_params.get("q", "").strip()
        
        if not q:
            return Response({"tasks": [], "projects": [], "users": []})
            
        user = request.user
        
        # 1. Tasks: belongs to user's project, filtered by title/desc
        tasks_qs = Task.objects.filter(
            Q(project__owner=user) | Q(project__members=user),
            Q(title__icontains=q) | Q(description__icontains=q)
        ).distinct()
        
        # 2. Projects: belongs to user, filtered by name/desc
        projects_qs = Project.objects.filter(
            Q(owner=user) | Q(members=user),
            Q(name__icontains=q) | Q(description__icontains=q)
        ).distinct()
        
        # 3. Users: all users, filtered by name/phone/profession
        users_qs = User.objects.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(profile__phone_number__icontains=q) |
            Q(profile__profession__icontains=q)
        ).distinct()
        
        from .serializers import SearchTaskSerializer, SearchProjectSerializer, SearchUserSerializer
        
        return Response({
            "tasks": SearchTaskSerializer(tasks_qs, many=True).data,
            "projects": SearchProjectSerializer(projects_qs, many=True).data,
            "users": SearchUserSerializer(users_qs, many=True).data
        })

class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    CRUD for User Notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")

    @extend_schema(summary="List Notifications", description="Get all notifications for the current user.")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Mark Notification as Read",
        description="Mark a single notification as read.",
        responses={200: NotificationSerializer}
    )
    @action(detail=True, methods=["patch"], url_path="read")
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response(self.get_serializer(notification).data)

    @extend_schema(
        summary="Mark All Notifications as Read",
        description="Mark all unread notifications for current user as read.",
        responses={200: OpenApiResponse(description="All notifications marked as read")}
    )
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"detail": "Barcha xabarlar o'qilgan deb belgilandi."}, status=status.HTTP_200_OK)

class DocumentViewSet(viewsets.ModelViewSet):
    """
    PM'lar uchun hujjatlarni (TZ, eslatmalar) boshqarish API'si.
    """
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsPM]

    def get_queryset(self):
        user = self.request.user
        # PM o'zi yaratgan yoki o'zi a'zo bo'lgan loyihalardagi hujjatlarni ko'ra oladi
        return Document.objects.filter(
            Q(created_by=user) | Q(project__owner=user) | Q(project__members=user)
        ).distinct().select_related("project", "created_by").order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(summary="PM hujjatlar ro'yxati (Faqat PM)")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Hujjat yaratish (Faqat PM)")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(summary="Hujjatni o'chirish (Faqat PM)")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


