import json
import asyncio
from typing import List, Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect, status
from src.middleware.auth import decode_access_token


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_sessions: Dict[WebSocket, str] = {}
        self.connection_users: Dict[WebSocket, str] = {}
        self.connection_rooms: Dict[WebSocket, Set[str]] = {}
        self.rooms: Dict[str, Set[WebSocket]] = {}

    def authenticate_token(self, token: Optional[str]) -> Optional[dict]:
        """Validate and decode JWT token for WebSocket connection."""
        if not token:
            return None
        payload = decode_access_token(token)
        return payload

    async def connect(
        self,
        websocket: WebSocket,
        token: Optional[str] = None,
        session_id: Optional[str] = None,
        rooms: Optional[List[str]] = None,
    ) -> Optional[dict]:
        """
        Authenticate token and accept WebSocket connection with scoped room initialization.
        """
        payload = self.authenticate_token(token)
        if not payload:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized: Invalid token")
            return None

        await websocket.accept()
        user_id = payload.get("user_id") or f"usr_{payload.get('sub', 'anonymous')}"

        self.active_connections.append(websocket)
        self.connection_users[websocket] = user_id
        self.connection_rooms[websocket] = set()

        if session_id:
            self.connection_sessions[websocket] = session_id

        # Automatically join user-scoped room `user:{id}`
        self.join_room(websocket, f"user:{user_id}")

        if rooms:
            for r in rooms:
                self.join_room(websocket, r)

        return payload

    def join_room(self, websocket: WebSocket, room: str):
        """Join a scoped room (e.g. project:{id}, incident:{id}, user:{id})."""
        if websocket not in self.connection_rooms:
            self.connection_rooms[websocket] = set()
        self.connection_rooms[websocket].add(room)

        if room not in self.rooms:
            self.rooms[room] = set()
        self.rooms[room].add(websocket)

    def leave_room(self, websocket: WebSocket, room: str):
        """Leave a scoped room."""
        if websocket in self.connection_rooms:
            self.connection_rooms[websocket].discard(room)
        if room in self.rooms:
            self.rooms[room].discard(websocket)
            if not self.rooms[room]:
                del self.rooms[room]

    def disconnect(self, websocket: WebSocket):
        """Clean up WebSocket connection and room memberships."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_sessions:
            del self.connection_sessions[websocket]
        if websocket in self.connection_users:
            del self.connection_users[websocket]

        if websocket in self.connection_rooms:
            for room in list(self.connection_rooms[websocket]):
                if room in self.rooms:
                    self.rooms[room].discard(websocket)
                    if not self.rooms[room]:
                        del self.rooms[room]
            del self.connection_rooms[websocket]

    async def broadcast_to_room(self, room: str, message: Dict[str, Any]):
        """Broadcast message to all subscribers of a specific room."""
        if room not in self.rooms:
            return
        disconnected = []
        for connection in list(self.rooms[room]):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast message to user-scoped room `user:{id}`."""
        await self.broadcast_to_room(f"user:{user_id}", message)

    async def broadcast_to_project(self, project_id: str, message: Dict[str, Any]):
        """Broadcast message to project-scoped room `project:{id}`."""
        await self.broadcast_to_room(f"project:{project_id}", message)

    async def broadcast_to_incident(self, incident_id: str, message: Dict[str, Any]):
        """Broadcast message to incident-scoped room `incident:{id}`."""
        await self.broadcast_to_room(f"incident:{incident_id}", message)

    async def broadcast(self, message: Dict[str, Any], session_id: Optional[str] = None, room: Optional[str] = None):
        """Broadcast message to room or all connections."""
        if room:
            await self.broadcast_to_room(room, message)
            return

        disconnected = []
        for connection in list(self.active_connections):
            conn_session = self.connection_sessions.get(connection)
            if session_id and conn_session and conn_session != session_id:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


websocket_manager = WebSocketManager()
ConnectionManager = WebSocketManager
