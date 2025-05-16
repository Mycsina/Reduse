import uuid
from typing import Optional

from beanie import PydanticObjectId
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users_db_beanie import ObjectIDIDMixin
from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2

from backend.config import settings
from backend.db import get_user_db
from backend.schemas.users import User

google_oauth_client = GoogleOAuth2("CLIENT_ID", "CLIENT_SECRET")
github_oauth_client = GitHubOAuth2("CLIENT_ID", "CLIENT_SECRET")

from logging import getLogger

logger = getLogger(__name__)


class UserManager(ObjectIDIDMixin, BaseUserManager[User, PydanticObjectId]):
    reset_password_token_secret = settings.AUTH_SECRET_KEY
    verification_token_secret = settings.AUTH_SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: User, token: str, request: Optional[Request] = None):
        logger.info(f"User {user.id} has forgot their password. Reset token: {token}")
        # Add email sending logic here

    async def on_after_request_verify(self, user: User, token: str, request: Optional[Request] = None):
        logger.info(f"Verification requested for user {user.id}. Verification token: {token}")
        # Add email sending logic here


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


cookie_transport = CookieTransport(cookie_name="reduseauth", cookie_max_age=3600, cookie_secure=False)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.AUTH_SECRET_KEY, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, PydanticObjectId](
    get_user_manager,
    [auth_backend],
)

# Define dependencies for route protection
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
