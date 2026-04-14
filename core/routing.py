from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/projects/(?P<project_id>\d+)/$", consumers.ProjectConsumer.as_asgi()),
    re_path(r"ws/channels/(?P<channel_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
]
