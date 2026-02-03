"""Blog Summarizer - Generate Instagram posts from RSS feeds."""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import get_settings, GENERATED_DIR, DATA_DIR
from src.utils.logger import setup_logger
from src.feeds.manager import RSSFeedManager
from src.feeds.selector import NewsSelector
from src.feeds.models import FeedItem, PostResult
from src.summarizer.gemini_client import GeminiSummarizer
from src.images.html_renderer import HTMLRenderer


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Instagram posts from RSS feeds")
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip timestamp filtering (process all fetched items)"
    )
    return parser.parse_args()


def export_posts_json(posts: list[PostResult], feed_items: list[FeedItem]) -> Path:
    """Export generated posts to JSON file."""
    # Create lookup dict for feed items
    feed_items_dict = {item.id: item for item in feed_items}

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "posts": [],
    }

    for post in posts:
        feed_item = feed_items_dict.get(post.feed_item_id)
        if not feed_item:
            continue

        output["posts"].append({
            "source": post.summary.source or "Unknown",
            "original_title": feed_item.title,
            "original_url": feed_item.link,
            "original_image_url": feed_item.image_url,
            "generated_title": post.summary.title,
            "generated_description": post.summary.description,
            "caption": post.summary.caption,
            "hashtags": post.summary.hashtags,
            "image_path": post.image_path,
            "caption_image_path": post.caption_image_path,
            "height": post.height,
            "category": feed_item.category,
            "created_at": datetime.utcnow().isoformat() + "Z",
        })

    output_path = DATA_DIR / "posts.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(output['posts'])} posts to {output_path}")
    return output_path


async def run_workflow(skip_time_filter: bool = False):
    """Run the full content generation workflow.

    Args:
        skip_time_filter: If True, process all fetched items regardless of timestamp
    """
    setup_logger()
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("Starting Blog Summarizer Workflow")
    if skip_time_filter:
        logger.info("  (--no-filter: skipping timestamp filter)")
    logger.info("=" * 60)

    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set! Please set it in .env file.")
        return

    # Step 1: Fetch RSS feeds
    logger.info("\n[Step 1/4] Fetching RSS feeds...")
    feed_manager = RSSFeedManager()
    parsed_feeds = await feed_manager.fetch_all_feeds()

    if skip_time_filter:
        # Get all items from all feeds
        new_items = []
        for feed in parsed_feeds:
            if not feed.error:
                new_items.extend(feed.items)
        logger.info(f"Found {len(new_items)} total items (filter skipped)")
    else:
        new_items = feed_manager.filter_new_items(parsed_feeds)

    if not new_items:
        logger.info("No new items since last run")
        return

    # Step 2: Select top items
    logger.info(f"\n[Step 2/4] Selecting top {settings.top_n_items} items...")
    selector = NewsSelector()
    selected_items = selector.select_top_items(new_items, settings.top_n_items)

    if not selected_items:
        logger.warning("No items selected for processing")
        return

    # Step 3: Generate summaries
    logger.info("\n[Step 3/4] Generating summaries with Gemini...")
    summarizer = GeminiSummarizer()
    summaries = summarizer.summarize_items(selected_items)

    if not summaries:
        logger.warning("No summaries generated")
        return

    # Step 4: Create images
    logger.info("\n[Step 4/4] Creating post images...")
    renderer = HTMLRenderer()
    posts = renderer.create_posts_for_summaries(summaries, selected_items)

    # Mark run complete (save timestamp) - skip when testing locally
    if not skip_time_filter:
        feed_manager.mark_run_complete()

    # Export results
    if posts:
        export_posts_json(posts, selected_items)

    logger.info("\n" + "=" * 60)
    logger.info("Workflow completed successfully!")
    logger.info(f"  Items fetched:  {len(new_items)}")
    logger.info(f"  Items selected: {len(selected_items)}")
    logger.info(f"  Posts created:  {len(posts)}")
    logger.info(f"  Output folder:  {GENERATED_DIR}")
    logger.info("=" * 60)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_workflow(skip_time_filter=args.no_filter))
