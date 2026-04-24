from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.core.cache import cache
from .models import Profile, Project, Task, Channel, Message, Feedback, Notification, Document

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    profession = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    bg_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone_number", "avatar", "bg_image", "role", "profession", "gender", "is_active")

    def _get_profile(self, obj):
        return getattr(obj, 'profile', None)

    def get_phone_number(self, obj):
        profile = self._get_profile(obj)
        return profile.phone_number if profile else None

    def get_role(self, obj):
        profile = self._get_profile(obj)
        return profile.role if profile else 'USER'

    def get_profession(self, obj):
        profile = self._get_profile(obj)
        return profile.profession if profile else None

    def get_gender(self, obj):
        profile = self._get_profile(obj)
        return profile.gender if profile else None

    def get_bg_image(self, obj):
        request = self.context.get('request')
        profile = self._get_profile(obj)
        if profile and profile.bg_image:
            if request:
                return request.build_absolute_uri(profile.bg_image.url)
            return profile.bg_image.url
        return None

    def get_avatar(self, obj):
        request = self.context.get('request')
        profile = self._get_profile(obj)
        
        if not profile:
            return None

        if profile.avatar:
            if request:
                return request.build_absolute_uri(profile.avatar.url)
            return profile.avatar.url

        if profile.gender == 'male':
            return 'default_male'
        elif profile.gender == 'female':
            return 'default_female'

        return None

class UserUpdateSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True)
    bg_image = serializers.ImageField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=['male', 'female'], required=False, allow_null=True)
    old_password = serializers.CharField(required=False, write_only=True, allow_blank=True)
    new_password = serializers.CharField(required=False, write_only=True, allow_blank=True, min_length=6)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone_number", "avatar", "bg_image", "gender", "old_password", "new_password")

    def validate(self, data):
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if new_password and not old_password:
            raise serializers.ValidationError({"old_password": "Yangi parol o'rnatish uchun eski parolni kiriting."})

        if old_password and new_password:
            user = self.instance
            if not user.check_password(old_password):
                raise serializers.ValidationError({"old_password": "Eski parol noto'g'ri."})

        return data

    def update(self, instance, validated_data):
        phone_number = validated_data.pop('phone_number', None)
        avatar = validated_data.pop('avatar', None)
        bg_image = validated_data.pop('bg_image', None)
        gender = validated_data.pop('gender', None)
        old_password = validated_data.pop('old_password', None)
        new_password = validated_data.pop('new_password', None)

        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)

        if old_password and new_password:
            instance.set_password(new_password)

        instance.save()

        profile, created = Profile.objects.get_or_create(user=instance)
        if phone_number is not None:
            profile.phone_number = phone_number
        if gender is not None:
            profile.gender = gender
        
        # Rasm yangilash mantiqi: agar yangi fayl berilsa yangilaymiz, 
        # agar null kelsa o'chiramiz (agar oldin bo'lsa)
        if bg_image is not None and not isinstance(bg_image, str):
            profile.bg_image = bg_image
        elif 'bg_image' in self.initial_data and self.initial_data['bg_image'] is None:
            profile.bg_image = None
            
        if avatar is not None and not isinstance(avatar, str):
            profile.avatar = avatar
        elif 'avatar' in self.initial_data and self.initial_data['avatar'] is None:
            profile.avatar = None
            
        profile.save()

        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate(self, data):
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Parollar mos kelmadi."})
        if data.get('old_password') == data.get('new_password'):
            raise serializers.ValidationError({"new_password": "Yangi parol eski paroldan farqli bo'lishi kerak."})
        return data


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

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)

    def validate(self, data):
        email = data.get('email')
        code = data.get('code')
        
        cached_code = cache.get(f"password_reset_{email}")
        
        if not cached_code or str(cached_code) != str(code):
            raise serializers.ValidationError({"code": "Kod noto'g'ri yoki muddati o'tgan."})
            
        return data

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        email = data.get('email')
        code = data.get('code')
        
        cached_code = cache.get(f"password_reset_{email}")
        
        if not cached_code or str(cached_code) != str(code):
            raise serializers.ValidationError({"code": "Kod noto'g'ri yoki muddati o'tgan."})
            
        if data.get('new_password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Parollar afsuski mos kelmadi."})
            
        return data


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
    user = UserSerializer(read_only=True)
    is_anonymous = serializers.BooleanField(default=True)

    class Meta:
        model = Feedback
        fields = ("id", "user", "content", "project", "is_anonymous", "created_at")
        read_only_fields = ("user", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Agar anonim bo'lsa, user ma'lumotlarini yashirish
        if instance.is_anonymous:
            data["user"] = None
        return data

class EmployeeSerializer(serializers.ModelSerializer):
    phone_number = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    profession = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    bg_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "is_active", "phone_number", "avatar", "bg_image", "role", "profession", "gender")

    def _get_profile(self, obj):
        return getattr(obj, 'profile', None)

    def get_phone_number(self, obj):
        profile = self._get_profile(obj)
        return profile.phone_number if profile else None

    def get_role(self, obj):
        profile = self._get_profile(obj)
        return profile.role if profile else 'USER'

    def get_profession(self, obj):
        profile = self._get_profile(obj)
        return profile.profession if profile else None

    def get_gender(self, obj):
        profile = self._get_profile(obj)
        return profile.gender if profile else None

    def get_bg_image(self, obj):
        request = self.context.get('request')
        profile = self._get_profile(obj)
        if profile and profile.bg_image:
            if request:
                return request.build_absolute_uri(profile.bg_image.url)
            return profile.bg_image.url
        return None

    def get_avatar(self, obj):
        request = self.context.get('request')
        profile = self._get_profile(obj)
        
        if not profile:
            return None
            
        if profile.avatar:
            if request:
                return request.build_absolute_uri(profile.avatar.url)
            return profile.avatar.url
        if profile.gender == 'male':
            return 'default_male'
        elif profile.gender == 'female':
            return 'default_female'
        return None

from drf_spectacular.utils import extend_schema_field

class EmployeeTaskSerializer(serializers.ModelSerializer):
    """Xodimga berilgan task'ning qisqacha ma'lumoti."""
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = Task
        fields = ("id", "title", "status", "priority", "deadline", "project_name", "created_at")

class EmployeeDetailSerializer(EmployeeSerializer):
    tasks = serializers.SerializerMethodField()

    class Meta(EmployeeSerializer.Meta):
        fields = EmployeeSerializer.Meta.fields + ("tasks",)

    @extend_schema_field(EmployeeTaskSerializer(many=True))
    def get_tasks(self, obj):
        tasks = obj.assigned_tasks.select_related("project").order_by("-created_at")
        return EmployeeTaskSerializer(tasks, many=True).data

class EmployeeCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    profession = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    avatar = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "profession", "phone_number", "avatar")

    def create(self, validated_data):
        profession = validated_data.pop('profession', '')
        phone_number = validated_data.pop('phone_number', '')
        avatar = validated_data.pop('avatar', None)

        user = User.objects.create_user(**validated_data)
        profile = user.profile
        profile.role = 'USER'
        profile.profession = profession
        profile.phone_number = phone_number
        if avatar and not isinstance(avatar, str):
            profile.avatar = avatar
        profile.save()
        return user

class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """PM faqat USER'larni tahrirlashi mumkin. Role o'zgartirish imkoniyati yo'q."""
    profession = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)
    avatar = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = ("is_active", "profession", "avatar")

    def update(self, instance, validated_data):
        profession = validated_data.pop('profession', None)
        avatar = validated_data.pop('avatar', None)
        
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
            instance.save()
            
        profile, created = Profile.objects.get_or_create(user=instance)
        if profession is not None:
            profile.profession = profession
        if avatar is not None and not isinstance(avatar, str):
            profile.avatar = avatar
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
    avatar = serializers.ImageField(source='profile.avatar', read_only=True)

    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "profession", "avatar")

class GlobalSearchResponseSerializer(serializers.Serializer):
    tasks = SearchTaskSerializer(many=True)
    projects = SearchProjectSerializer(many=True)
    users = SearchUserSerializer(many=True)

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"

class DocumentSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Document
        fields = "__all__"
