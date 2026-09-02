"""Asynchronous WebSocket server for ImageGenPiper bridge."""

import asyncio
import logging
import uuid
from typing import Any, Callable, Coroutine, Dict, Optional, Set
import websockets
from websockets.server import WebSocketServerProtocol, serve

from core.protocol import (
    AnyMessage,
    BaseMessage,
    PingMessage,
    PongMessage,
    parse_message,
    serialize_message,
)

logger = logging.getLogger(__name__)

MessageHandler = Callable[[str, AnyMessage], Coroutine[Any, Any, None]]


class WebSocketBridgeServer:
    """WebSocket server bridging Python orchestrator with Chrome Extension."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._server = None
        self._clients: Dict[str, WebSocketServerProtocol] = {}
        self._handlers: Set[MessageHandler] = set()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def connected_clients_count(self) -> int:
        return len(self._clients)

    def register_handler(self, handler: MessageHandler) -> None:
        """Register an async callback for received client messages."""
        self._handlers.add(handler)

    def unregister_handler(self, handler: MessageHandler) -> None:
        """Unregister a callback."""
        self._handlers.discard(handler)

    async def start(self) -> None:
        """Start the WebSocket server."""
        if self._is_running:
            return

        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=20,
        )
        self._is_running = True
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully stop the WebSocket server and close client connections."""
        if not self._is_running:
            return

        self._is_running = False
        # Close all active client connections
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self._clients.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("WebSocket server stopped.")

    async def send_to_client(self, client_id: str, message: BaseMessage) -> bool:
        """Send a message to a specific client."""
        ws = self._clients.get(client_id)
        if not ws:
            logger.warning(f"Client {client_id} not connected.")
            return False

        try:
            payload = serialize_message(message)
            await ws.send(payload)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            return False

    async def broadcast(self, message: BaseMessage) -> int:
        """Broadcast a message to all connected clients. Returns count of successful deliveries."""
        if not self._clients:
            logger.debug("No connected clients to broadcast to.")
            return 0

        payload = serialize_message(message)
        sent_count = 0
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(payload)
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to broadcast to client {client_id}: {e}")
        return sent_count

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket connection lifecycle."""
        client_id = str(uuid.uuid4())
        self._clients[client_id] = websocket
        logger.info(f"Client connected: {client_id} (Total: {len(self._clients)})")

        try:
            async for raw_msg in websocket:
                try:
                    parsed_msg = parse_message(raw_msg)
                except Exception as e:
                    logger.warning(f"Failed to parse incoming message from {client_id}: {e}")
                    continue

                # Auto-reply to ping messages
                if isinstance(parsed_msg, PingMessage):
                    pong = PongMessage(timestamp=parsed_msg.timestamp)
                    await websocket.send(serialize_message(pong))
                    continue

                # Dispatch to all registered message handlers
                for handler in list(self._handlers):
                    try:
                        asyncio.create_task(handler(client_id, parsed_msg))
                    except Exception as e:
                        logger.error(f"Error invoking handler {handler}: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed for client: {client_id}")
        except Exception as e:
            logger.error(f"Unexpected error in client connection {client_id}: {e}")
        finally:
            self._clients.pop(client_id, None)
            logger.info(f"Client removed: {client_id} (Remaining: {len(self._clients)})")
