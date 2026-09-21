from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from dicehub.api_keys._validation import MAX_ID_LENGTH, MAX_NAME_LENGTH, MAX_SECRET_LENGTH


class NamespacePermission(str, Enum):
    NONE = "NONE"
    VIEW_TEAM_INFO = "VIEW_TEAM_INFO"
    VIEW_GROUP_INFO = "VIEW_GROUP_INFO"
    VIEW_PROJECT_INFO = "VIEW_PROJECT_INFO"
    CREATE_SUBGROUP = "CREATE_SUBGROUP"
    CREATE_PROJECT = "CREATE_PROJECT"
    DELETE_GROUP = "DELETE_GROUP"
    MANAGE_GROUP_MEMBERS = "MANAGE_GROUP_MEMBERS"
    CREATE_TEAM = "CREATE_TEAM"
    EDIT_GROUP_INFO = "EDIT_GROUP_INFO"
    VIEW_GROUP_ACTIVITIES = "VIEW_GROUP_ACTIVITIES"
    VIEW_APP_INFO = "VIEW_APP_INFO"
    CREATE_APP = "CREATE_APP"
    DELETE_PROJECT = "DELETE_PROJECT"
    VIEW_PROJECT_ACTIVITIES = "VIEW_PROJECT_ACTIVITIES"
    MANAGE_PROJECT_MEMBERS = "MANAGE_PROJECT_MEMBERS"
    EDIT_PROJECT_INFO = "EDIT_PROJECT_INFO"
    EDIT_APP = "EDIT_APP"
    VIEW_RUN = "VIEW_RUN"
    EDIT_RUN = "EDIT_RUN"
    DELETE_APP = "DELETE_APP"
    EDIT_APP_INFO = "EDIT_APP_INFO"
    VIEW_USER_PROFILE = "VIEW_USER_PROFILE"
    EDIT_USER_PROFILE = "EDIT_USER_PROFILE"
    CREATE_USER_PROJECT = "CREATE_USER_PROJECT"
    MANAGE_TEAM_MEMBERS = "MANAGE_TEAM_MEMBERS"
    DELETE_TEAM = "DELETE_TEAM"
    CREATE_USER = "CREATE_USER"
    CREATE_GROUP = "CREATE_GROUP"
    MANAGE_APP_TEMPLATES = "MANAGE_APP_TEMPLATES"
    LIST_USERS = "LIST_USERS"
    LIST_USER_LINKED_ACCOUNTS = "LIST_USER_LINKED_ACCOUNTS"
    EDIT_TEAM_PROFILE = "EDIT_TEAM_PROFILE"
    MANAGE_ADMIN_MEMBERS = "MANAGE_ADMIN_MEMBERS"
    SHARE_APP = "SHARE_APP"
    BLOCK_USER = "BLOCK_USER"
    DELETE_USER_BY_ADMIN = "DELETE_USER_BY_ADMIN"
    DELETE_USER_BY_USER = "DELETE_USER_BY_USER"
    LIST_USER_EMAILS = "LIST_USER_EMAILS"
    VIEW_APP_TEMPLATE = "VIEW_APP_TEMPLATE"
    VIEW_PUBLIC_GROUP_MEMBERS = "VIEW_PUBLIC_GROUP_MEMBERS"
    VIEW_PRIVATE_GROUP_MEMBERS = "VIEW_PRIVATE_GROUP_MEMBERS"
    VIEW_PUBLIC_PROJECT_MEMBERS = "VIEW_PUBLIC_PROJECT_MEMBERS"
    VIEW_PRIVATE_PROJECT_MEMBERS = "VIEW_PRIVATE_PROJECT_MEMBERS"
    VIEW_PUBLIC_TEAM_MEMBERS = "VIEW_PUBLIC_TEAM_MEMBERS"
    VIEW_PRIVATE_TEAM_MEMBERS = "VIEW_PRIVATE_TEAM_MEMBERS"
    MANAGE_BILLING = "MANAGE_BILLING"
    WRITE_APP_STORAGE = "WRITE_APP_STORAGE"
    VIEW_APP = "VIEW_APP"
    VIEW_CONFIG_INFO = "VIEW_CONFIG_INFO"
    CREATE_CONFIG = "CREATE_CONFIG"
    EDIT_CONFIG_INFO = "EDIT_CONFIG_INFO"
    DELETE_CONFIG = "DELETE_CONFIG"
    VIEW_CONFIG_CONTENT = "VIEW_CONFIG_CONTENT"
    EDIT_CONFIG_CONTENT = "EDIT_CONFIG_CONTENT"
    VIEW_RUN_INFO = "VIEW_RUN_INFO"
    START_RUN = "START_RUN"
    STOP_RUN = "STOP_RUN"
    DOWNLOAD_RUN_RESULT = "DOWNLOAD_RUN_RESULT"
    VIEW_PUBLIC_APP_MEMBERS = "VIEW_PUBLIC_APP_MEMBERS"
    VIEW_PRIVATE_APP_MEMBERS = "VIEW_PRIVATE_APP_MEMBERS"
    MANAGE_APP_MEMBERS = "MANAGE_APP_MEMBERS"


class ApiKeyStatus(str, Enum):
    ACTIVE = "ACTIVE"


class ApiKeyValidityStatus(str, Enum):
    ACTIVE = "ACTIVE"
    NOT_YET_ACTIVE = "NOT_YET_ACTIVE"
    EXPIRED = "EXPIRED"


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("API-key timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


class ApiKey(BaseModel):
    """Managed-key metadata.

    Timestamp defaults preserve construction compatibility with the original metadata-only
    model. Service-returned instances always populate the server-required timestamps.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    api_key_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    prefix: str = Field(min_length=1, max_length=MAX_SECRET_LENGTH)
    permissions: tuple[NamespacePermission, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_used_at: datetime | None = None
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE
    not_before: datetime | None = None
    expires_at: datetime | None = None
    validity_status: ApiKeyValidityStatus = ApiKeyValidityStatus.ACTIVE

    @field_validator(
        "created_at",
        "updated_at",
        "last_used_at",
        "not_before",
        "expires_at",
    )
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return _utc_datetime(value)


class CreatedApiKey(ApiKey):
    value: SecretStr = Field(min_length=1, max_length=MAX_SECRET_LENGTH)
