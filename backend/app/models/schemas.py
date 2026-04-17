from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ── AUTH ──────────────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    avatar_color: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── ROOMS ─────────────────────────────────────────────────────
class RoomCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = ""
    video_url: Optional[str] = ""
    category: Optional[str] = "Movies"
    access: Optional[str] = "public"
    max_viewers: Optional[int] = 50


class RoomUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    status: Optional[str] = None


class RoomOut(BaseModel):
    id: str
    title: str
    description: str
    video_url: str
    category: str
    access: str
    status: str
    host_id: str
    max_viewers: int
    created_at: datetime
    host: UserOut
    viewer_count: int = 0

    model_config = {"from_attributes": True}


# ── MESSAGES ──────────────────────────────────────────────────
class MessageOut(BaseModel):
    id: str
    room_id: str
    user_id: str
    text: str
    msg_type: str
    created_at: datetime
    username: str
    avatar_color: str

    model_config = {"from_attributes": True}


# ── SOCKET EVENTS ─────────────────────────────────────────────
class PlayerState(BaseModel):
    playing: bool
    position: float  # seconds
    updated_at: Optional[float] = None  # unix timestamp


class SyncPayload(BaseModel):
    room_id: str
    state: PlayerState
    viewer_count: int
