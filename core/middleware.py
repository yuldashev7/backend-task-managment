import os
import jwt
from urllib.parse import parse_qs
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

User = get_user_model()

@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers", []))
        token = None

        if b"cookie" in headers:
            cookies = headers[b"cookie"].decode("utf-8").split("; ")
            for cookie in cookies:
                if cookie.startswith("access_token="):
                    token = cookie.split("=")[1]
                    break

        if not token:
            query_string = scope.get("query_string", b"").decode("utf-8")
            query_params = parse_qs(query_string)
            if "token" in query_params:
                token = query_params["token"][0]

        if token:
            try:
                from rest_framework_simplejwt.settings import api_settings
                from rest_framework_simplejwt.tokens import AccessToken
                
                access_token = AccessToken(token)
                user_id = access_token.get(api_settings.USER_ID_CLAIM)
                scope["user"] = await get_user(user_id)
            except Exception:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
