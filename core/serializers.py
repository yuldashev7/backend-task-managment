from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Project, Task, Channel, Message, Feedback, Notification

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)
    avatar_url = serializers.URLField(source='profile.avatar_url', read_only=True)
    role = serializers.CharField(source='profile.role', read_only=True)
    profession = serializers.CharField(source='profile.profession', read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "avatar_url", "role", "profession", "is_active")

class UserUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='profile.phone_number', required=False)
    avatar_url = serializers.URLField(source='profile.avatar_url', required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone_number", "avatar_url")
        
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()

        profile = instance.profile
        profile.phone_number = profile_data.get('phone_number', profile.phone_number)
        profile.avatar_url = profile_data.get('avatar_url', profile.avatar_url)
        profile.save()

        return instance

class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "password", "email", "first_name", "last_name")

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class GoogleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)


class ProjectMemberSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField())


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ("id", "name", "description", "owner", "members", "created_at", "updated_at")


class TaskSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Task
        fields = "__all__"

    def validate(self, data):
        project = data.get('project')
        assignee = data.get('assignee')
        
        if project and assignee:
            if assignee != project.owner and not project.members.filter(id=assignee.id).exists():
                raise serializers.ValidationError({"assignee": "Assignee must be a member of the project."})
        
        return data

class TaskMoveSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Task.Status.choices)

class TaskApproveSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()

class ChannelSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Channel
        fields = "__all__"

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    channel = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Message
        fields = "__all__"

class DashboardSerializer(serializers.Serializer):
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    in_progress_tasks = serializers.IntegerField()
    review_tasks = serializers.IntegerField()
    todo_tasks = serializers.IntegerField()
    approved_tasks = serializers.IntegerField()
    progress_percentage = serializers.FloatField()
    tasks_by_priority = serializers.DictField(child=serializers.IntegerField())
    recent_tasks = TaskSerializer(many=True)

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"

class EmployeeSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='profile.phone_number', read_only=True)
    avatar_url = serializers.URLField(source='profile.avatar_url', read_only=True)
    role = serializers.CharField(source='profile.role', read_only=True)
    profession = serializers.CharField(source='profile.profession', read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "is_active", "phone_number", "avatar_url", "role", "profession")

class EmployeeCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['PM', 'USER'], required=False)
    profession = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "role", "profession", "phone_number")

    def create(self, validated_data):
        role = validated_data.pop('role', 'USER')
        profession = validated_data.pop('profession', '')
        phone_number = validated_data.pop('phone_number', '')

        user = User.objects.create_user(**validated_data)
        profile = user.profile
        profile.role = role
        profile.profession = profession
        profile.phone_number = phone_number
        profile.save()
        return user

class EmployeeUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=['PM', 'USER'], required=False)
    profession = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = User
        fields = ("is_active", "role", "profession")

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        profession = validated_data.pop('profession', None)
        
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
            instance.save()
            
        profile = instance.profile
        if role is not None:
            profile.role = role
        if profession is not None:
            profile.profession = profession
        profile.save()
        return instance

class SearchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "status")

class SearchProjectSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='name')
    status = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ("id", "title", "status")
        
    def get_status(self, obj):
        return "ACTIVE"

class SearchUserSerializer(serializers.ModelSerializer):
    profession = serializers.CharField(source='profile.profession', read_only=True)
    avatar_url = serializers.URLField(source='profile.avatar_url', read_only=True)

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "profession", "avatar_url")

class GlobalSearchResponseSerializer(serializers.Serializer):
    tasks = SearchTaskSerializer(many=True)
    projects = SearchProjectSerializer(many=True)
    users = SearchUserSerializer(many=True)

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

