from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Project, Task, Channel, Message, Feedback

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

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

