from datetime import datetime
from typing import List

from beanie import Document, PydanticObjectId
from fastapi_users.db import BeanieBaseUser
from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from fastapi_users_db_beanie import BaseOAuthAccount, ObjectIDIDMixin
from pydantic import Field


class OAuthAccount(BaseOAuthAccount):
    pass


class User(BeanieBaseUser, Document):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    oauth_accounts: List[OAuthAccount] = Field(default_factory=list)

    class Settings(BeanieBaseUser.Settings):
        name = "users"


class UserRead(BaseUser[PydanticObjectId]):
    pass


class UserCreate(BaseUserCreate):
    pass


class UserUpdate(BaseUserUpdate):
    pass
