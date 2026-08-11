from src.services.websocket import WebSocketManager, websocket_manager

ConnectionManager = WebSocketManager
ws_manager = websocket_manager

__all__ = ["ConnectionManager", "WebSocketManager", "ws_manager", "websocket_manager"]
