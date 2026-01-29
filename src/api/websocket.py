"""WebSocket support for real-time updates."""

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and store new connection.

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket connected | total={len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection.

        Args:
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected | total={len(self.active_connections)}")

    async def send_personal(self, message: dict[str, Any], websocket: WebSocket) -> None:
        """Send message to specific connection.

        Args:
            message: Message to send
            websocket: Target WebSocket
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast message to all connections.

        Args:
            message: Message to broadcast
        """
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send broadcast: {e}")
                    disconnected.append(connection)

            # Remove disconnected clients
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    async def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast typed event.

        Args:
            event_type: Event type identifier
            data: Event data
        """
        message = {
            "type": event_type,
            "data": data,
        }
        await self.broadcast(message)

    @property
    def connection_count(self) -> int:
        """Get number of active connections.

        Returns:
            Connection count
        """
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint handler.

    Args:
        websocket: WebSocket connection
    """
    await manager.connect(websocket)

    try:
        while True:
            # Receive and process messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_websocket_message(websocket, message)
            except json.JSONDecodeError:
                await manager.send_personal(
                    {"type": "error", "message": "Invalid JSON"},
                    websocket,
                )
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


async def handle_websocket_message(websocket: WebSocket, message: dict[str, Any]) -> None:
    """Handle incoming WebSocket message.

    Args:
        websocket: WebSocket connection
        message: Received message
    """
    msg_type = message.get("type", "")

    if msg_type == "ping":
        await manager.send_personal({"type": "pong"}, websocket)

    elif msg_type == "subscribe":
        # Handle subscription requests
        channel = message.get("channel")
        await manager.send_personal(
            {"type": "subscribed", "channel": channel},
            websocket,
        )

    elif msg_type == "unsubscribe":
        channel = message.get("channel")
        await manager.send_personal(
            {"type": "unsubscribed", "channel": channel},
            websocket,
        )

    else:
        await manager.send_personal(
            {"type": "error", "message": f"Unknown message type: {msg_type}"},
            websocket,
        )


# Event emitters for different parts of the system
async def emit_task_update(task_id: str, status: str, data: dict[str, Any] | None = None) -> None:
    """Emit task update event.

    Args:
        task_id: Task ID
        status: New status
        data: Additional data
    """
    await manager.broadcast_event(
        "task_update",
        {
            "task_id": task_id,
            "status": status,
            **(data or {}),
        },
    )


async def emit_scraping_progress(
    task_id: str,
    page: int,
    items: int,
    total_pages: int | None = None,
) -> None:
    """Emit scraping progress event.

    Args:
        task_id: Task ID
        page: Current page
        items: Items scraped
        total_pages: Total pages if known
    """
    await manager.broadcast_event(
        "scraping_progress",
        {
            "task_id": task_id,
            "current_page": page,
            "items_scraped": items,
            "total_pages": total_pages,
        },
    )


async def emit_worker_status(worker_id: str, status: str, stats: dict[str, Any] | None = None) -> None:
    """Emit worker status event.

    Args:
        worker_id: Worker ID
        status: Worker status
        stats: Worker statistics
    """
    await manager.broadcast_event(
        "worker_status",
        {
            "worker_id": worker_id,
            "status": status,
            "stats": stats,
        },
    )


async def emit_metrics_update(metrics: dict[str, Any]) -> None:
    """Emit metrics update event.

    Args:
        metrics: Current metrics
    """
    await manager.broadcast_event("metrics_update", metrics)
