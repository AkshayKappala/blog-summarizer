"""Configuration management for Blog Summarizer."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="", description="Gemini API key")
    top_n_items: int = Field(default=5, description="Number of posts to generate per run")
    gemini_model: str = Field(default="gemini-2.5-pro", description="Gemini model to use")
    log_level: str = Field(default="INFO", description="Logging level")


class FeedConfig:
    """RSS feed configuration loaded from feeds.yaml."""

    def __init__(self):
        feeds_path = CONFIG_DIR / "feeds.yaml"
        if not feeds_path.exists():
            raise FileNotFoundError(f"Config file not found: {feeds_path}")
        with open(feeds_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    @property
    def feeds(self) -> list[dict]:
        """Get list of feed configurations."""
        return self._config.get("feeds", [])

    @property
    def enabled_feeds(self) -> list[dict]:
        """Get list of enabled feeds only."""
        return [f for f in self.feeds if f.get("enabled", True)]


class PromptConfig:
    """Prompt templates loaded from prompts.yaml."""

    def __init__(self):
        prompts_path = CONFIG_DIR / "prompts.yaml"
        if not prompts_path.exists():
            raise FileNotFoundError(f"Config file not found: {prompts_path}")
        with open(prompts_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    @property
    def system_message(self) -> str:
        return self._config.get("system_message", "")

    @property
    def summarization_prompt(self) -> str:
        return self._config.get("summarization_prompt", "")

    @property
    def model_settings(self) -> dict:
        return self._config.get("model_settings", {})


# Singletons
_settings: Optional[Settings] = None
_feed_config: Optional[FeedConfig] = None
_prompt_config: Optional[PromptConfig] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_feed_config() -> FeedConfig:
    global _feed_config
    if _feed_config is None:
        _feed_config = FeedConfig()
    return _feed_config


def get_prompt_config() -> PromptConfig:
    global _prompt_config
    if _prompt_config is None:
        _prompt_config = PromptConfig()
    return _prompt_config


# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
