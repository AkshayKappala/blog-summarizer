"""HTML-based image renderer using Playwright."""

from datetime import datetime
from pathlib import Path
from typing import Optional
import asyncio
import httpx

from playwright.async_api import async_playwright
from loguru import logger
from PIL import Image
from io import BytesIO

from src.config import GENERATED_DIR, PROJECT_ROOT, DATA_DIR
from src.feeds.models import FeedItem, SummaryResult, PostResult


class HTMLRenderer:
    """Renders HTML templates to images using Playwright."""

    # Canvas dimensions - 4:5 ratio (Instagram portrait)
    WIDTH = 1080
    HEIGHT = 1440

    def __init__(self):
        self.css_path = PROJECT_ROOT / "templates" / "post_styles.css"

        # Load shared CSS once
        with open(self.css_path, 'r', encoding='utf-8') as f:
            self.shared_css = f.read()

    def _extract_source_name(self, feed_item: FeedItem) -> str:
        """Extract clean source name from feed item."""
        if feed_item.source_name:
            return feed_item.source_name

        # Extract domain from feed URL
        url = feed_item.feed_url
        domain = url.split('/')[2] if len(url.split('/')) > 2 else url

        # Clean up common patterns
        domain = domain.replace('feeds.', '').replace('www.', '').replace('rss.', '')

        # Extract main name (before .com, .org, etc)
        name = domain.split('.')[0]

        # Capitalize properly
        name_map = {
            'bloomberg': 'Bloomberg',
            'techcrunch': 'TechCrunch',
            'theverge': 'The Verge',
            'arstechnica': 'Ars Technica',
            'bbci': 'BBC',
            'nytimes': 'NY Times',
            'cnbc': 'CNBC',
        }

        return name_map.get(name.lower(), name.capitalize())

    async def _get_image_aspect_ratio(self, image_url: str) -> Optional[float]:
        """Fetch image and calculate aspect ratio (width/height).

        Returns:
            Aspect ratio or None if image cannot be fetched
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(image_url)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    width, height = img.size
                    return width / height if height > 0 else None
        except Exception as e:
            logger.warning(f"Could not fetch image for aspect ratio: {e}")
        return None

    async def _determine_canvas_height(self, image_url: Optional[str]) -> int:
        """Determine canvas height based on image aspect ratio.

        - For images with aspect ratio > 4:3 (1.333): use 1080x1350
        - Otherwise: use 1080x1440 (4:5 ratio)
        """
        if not image_url:
            return self.HEIGHT  # Default 1440

        aspect_ratio = await self._get_image_aspect_ratio(image_url)

        if aspect_ratio and aspect_ratio > 1.333:
            # Wide image - use shorter canvas to avoid too much padding
            return 1350

        return self.HEIGHT  # Default 1440

    def _create_single_post_html(
        self,
        summary: SummaryResult,
        feed_item: FeedItem,
        canvas_height: int = None,
    ) -> str:
        """Create HTML for a single post card.

        Returns HTML string that can be rendered.
        """
        if canvas_height is None:
            canvas_height = self.HEIGHT

        category = feed_item.category or "default"
        image_url = feed_item.image_url or ""
        # Use source from summary if available, otherwise extract from feed
        source_name = summary.source if summary.source and summary.source != "Unknown" else self._extract_source_name(feed_item)

        # Determine gradient class
        category_colors = {
            'technology': 'bg-technology',
            'business': 'bg-business',
            'news': 'bg-news'
        }
        gradient_class = category_colors.get(category, 'bg-default')

        # Create standalone HTML for single post
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Post Preview</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        {self.shared_css}

        .glass-card {{
            display: flex;
            flex-direction: column;
            position: relative;
        }}

        .swipe-hint {{
            position: absolute;
            bottom: 20px;
            right: 24px;
            font-size: 1.6rem;
            color: rgba(255, 255, 255, 0.4);
            font-weight: 300;
            letter-spacing: 0.15em;
        }}
    </style>
</head>
<body>
    <div class="post-container" id="post-card" style="height: {canvas_height}px;">
        <!-- Layer 1: Blurred Background -->
        <div class="bg-layer {gradient_class if not image_url else ''}">
            {f'<img src="{image_url}" onerror="this.style.display=' + "'none'" + '">' if image_url else ''}
        </div>

        <!-- Layer 2: Main Content -->
        <div class="content-layer">
            <!-- Featured Image -->
            <div class="featured-image-wrapper">
                {f'<img src="{image_url}" class="featured-image" alt="Featured" id="featured-img">' if image_url else '<div style="width:100%; height:200px; display:flex; align-items:center; justify-content:center; background:rgba(255,255,255,0.1);">No Image</div>'}
            </div>

            <!-- Glass Card: Text Content -->
            <div class="glass-card">
                <div class="post-title">{summary.title}</div>
                <div class="post-description">{summary.description}</div>
                <div class="swipe-hint">read more ›››</div>
            </div>
        </div>

        <!-- Source Attribution -->
        <div class="source-attribution">{source_name}</div>
    </div>

    <script>
        // No aspect ratio detection needed - all posts are 1080x1440
    </script>
</body>
</html>"""
        return html

    def _create_caption_slide_html(
        self,
        summary: SummaryResult,
        feed_item: FeedItem,
        canvas_height: int = None,
    ) -> str:
        """Create HTML for the caption slide (second image).

        Contains:
        - Blurred background
        - Glassmorphic text box with caption
        """
        if canvas_height is None:
            canvas_height = self.HEIGHT

        category = feed_item.category or "default"
        image_url = feed_item.image_url or ""

        # Determine gradient class
        category_colors = {
            'technology': 'bg-technology',
            'business': 'bg-business',
            'news': 'bg-news'
        }
        gradient_class = category_colors.get(category, 'bg-default')

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Caption Slide</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        {self.shared_css}

        .caption-content-layer {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            padding: 60px;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
            z-index: 10;
        }}

        .caption-glass-card {{
            flex: 1;
            border-radius: 60px;
            background: rgba(0, 0, 0, 0.45);
            backdrop-filter: blur(60px);
            -webkit-backdrop-filter: blur(60px);
            border: 3px solid rgba(255, 255, 255, 0.15);
            padding: 54px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            box-shadow: 0 30px 90px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .caption-text {{
            font-size: 1.65rem;
            line-height: 1.6;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 400;
            overflow-wrap: break-word;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="post-container" id="post-card" style="height: {canvas_height}px;">
        <!-- Layer 1: Blurred Background -->
        <div class="bg-layer {gradient_class if not image_url else ''}">
            {f'<img src="{image_url}" onerror="this.style.display=' + "'none'" + '">' if image_url else ''}
        </div>

        <!-- Layer 2: Caption Content -->
        <div class="caption-content-layer">
            <div class="caption-glass-card">
                <div class="caption-text">{summary.caption}</div>
            </div>
        </div>
    </div>
</body>
</html>"""
        return html

    async def render_post_async(
        self,
        summary: SummaryResult,
        feed_item: FeedItem,
    ) -> Optional[tuple[Path, Path, int]]:
        """Render both post images using Playwright.

        Returns:
            Tuple of (main_filepath, caption_filepath, canvas_height) or None on failure
        """
        try:
            # Determine canvas height based on image aspect ratio
            canvas_height = await self._determine_canvas_height(feed_item.image_url)

            # Generate HTML for both images
            main_html = self._create_single_post_html(summary, feed_item, canvas_height)
            caption_html = self._create_caption_slide_html(summary, feed_item, canvas_height)

            # Generate filenames
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            item_id_short = feed_item.id[:8]
            main_filename = f"post_{timestamp}_{item_id_short}.png"
            caption_filename = f"post_{timestamp}_{item_id_short}_caption.png"
            main_filepath = GENERATED_DIR / main_filename
            caption_filepath = GENERATED_DIR / caption_filename

            # Render both with Playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Set viewport to exact dimensions
                await page.set_viewport_size({"width": self.WIDTH, "height": canvas_height})

                # Render main image
                await page.set_content(main_html)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
                await page.locator("#post-card").screenshot(path=str(main_filepath))
                logger.info(f"Saved main post image: {main_filepath}")

                # Render caption image
                await page.set_content(caption_html)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(0.5)
                await page.locator("#post-card").screenshot(path=str(caption_filepath))
                logger.info(f"Saved caption image: {caption_filepath}")

                await browser.close()

            return main_filepath, caption_filepath, canvas_height

        except Exception as e:
            logger.error(f"Failed to render post: {e}")
            return None

    def render_post(
        self,
        summary: SummaryResult,
        feed_item: FeedItem,
    ) -> Optional[tuple[Path, Path, int]]:
        """Synchronous wrapper for render_post_async."""
        try:
            # Check if there's already a running event loop
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, we can use asyncio.run()
            return asyncio.run(self.render_post_async(summary, feed_item))
        else:
            # There's already a running loop, create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.render_post_async(summary, feed_item)
                )
                return future.result()

    def create_post(
        self,
        summary: SummaryResult,
        feed_item: FeedItem,
    ) -> Optional[PostResult]:
        """Create post images and return PostResult.

        Returns:
            PostResult or None on failure
        """
        try:
            # Render both images
            result = self.render_post(summary, feed_item)

            if not result:
                return None

            main_filepath, caption_filepath, canvas_height = result

            # Use relative paths from project root
            relative_main = main_filepath.relative_to(PROJECT_ROOT)
            relative_caption = caption_filepath.relative_to(PROJECT_ROOT)

            return PostResult(
                image_path=str(relative_main).replace("\\", "/"),
                caption_image_path=str(relative_caption).replace("\\", "/"),
                height=canvas_height,
                feed_item_id=feed_item.id,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            return None

    def create_posts_for_summaries(
        self,
        summaries: list[SummaryResult],
        feed_items: list[FeedItem],
    ) -> list[PostResult]:
        """Create posts for multiple summaries.

        Args:
            summaries: List of SummaryResult objects
            feed_items: List of FeedItem objects

        Returns:
            List of PostResult objects
        """
        # Create lookup dict for feed items
        feed_items_dict = {item.id: item for item in feed_items}

        posts = []

        for i, summary in enumerate(summaries, 1):
            logger.info(f"Creating post {i}/{len(summaries)}")

            feed_item = feed_items_dict.get(summary.feed_item_id)
            if not feed_item:
                logger.warning(f"Feed item not found for summary: {summary.feed_item_id}")
                continue

            post = self.create_post(summary, feed_item)
            if post:
                posts.append(post)

        logger.info(f"Created {len(posts)} posts (each with main + caption image)")
        return posts
