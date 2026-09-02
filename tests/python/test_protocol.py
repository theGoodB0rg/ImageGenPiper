import pytest
from core.protocol import (
    MessageType,
    GenerateRequest,
    ImageFound,
    GenerationError,
    StatusUpdate,
    PingMessage,
    PongMessage,
    parse_message,
    serialize_message,
    ErrorCode,
    GenerationStatus,
)


def test_generate_request_serialization():
    req = GenerateRequest(
        id="test-id-123",
        prompt="A vibrant watercolor landscape with mountains",
        timeout_ms=60000,
        options={"aspect_ratio": "16:9"}
    )
    raw_json = serialize_message(req)
    parsed = parse_message(raw_json)
    
    assert isinstance(parsed, GenerateRequest)
    assert parsed.type == MessageType.GENERATE_REQUEST
    assert parsed.id == "test-id-123"
    assert parsed.prompt == "A vibrant watercolor landscape with mountains"
    assert parsed.timeout_ms == 60000
    assert parsed.options.get("aspect_ratio") == "16:9"


def test_image_found_serialization():
    img_msg = ImageFound(
        id="test-id-456",
        image_index=1,
        mime_type="image/png",
        data_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        metadata={"width": 1, "height": 1, "source_url": "https://lh3.googleusercontent.com/test"}
    )
    raw_json = serialize_message(img_msg)
    parsed = parse_message(raw_json)

    assert isinstance(parsed, ImageFound)
    assert parsed.type == MessageType.IMAGE_FOUND
    assert parsed.id == "test-id-456"
    assert parsed.image_index == 1
    assert parsed.mime_type == "image/png"
    assert parsed.metadata["width"] == 1


def test_generation_error_serialization():
    err_msg = GenerationError(
        id="test-id-789",
        error_code=ErrorCode.SAFETY_BLOCKED,
        message="Prompt violated safety guidelines",
        retryable=False
    )
    raw_json = serialize_message(err_msg)
    parsed = parse_message(raw_json)

    assert isinstance(parsed, GenerationError)
    assert parsed.type == MessageType.GENERATION_ERROR
    assert parsed.error_code == ErrorCode.SAFETY_BLOCKED
    assert parsed.retryable is False


def test_status_update_serialization():
    status_msg = StatusUpdate(
        id="test-id-101",
        status=GenerationStatus.GENERATING,
        message="Waiting for Gemini rendering..."
    )
    raw_json = serialize_message(status_msg)
    parsed = parse_message(raw_json)

    assert isinstance(parsed, StatusUpdate)
    assert parsed.type == MessageType.STATUS_UPDATE
    assert parsed.status == GenerationStatus.GENERATING


def test_ping_pong_serialization():
    ping = PingMessage(timestamp=1700000000)
    raw_ping = serialize_message(ping)
    parsed_ping = parse_message(raw_ping)
    assert isinstance(parsed_ping, PingMessage)

    pong = PongMessage(timestamp=1700000005)
    raw_pong = serialize_message(pong)
    parsed_pong = parse_message(raw_pong)
    assert isinstance(parsed_pong, PongMessage)


def test_invalid_json_handling():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_message("not a json string")


def test_unknown_message_type():
    with pytest.raises(ValueError, match="Unknown or missing message type"):
        parse_message('{"type": "UNKNOWN_TYPE", "id": "123"}')
