"""RSS Feed Manager - fetching and parsing RSS feeds."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from html import unescape
import re

import aiohttp
import feedparser
from loguru import logger

from src.config import get_feed_config, DATA_DIR
from .models import FeedConfig, FeedItem, ParsedFeed


LAST_RUN_FILE = DATA_DIR / "last_run.json"


class RSSFeedManager:
    """Manages RSS feed fetching and parsing."""

    def __init__(self):
        self.feed_config = get_feed_config()
        self._last_run = self._load_last_run()

    def _load_last_run(self) -> datetime:
        """Load last run timestamp, default to 6 hours ago."""
        if LAST_RUN_FILE.exists():
            try:
                with open(LAST_RUN_FILE, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data["last_run"].replace("Z", "+00:00")).replace(tzinfo=None)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load last run timestamp: {e}")
        return datetime.utcnow() - timedelta(hours=6)

    def _save_last_run(self):
        """Save current timestamp as last run."""
        with open(LAST_RUN_FILE, 'w') as f:
            json.dump({"last_run": datetime.utcnow().isoformat() + "Z"}, f)

    def _generate_item_id(self, title: str, link: str) -> str:
        """Generate unique ID by hashing title and link."""
        content = f"{title}{link}"
        return hashlib.md5(content.encode()).hexdigest()

    def _clean_html(self, text: Optional[str]) -> Optional[str]:
        """Remove HTML tags and clean up text."""
        if not text:
            return None
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Unescape HTML entities
        clean = unescape(clean)
        # Clean up whitespace
        clean = " ".join(clean.split())
        return clean.strip() if clean else None

    def _extract_image_url(self, entry: dict) -> Optional[str]:
        """Extract image URL from feed entry."""
        # Try media:content
        if "media_content" in entry:
            for media in entry.media_content:
                if media.get("medium") == "image" or media.get("type", "").startswith("image"):
                    return media.get("url")

        # Try media:thumbnail
        if "media_thumbnail" in entry:
            thumbnails = entry.media_thumbnail
            if thumbnails:
                return thumbnails[0].get("url")

        # Try enclosures
        if "enclosures" in entry:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image"):
                    return enc.get("url")

        # Try to find image in content
        content = entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
        content += entry.get("summary", "")

        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
        if img_match:
            return img_match.group(1)

        return None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from feed entry."""
        date_fields = ["published_parsed", "updated_parsed", "created_parsed"]
        for field in date_fields:
            if field in entry and entry[field]:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(entry[field]))
                except (TypeError, ValueError, OverflowError):
                    continue
        return None

    def _get_source_name(self, feed: feedparser.FeedParserDict) -> Optional[str]:
        """Extract source name from feed."""
        if feed.feed.get("title"):
            return feed.feed.title
        return None

    async def fetch_feed(self, url: str, category: str) -> ParsedFeed:
        """Fetch and parse a single RSS feed."""
        logger.info(f"Fetching feed: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch {url}: HTTP {response.status}")
                        return ParsedFeed(url=url, error=f"HTTP {response.status}")

                    content = await response.text()

            # Parse the feed
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                logger.error(f"Failed to parse {url}: {feed.bozo_exception}")
                return ParsedFeed(url=url, error=str(feed.bozo_exception))

            source_name = self._get_source_name(feed)
            items = []

            for entry in feed.entries:
                title = self._clean_html(entry.get("title", ""))
                link = entry.get("link", "")

                if not title or not link:
                    continue

                item_id = self._generate_item_id(title, link)
                description = self._clean_html(
                    entry.get("summary") or
                    (entry.get("content", [{}])[0].get("value") if entry.get("content") else None)
                )

                item = FeedItem(
                    id=item_id,
                    feed_url=url,
                    title=title,
                    link=link,
                    description=description,
                    published_date=self._parse_date(entry),
                    image_url=self._extract_image_url(entry),
                    category=category,
                    source_name=source_name,
                )
                items.append(item)

            logger.info(f"Parsed {len(items)} items from {url}")
            return ParsedFeed(url=url, title=source_name, items=items)

        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching {url}: {e}")
            return ParsedFeed(url=url, error=str(e))
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ParsedFeed(url=url, error=str(e))

    async def fetch_all_feeds(self) -> list[ParsedFeed]:
        """Fetch all enabled feeds."""
        import asyncio

        feeds = self.feed_config.enabled_feeds
        logger.info(f"Fetching {len(feeds)} feeds...")

        tasks = [
            self.fetch_feed(feed["url"], feed["category"])
            for feed in feeds
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        parsed_feeds = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Feed fetch failed: {result}")
            elif isinstance(result, ParsedFeed):
                parsed_feeds.append(result)

        return parsed_feeds

    def filter_new_items(self, parsed_feeds: list[ParsedFeed]) -> list[FeedItem]:
        """Filter items published after last run."""
        new_items = []
        for feed in parsed_feeds:
            if feed.error:
                continue
            for item in feed.items:
                if item.published_date and item.published_date > self._last_run:
                    new_items.append(item)
                elif not item.published_date:
                    # Include items without date (assume recent)
                    new_items.append(item)
        logger.info(f"Found {len(new_items)} items since {self._last_run}")
        return new_items

    def mark_run_complete(self):
        """Mark this run as complete (save timestamp)."""
        self._save_last_run()
        logger.info(f"Saved run timestamp to {LAST_RUN_FILE}")
