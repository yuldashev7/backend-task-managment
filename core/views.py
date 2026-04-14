"""
DRF views / ViewSets for the Task Management System.

Every endpoint is documented with ``@extend_schema`` for drf-spectacular.
"""

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Channel, Feedback, Message, Project, Task
from .permissions import IsProjectMember
from .serializers import (
    ChannelSerializer,
    DashboardSerializer,
    FeedbackSerializer,
    LoginSerializer,
    MessageSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    RegisterSerializer,
    TaskApproveSerializer,
    TaskMoveSerializer,
    TaskSerializer,
    UserSerializer,
    UserUpdateSerializer,
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
        response = Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
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
        response = Response(UserSerializer(user).data)
        return _set_auth_cookies(response, refresh)


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
        raw_refresh = request.COOKIES.get(
            jwt_cfg.get("AUTH_COOKIE_REFRESH", "refresh_token")
        )
        if not raw_refresh:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw_refresh)
            response = Response({"detail": "Token refreshed."})
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
    """Get or update the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    @extend_schema(summary="Get Current User", responses={200: UserSerializer})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(summary="Update Current User", request=UserUpdateSerializer, responses={200: UserSerializer})
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(summary="Partial Update Current User", request=UserUpdateSerializer, responses={200: UserSerializer})
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


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
        summary="Submit Anonymous Feedback",
        description="No authentication required. User identity is not stored.",
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="List Feedback",
        description="Filterable by `project` query param. Requires authentication.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Get Feedback")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
