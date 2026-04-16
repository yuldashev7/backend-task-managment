from rest_framework import permissions
from .models import Project

class IsProjectMember(permissions.BasePermission):
    """
    Ruxsatnoma: Foydalanuvchi loyiha egasi yoki a'zosi ekanligini tekshiradi.
    """
    def has_object_permission(self, request, view, obj):
        # Agar obyekt Project bo'lsa
        if isinstance(obj, Project):
            return request.user == obj.owner or obj.members.filter(id=request.user.id).exists()
        
        # Agar obyekt Task yoki Channel bo'lsa (ularning project'i bor)
        if hasattr(obj, 'project'):
            return request.user == obj.project.owner or obj.project.members.filter(id=request.user.id).exists()
            
        return False

class IsPM(permissions.BasePermission):
    """
    Ruxsatnoma: Foydalanuvchi faqat PM (Project Manager) rolida bo'lsa ruxsat beradi.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.role == 'PM'
        )
