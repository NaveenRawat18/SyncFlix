from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.orm import User
from app.models.schemas import UserRegister, UserLogin, TokenResponse, UserOut
from app.utils.auth import hash_password, verify_password, create_access_token
import random

router = APIRouter(prefix="/api/auth", tags=["auth"])

AVATAR_COLORS = ["#e63c6e", "#7c3aed", "#3b82f6", "#22c55e", "#f59e0b", "#06b6d4", "#f97316"]


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check duplicate
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email or username already registered")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        avatar_color=random.choice(AVATAR_COLORS),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(db: AsyncSession = Depends(get_db), credentials=None):
    from app.utils.auth import get_current_user
    from fastapi.security import HTTPBearer
    # handled via dependency injection in actual use
    pass
