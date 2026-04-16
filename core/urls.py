from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"projects", views.ProjectViewSet, basename="project")
router.register(r"tasks", views.TaskViewSet, basename="task")
router.register(r"channels", views.ChannelViewSet, basename="channel")
router.register(r"feedback", views.FeedbackViewSet, basename="feedback")
router.register(r"admin/users", views.TeamManagementViewSet, basename="admin-users")
router.register(r"notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/forgot-password/", views.ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/reset-password/", views.ResetPasswordView.as_view(), name="auth-reset-password"),
    path("auth/refresh/", views.TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("users/me/", views.MeView.as_view(), name="users-me"),
    path("users/me/change-password/", views.PasswordChangeView.as_view(), name="users-change-password"),
    path("search/", views.GlobalSearchView.as_view(), name="global-search"),
    path("", include(router.urls)),
]
