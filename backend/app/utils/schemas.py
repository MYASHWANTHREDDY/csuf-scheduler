"""Pydantic schemas for API request validation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Validated payload for user login."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    """Validated payload for creating a user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str = ""
    last_name: str = ""
    name: str = ""
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    role: str = "student"


class CreateShiftRequest(BaseModel):
    """Validated payload for creating a shift."""

    model_config = ConfigDict(str_strip_whitespace=True)

    date: str
    start_time: str
    end_time: str


class AssignShiftRequest(BaseModel):
    """Validated payload for assigning a shift."""

    shift_id: int
    user_id: int


class ShiftResponse(BaseModel):
    """Serialized shift response schema."""

    id: int
    date: str
    start_time: str
    end_time: str
    assigned_user_id: int | None = None


class PaginatedShiftsResponse(BaseModel):
    """Paginated shift list response schema."""

    items: list[ShiftResponse]
    page: int
    per_page: int
    total: int
    pages: int


class ErrorResponse(BaseModel):
    """Standardized error response schema."""

    error: str | list[dict]
