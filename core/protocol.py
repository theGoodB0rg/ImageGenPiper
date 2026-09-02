"""WebSocket JSON-RPC Protocol definitions and models for ImageGenPiper."""

from enum import Enum
import json
import time
from typing import Any, Dict, Optional, Union
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    GENERATE_REQUEST = "GENERATE_REQUEST"
    IMAGE_FOUND = "IMAGE_FOUND"
    GENERATION_ERROR = "GENERATION_ERROR"
    STATUS_UPDATE = "STATUS_UPDATE"
    PING = "PING"
    PONG = "PONG"


class ErrorCode(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    DOM_ERROR = "DOM_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNKNOWN = "UNKNOWN"


class GenerationStatus(str, Enum):
    QUEUED = "QUEUED"
    TYPING = "TYPING"
    GENERATING = "GENERATING"
    RENDERING = "RENDERING"
    DONE = "DONE"
    ERROR = "ERROR"


class BaseMessage(BaseModel):
    type: MessageType


class GenerateRequest(BaseMessage):
    type: MessageType = MessageType.GENERATE_REQUEST
    id: str
    prompt: str
    timeout_ms: int = 120000
    options: Dict[str, Any] = Field(default_factory=dict)


class ImageMetadata(BaseModel):
    width: Optional[int] = None
    height: Optional[int] = None
    source_url: Optional[str] = None


class ImageFound(BaseMessage):
    type: MessageType = MessageType.IMAGE_FOUND
    id: str
    image_index: int = 1
    mime_type: str = "image/png"
    data_base64: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GenerationError(BaseMessage):
    type: MessageType = MessageType.GENERATION_ERROR
    id: str
    error_code: ErrorCode = ErrorCode.UNKNOWN
    message: str
    retryable: bool = True


class StatusUpdate(BaseMessage):
    type: MessageType = MessageType.STATUS_UPDATE
    id: str
    status: GenerationStatus
    message: Optional[str] = None


class PingMessage(BaseMessage):
    type: MessageType = MessageType.PING
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


class PongMessage(BaseMessage):
    type: MessageType = MessageType.PONG
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))


AnyMessage = Union[
    GenerateRequest,
    ImageFound,
    GenerationError,
    StatusUpdate,
    PingMessage,
    PongMessage,
]

_TYPE_MAP = {
    MessageType.GENERATE_REQUEST: GenerateRequest,
    MessageType.IMAGE_FOUND: ImageFound,
    MessageType.GENERATION_ERROR: GenerationError,
    MessageType.STATUS_UPDATE: StatusUpdate,
    MessageType.PING: PingMessage,
    MessageType.PONG: PongMessage,
}


def serialize_message(message: BaseMessage) -> str:
    """Serialize a message model to JSON string."""
    return message.model_dump_json()


def parse_message(raw_json: str) -> AnyMessage:
    """Parse raw JSON string into the appropriate message model."""
    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Unknown or missing message type")

    msg_type_str = data.get("type")
    try:
        msg_type = MessageType(msg_type_str)
    except ValueError:
        raise ValueError(f"Unknown or missing message type: {msg_type_str}")

    model_cls = _TYPE_MAP.get(msg_type)
    if not model_cls:
        raise ValueError(f"No handler model for message type: {msg_type}")

    return model_cls.model_validate(data)
