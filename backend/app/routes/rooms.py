from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app.models.orm import Room, User
from app.models.schemas import RoomCreate, RoomUpdate, RoomOut
from app.utils.auth import get_current_user
from app.services.socket_manager import manager

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def _room_out(room: Room, viewer_count: int = 0) -> RoomOut:
    data = RoomOut.model_validate(room)
    data.viewer_count = viewer_count
    return data


@router.get("", response_model=List[RoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Room).options(selectinload(Room.host)).order_by(Room.created_at.desc())
    )
    rooms = result.scalars().all()
    return [_room_out(r, manager.viewer_count(r.id)) for r in rooms]


@router.post("", response_model=RoomOut, status_code=201)
async def create_room(
    body: RoomCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = Room(
        title=body.title,
        description=body.description or "",
        video_url=body.video_url or "",
        category=body.category or "Movies",
        access=body.access or "public",
        host_id=current_user.id,
        max_viewers=body.max_viewers or 50,
    )
    db.add(room)
    await db.commit()
    await db.execute(select(Room).where(Room.id == room.id).options(selectinload(Room.host)))
    await db.refresh(room)
    # Eagerly load host
    result = await db.execute(
        select(Room).where(Room.id == room.id).options(selectinload(Room.host))
    )
    room = result.scalar_one()
    return _room_out(room, 0)


@router.get("/{room_id}", response_model=RoomOut)
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Room).where(Room.id == room_id).options(selectinload(Room.host))
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return _room_out(room, manager.viewer_count(room_id))


@router.patch("/{room_id}", response_model=RoomOut)
async def update_room(
    room_id: str,
    body: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Room).where(Room.id == room_id).options(selectinload(Room.host))
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    if room.host_id != current_user.id:
        raise HTTPException(403, "Not the host")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(room, field, value)

    await db.commit()
    await db.refresh(room)
    result = await db.execute(
        select(Room).where(Room.id == room_id).options(selectinload(Room.host))
    )
    room = result.scalar_one()
    return _room_out(room, manager.viewer_count(room_id))


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    if room.host_id != current_user.id:
        raise HTTPException(403, "Not the host")
    await db.delete(room)
    await db.commit()


@router.get("/{room_id}/messages")
async def get_messages(room_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.orm import Message
    from sqlalchemy.orm import selectinload as sl
    result = await db.execute(
        select(Message).where(Message.room_id == room_id)
        .options(sl(Message.user))
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    msgs = result.scalars().all()
    return [
        {
            "id": m.id,
            "room_id": m.room_id,
            "user_id": m.user_id,
            "text": m.text,
            "msg_type": m.msg_type,
            "created_at": m.created_at.isoformat(),
            "username": m.user.username,
            "avatar_color": m.user.avatar_color,
        }
        for m in msgs
    ]
