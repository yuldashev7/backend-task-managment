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
router.register(r"documents", views.DocumentViewSet, basename="document")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/register", views.RegisterView.as_view()),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/login", views.LoginView.as_view()),
    path("auth/google/", views.GoogleLoginView.as_view(), name="auth-google"),
    path("auth/google", views.GoogleLoginView.as_view()),
    path("auth/forgot-password/", views.ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/forgot-password", views.ForgotPasswordView.as_view()),
    path("auth/verify-otp/", views.VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("auth/verify-otp", views.VerifyOTPView.as_view()),
    path("auth/reset-password/", views.ResetPasswordView.as_view(), name="auth-reset-password"),
    path("auth/reset-password", views.ResetPasswordView.as_view()),
    path("auth/refresh/", views.TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/refresh", views.TokenRefreshView.as_view()),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("auth/me", views.MeView.as_view()),
    path("users/me/", views.MeView.as_view(), name="users-me"),
    path("users/me", views.MeView.as_view()),
    path("users/me/change-password/", views.PasswordChangeView.as_view(), name="users-change-password"),
    path("search/", views.GlobalSearchView.as_view(), name="global-search"),
    path("", include(router.urls)),
]
