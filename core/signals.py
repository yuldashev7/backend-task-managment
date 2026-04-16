from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Task, Message, Notification, Feedback

@receiver(pre_save, sender=Task)
def task_pre_save(sender, instance, **kwargs):
    if instance.pk:
        old_instance = Task.objects.get(pk=instance.pk)
        instance._old_status = old_instance.status
        instance._old_is_approved = old_instance.is_approved
        instance._old_assignee = old_instance.assignee
    else:
        instance._old_status = None
        instance._old_is_approved = None
        instance._old_assignee = None

@receiver(post_save, sender=Task)
def task_post_save(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    group_name = f"project_{instance.project_id}"

    if getattr(instance, "_old_status", None) != instance.status:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "task_moved",
                "task_id": instance.id,
                "status": instance.status,
            }
        )

    if getattr(instance, "_old_is_approved", None) != instance.is_approved and instance.is_approved:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notification_received",
                "message": f"Task {instance.title} approved!"
            }
        )

    if getattr(instance, "_old_assignee", None) != instance.assignee and instance.assignee:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notification_received",
                "message": f"Task {instance.title} assigned to {instance.assignee.username}"
            }
        )

    # Database Notifications for Assignee
    if created and instance.assignee:
        Notification.objects.create(
            user=instance.assignee,
            title="Yangi vazifa",
            message=f"Sizga yangi vazifa biriktirildi: {instance.title}",
            notification_type="TASK_ASSIGNED"
        )
    elif not created:
        old_assignee = getattr(instance, "_old_assignee", None)
        if old_assignee != instance.assignee and instance.assignee:
            Notification.objects.create(
                user=instance.assignee,
                title="Yangi vazifa",
                message=f"Sizga yangi vazifa biriktirildi: {instance.title}",
                notification_type="TASK_ASSIGNED"
            )

        old_status = getattr(instance, "_old_status", None)
        if old_status != instance.status:
            if instance.assignee:
                Notification.objects.create(
                    user=instance.assignee,
                    title="Vazifa holati o'zgardi",
                    message=f"Vazifangiz holati o'zgardi: {instance.title} -> {instance.status}",
                    notification_type="STATUS_UPDATED"
                )
            
            if instance.status in [Task.Status.REVIEW, Task.Status.DONE]:
                Notification.objects.create(
                    user=instance.project.owner,
                    title="Vazifa tekshirish uchun yuborildi",
                    message=f"Xodim {instance.assignee.first_name if instance.assignee else 'Noma`lum'} '{instance.title}' vazifasini tekshirish uchun yubordi",
                    notification_type="NEEDS_REVIEW"
                )


@receiver(post_save, sender=Message)
def message_post_save(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        group_name = f"channel_{instance.channel_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "chat_message",
                "message_id": instance.id,
                "content": instance.content,
                "sender": instance.sender.username,
            }
        )

@receiver(post_save, sender=Feedback)
def feedback_post_save(sender, instance, created, **kwargs):
    if created and instance.project and instance.project.owner:
        Notification.objects.create(
            user=instance.project.owner,
            title="Yangi fikr/izoh",
            message=f"Loyiha doirasida yangi fikr qoldirildi: {instance.content[:50]}...",
            notification_type="NEW_FEEDBACK"
        )
