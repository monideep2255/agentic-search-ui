"""Pydantic request and response schemas for the `/auth` router.

Spec: Technical_specification.md Section 15 (lines 2372-2390), the auth
service and its five-endpoint list.

Every request model sets `extra="forbid"`, so an unknown field in a
request body is a 422, not a silently ignored field (T-1.1-03 acceptance
criterion). Every response model excludes `password_hash`,
`refresh_token_hash`, and any field belonging to a user other than the
caller.

Depends on:
    - Nothing outside pydantic. This module never imports the ORM models
      or the database session directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class SignupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    created_at: datetime
    last_login_at: datetime | None
