"""Configuration module for Gemini Computer Use Agent."""

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration settings for the Gemini Computer Use Agent."""

    screen_width: int = Field(default=1440, description="Target viewport width in pixels")
    screen_height: int = Field(default=900, description="Target viewport height in pixels")
    model: str = Field(
        default="gemini-3.6-flash",
        description="Gemini model ID to use (e.g. gemini-3.6-flash, gemini-3-flash-preview, gemini-2.5-computer-use-preview-10-2025)",
    )
    max_turns: int = Field(default=10, description="Maximum agent interaction turns limit")
    headless: bool = Field(default=True, description="Run Playwright browser in headless mode")
    enable_prompt_injection_detection: bool = Field(
        default=True, description="Enable prompt injection detection in Computer Use tool"
    )
    allowed_domains: List[str] = Field(
        default_factory=list,
        description="Domain allowlist (if non-empty, only allowed domains can be navigated to)",
    )
    blocked_domains: List[str] = Field(
        default_factory=list,
        description="Domain blocklist (prohibited domains)",
    )
    log_dir: str = Field(default="logs", description="Directory path for audit logs")
    screenshots_dir: str = Field(
        default="logs/screenshots", description="Directory path for saved screenshot artifacts"
    )
    initial_url: Optional[str] = Field(
        default="https://www.google.com", description="Initial URL to load before agent loop starts"
    )
