"""Configuration settings for ImageGenPiper."""

from typing import Tuple
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configurations."""

    model_config = SettingsConfigDict(env_prefix="IGP_", env_file=".env", extra="ignore")

    ws_host: str = Field(default="127.0.0.1", description="WebSocket host to bind")
    ws_port: int = Field(default=8765, description="WebSocket port to listen on")
    output_dir: str = Field(default="./outputs", description="Directory to save generated images")
    rate_limit_rpm: float = Field(default=6.0, description="Rate limit (requests per minute)")
    burst_capacity: float = Field(default=2.0, description="Token bucket burst capacity")
    jitter_range: Tuple[float, float] = Field(default=(1.0, 3.0), description="Jitter delay range in seconds")
    concurrency: int = Field(default=1, description="Worker concurrency (default: 1 for single tab)")
    max_retries: int = Field(default=3, description="Maximum retries per failed prompt")
    timeout_ms: int = Field(default=120000, description="Per-prompt generation timeout in milliseconds")
