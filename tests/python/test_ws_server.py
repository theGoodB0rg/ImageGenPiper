import asyncio
import json
import pytest
import websockets
from core.protocol import (
    GenerateRequest,
    ImageFound,
    PingMessage,
    PongMessage,
    serialize_message,
    parse_message,
    MessageType,
)
from core.ws_server import WebSocketBridgeServer


@pytest.mark.asyncio
async def test_ws_server_startup_and_client_connection():
    server = WebSocketBridgeServer(host="127.0.0.1", port=8769)
    await server.start()
    assert server.is_running
    assert server.connected_clients_count == 0

    try:
        async with websockets.connect("ws://127.0.0.1:8769") as ws:
            # Wait briefly for server to register connection
            await asyncio.sleep(0.05)
            assert server.connected_clients_count == 1

            # Send ping, receive pong
            ping = PingMessage(timestamp=123456789)
            await ws.send(serialize_message(ping))

            resp_raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            resp = parse_message(resp_raw)
            assert isinstance(resp, PongMessage)
            assert resp.timestamp >= 123456789

        # Client disconnected
        await asyncio.sleep(0.05)
        assert server.connected_clients_count == 0
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_ws_server_dispatch_and_receive():
    server = WebSocketBridgeServer(host="127.0.0.1", port=8770)
    received_on_server = []

    async def message_handler(client_id: str, msg):
        received_on_server.append((client_id, msg))

    server.register_handler(message_handler)
    await server.start()

    try:
        async with websockets.connect("ws://127.0.0.1:8770") as ws:
            await asyncio.sleep(0.05)

            # Send GenerateRequest from server to client
            req = GenerateRequest(
                id="req-999",
                prompt="test prompt",
                timeout_ms=10000
            )
            await server.broadcast(req)

            # Client receives request
            client_recv = await asyncio.wait_for(ws.recv(), timeout=2.0)
            parsed_client = parse_message(client_recv)
            assert isinstance(parsed_client, GenerateRequest)
            assert parsed_client.id == "req-999"

            # Client responds with ImageFound
            img_msg = ImageFound(
                id="req-999",
                image_index=1,
                mime_type="image/png",
                data_base64="dGVzdA==",
                metadata={}
            )
            await ws.send(serialize_message(img_msg))

            # Wait for server handler to process message
            await asyncio.sleep(0.05)
            assert len(received_on_server) == 1
            client_id, msg = received_on_server[0]
            assert isinstance(msg, ImageFound)
            assert msg.id == "req-999"
    finally:
        await server.stop()
