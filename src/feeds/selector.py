"""News Selector - ranking and selecting top news items."""

from datetime import datetime, timedelta
from collections import defaultdict

from loguru import logger

from src.config import get_feed_config, get_settings
from .models import FeedItem


class NewsSelector:
    """Selects and ranks news items for processing."""

    def __init__(self):
        self.feed_config = get_feed_config()
        self.settings = get_settings()

    def _calculate_recency_score(self, item: FeedItem) -> float:
        """Calculate score based on how recent the item is."""
        if not item.published_date:
            return 0.5  # Default score for items without date

        now = datetime.utcnow()
        age = now - item.published_date

        # Score decreases with age
        if age < timedelta(hours=1):
            return 1.0
        elif age < timedelta(hours=6):
            return 0.9
        elif age < timedelta(hours=12):
            return 0.8
        elif age < timedelta(days=1):
            return 0.7
        elif age < timedelta(days=2):
            return 0.5
        elif age < timedelta(days=7):
            return 0.3
        else:
            return 0.1

    def _get_source_priority(self, item: FeedItem) -> float:
        """Get priority multiplier for the item's source."""
        for feed in self.feed_config.feeds:
            if feed.get("category") == item.category:
                return feed.get("priority", 1.0)
        return 1.0

    def _has_image_bonus(self, item: FeedItem) -> float:
        """Bonus for items with images."""
        return 1.2 if item.image_url else 1.0

    def _description_quality_score(self, item: FeedItem) -> float:
        """Score based on description quality."""
        if not item.description:
            return 0.5

        length = len(item.description)
        if length < 50:
            return 0.6
        elif length < 100:
            return 0.8
        elif length < 500:
            return 1.0
        else:
            return 0.9  # Very long descriptions might be noisy

    def calculate_score(self, item: FeedItem) -> float:
        """Calculate overall score for an item."""
        recency = self._calculate_recency_score(item)
        priority = self._get_source_priority(item)
        image_bonus = self._has_image_bonus(item)
        quality = self._description_quality_score(item)

        # Weighted combination
        score = (
            recency * 0.4 +
            quality * 0.3 +
            0.3  # Base score
        ) * priority * image_bonus

        return round(score, 4)

    def rank_items(self, items: list[FeedItem]) -> list[tuple[FeedItem, float]]:
        """Rank items by score. Returns list of (item, score) tuples."""
        scored_items = []
        for item in items:
            score = self.calculate_score(item)
            scored_items.append((item, score))

        return sorted(scored_items, key=lambda x: x[1], reverse=True)

    def ensure_category_diversity(
        self, scored_items: list[tuple[FeedItem, float]], top_n: int
    ) -> list[FeedItem]:
        """Ensure selected items have category diversity."""
        if len(scored_items) <= top_n:
            return [item for item, _ in scored_items]

        selected = []
        category_counts = defaultdict(int)
        max_per_category = max(2, top_n // 2)  # At most half from same category

        for item, score in scored_items:
            if len(selected) >= top_n:
                break

            # Check category limit
            if category_counts[item.category] >= max_per_category:
                continue

            selected.append(item)
            category_counts[item.category] += 1

        # If we don't have enough, fill from remaining
        if len(selected) < top_n:
            for item, _ in scored_items:
                if item not in selected:
                    selected.append(item)
                if len(selected) >= top_n:
                    break

        return selected

    def select_top_items(
        self,
        items: list[FeedItem],
        top_n: int = None,
    ) -> list[FeedItem]:
        """Select top N items for processing."""
        top_n = top_n or self.settings.top_n_items

        if not items:
            logger.warning("No items available for selection")
            return []

        # Filter out items without images
        items_with_images = [item for item in items if item.image_url]
        filtered_count = len(items) - len(items_with_images)

        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} items without images")

        if not items_with_images:
            logger.warning("No items with images available for selection")
            return []

        logger.info(f"Ranking {len(items_with_images)} items...")

        # Rank all items (only those with images)
        ranked = self.rank_items(items_with_images)

        # Apply diversity filter
        selected = self.ensure_category_diversity(ranked, top_n)

        logger.info(f"Selected {len(selected)} items for processing")
        for i, item in enumerate(selected, 1):
            score = next((s for it, s in ranked if it == item), 0)
            logger.debug(
                f"  {i}. [{item.category}] {item.title[:50]}... (score: {score})"
            )

        return selected
