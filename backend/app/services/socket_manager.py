"""
Socket.IO connection manager.
Handles real-time room events: join/leave, playback sync, chat, reactions.
"""
import socketio
from datetime import datetime
from typing import Dict, Set, Optional

# In-memory room state (use Redis in production for multi-process)
class RoomState:
    def __init__(self):
        self.playing: bool = False
        self.position: float = 0.0          # seconds
        self.updated_at: float = 0.0         # unix timestamp
        self.viewers: Dict[str, dict] = {}   # sid -> {user_id, username, avatar_color}

    def to_dict(self):
        return {
            "playing": self.playing,
            "position": self.position,
            "updated_at": self.updated_at,
            "viewer_count": len(self.viewers),
        }


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[str, RoomState] = {}          # room_id -> RoomState
        self._sid_to_room: Dict[str, str] = {}          # sid -> room_id

    def _get_or_create(self, room_id: str) -> RoomState:
        if room_id not in self._rooms:
            self._rooms[room_id] = RoomState()
        return self._rooms[room_id]

    def viewer_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, RoomState()).viewers)

    def join(self, room_id: str, sid: str, user_info: dict):
        state = self._get_or_create(room_id)
        state.viewers[sid] = user_info
        self._sid_to_room[sid] = room_id

    def leave(self, sid: str) -> Optional[str]:
        room_id = self._sid_to_room.pop(sid, None)
        if room_id and room_id in self._rooms:
            self._rooms[room_id].viewers.pop(sid, None)
            if not self._rooms[room_id].viewers:
                del self._rooms[room_id]
        return room_id

    def get_state(self, room_id: str) -> Optional[RoomState]:
        return self._rooms.get(room_id)

    def viewers_list(self, room_id: str) -> list:
        state = self._rooms.get(room_id)
        if not state:
            return []
        return list(state.viewers.values())


manager = ConnectionManager()


def create_sio() -> socketio.AsyncServer:
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    @sio.event
    async def connect(sid, environ, auth):
        print(f"[WS] connect sid={sid}")

    @sio.event
    async def disconnect(sid):
        room_id = manager.leave(sid)
        if room_id:
            state = manager.get_state(room_id)
            viewers = manager.viewers_list(room_id)
            await sio.emit(
                "viewer_left",
                {"sid": sid, "viewers": viewers, "viewer_count": len(viewers)},
                room=room_id,
            )
            print(f"[WS] disconnect sid={sid} left room={room_id}")

    @sio.event
    async def join_room(sid, data):
        """
        data: {room_id, user_id, username, avatar_color}
        """
        room_id = data.get("room_id")
        if not room_id:
            return

        user_info = {
            "sid": sid,
            "user_id": data.get("user_id", sid),
            "username": data.get("username", "Viewer"),
            "avatar_color": data.get("avatar_color", "#e63c6e"),
        }

        manager.join(room_id, sid, user_info)
        await sio.enter_room(sid, room_id)

        state = manager.get_state(room_id)
        viewers = manager.viewers_list(room_id)

        # Send current state to new joiner
        await sio.emit(
            "sync_state",
            {**state.to_dict(), "viewers": viewers},
            to=sid,
        )

        # Notify room of new viewer
        await sio.emit(
            "viewer_joined",
            {"user": user_info, "viewers": viewers, "viewer_count": len(viewers)},
            room=room_id,
        )
        print(f"[WS] {user_info['username']} joined room={room_id}")

    @sio.event
    async def leave_room(sid, data):
        room_id = data.get("room_id")
        manager.leave(sid)
        if room_id:
            await sio.leave_room(sid, room_id)
            viewers = manager.viewers_list(room_id)
            await sio.emit(
                "viewer_left",
                {"sid": sid, "viewers": viewers, "viewer_count": len(viewers)},
                room=room_id,
            )

    @sio.event
    async def player_play(sid, data):
        """data: {room_id, position}"""
        room_id = data.get("room_id")
        state = manager.get_state(room_id)
        if not state:
            return
        state.playing = True
        state.position = data.get("position", state.position)
        import time
        state.updated_at = time.time()
        await sio.emit("player_play", {"position": state.position, "updated_at": state.updated_at}, room=room_id, skip_sid=sid)

    @sio.event
    async def player_pause(sid, data):
        """data: {room_id, position}"""
        room_id = data.get("room_id")
        state = manager.get_state(room_id)
        if not state:
            return
        state.playing = False
        state.position = data.get("position", state.position)
        import time
        state.updated_at = time.time()
        await sio.emit("player_pause", {"position": state.position, "updated_at": state.updated_at}, room=room_id, skip_sid=sid)

    @sio.event
    async def player_seek(sid, data):
        """data: {room_id, position}"""
        room_id = data.get("room_id")
        state = manager.get_state(room_id)
        if not state:
            return
        state.position = data.get("position", 0)
        import time
        state.updated_at = time.time()
        await sio.emit("player_seek", {"position": state.position, "updated_at": state.updated_at}, room=room_id, skip_sid=sid)

    @sio.event
    async def request_sync(sid, data):
        """Host broadcasts current state on demand"""
        room_id = data.get("room_id")
        state = manager.get_state(room_id)
        if not state:
            return
        viewers = manager.viewers_list(room_id)
        await sio.emit("sync_state", {**state.to_dict(), "viewers": viewers}, room=room_id)

    @sio.event
    async def chat_message(sid, data):
        """data: {room_id, text, username, avatar_color}"""
        room_id = data.get("room_id")
        if not room_id:
            return

        payload = {
            "id": str(datetime.utcnow().timestamp()),
            "user_id": data.get("user_id", sid),
            "username": data.get("username", "Viewer"),
            "avatar_color": data.get("avatar_color", "#e63c6e"),
            "text": data.get("text", ""),
            "msg_type": "chat",
            "created_at": datetime.utcnow().isoformat(),
        }
        await sio.emit("chat_broadcast", payload, room=room_id)

    @sio.event
    async def reaction(sid, data):
        """data: {room_id, emoji, username}"""
        room_id = data.get("room_id")
        if not room_id:
            return
        await sio.emit(
            "reaction_broadcast",
            {"emoji": data.get("emoji", "❤️"), "username": data.get("username", "")},
            room=room_id,
        )

    return sio
