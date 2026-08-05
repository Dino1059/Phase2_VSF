from typing import List, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_sessions: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, session_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if session_id:
            self.connection_sessions[websocket] = session_id

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_sessions:
            del self.connection_sessions[websocket]

    async def broadcast(self, message: Dict[str, Any], session_id: Optional[str] = None):
        disconnected = []
        for connection in self.active_connections:
            conn_session = self.connection_sessions.get(connection)
            if session_id and conn_session and conn_session != session_id:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

ws_manager = ConnectionManager()
