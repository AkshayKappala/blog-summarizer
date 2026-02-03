"""Pydantic models for RSS feed data."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class FeedConfig(BaseModel):
    """Configuration for a single RSS feed."""

    url: str
    category: str
    priority: float = 1.0
    enabled: bool = True


class FeedItem(BaseModel):
    """Parsed item from an RSS feed."""

    id: str = Field(description="Unique hash of title+link")
    feed_url: str
    title: str
    link: str
    description: Optional[str] = None
    published_date: Optional[datetime] = None
    image_url: Optional[str] = None
    category: str
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class ParsedFeed(BaseModel):
    """Result of parsing an RSS feed."""

    url: str
    title: Optional[str] = None
    items: list[FeedItem] = []
    error: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class SummaryResult(BaseModel):
    """Result from Gemini summarization."""

    title: str
    description: str
    caption: str
    hashtags: list[str]
    source: str = "Unknown"
    feed_item_id: str = ""


class PostResult(BaseModel):
    """Result from image rendering."""

    image_path: str
    caption_image_path: str
    height: int
    feed_item_id: str
    summary: SummaryResult
