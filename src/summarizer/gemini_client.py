"""Gemini API client for article summarization."""

import json
import re
import time
from typing import Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import content_types
from loguru import logger

from src.config import get_settings, get_prompt_config
from src.feeds.models import FeedItem, SummaryResult


class GeminiSummarizer:
    """Gemini-based article summarizer."""

    def __init__(self):
        self.settings = get_settings()
        self.prompt_config = get_prompt_config()

        if not self.settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")

        # Configure Gemini
        genai.configure(api_key=self.settings.gemini_api_key)

        # Get model settings
        model_settings = self.prompt_config.model_settings
        self.model_name = self.settings.gemini_model
        self.fallback_model = "gemini-3-flash-preview"  # Latest free tier model (Feb 2026)
        self.temperature = model_settings.get("temperature", 0.7)
        self.max_tokens = model_settings.get("max_tokens", 2048)

    def _get_response_schema(self):
        """Define JSON Schema for structured output with strict constraints.

        Note: Google Gemini API doesn't support minLength/maxLength, but will follow
        the constraints specified in the description and prompt.
        """
        return {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Article title (max 65 characters)"
                },
                "description": {
                    "type": "STRING",
                    "description": "Intriguing hook (170-230 characters, aim for 200)"
                },
                "caption": {
                    "type": "STRING",
                    "description": "Detailed summary in 3-4 paragraphs (1200-1400 characters total, aim for 1300)"
                },
                "hashtags": {
                    "type": "ARRAY",
                    "description": "10-15 relevant hashtags",
                    "items": {
                        "type": "STRING"
                    }
                },
                "source": {
                    "type": "STRING",
                    "description": "Clean, readable source name"
                }
            },
            "required": ["title", "description", "caption", "hashtags", "source"]
        }

    def _get_batch_response_schema(self):
        """Define JSON Schema for batch responses (array of summaries)."""
        return {
            "type": "ARRAY",
            "items": self._get_response_schema()
        }

    def _build_prompt(self, item: FeedItem) -> tuple[str, str]:
        """Build the summarization prompt for an item.

        Returns:
            Tuple of (prompt, original_title)
        """
        template = self.prompt_config.summarization_prompt

        # Get source name from feed item
        source = item.source_name or "Unknown"

        prompt = template.format(
            title=item.title,
            description=item.description or "No description available",
            category=item.category,
            source=source,
        )

        return prompt, item.title

    def _clean_text(self, text: str) -> str:
        """Remove common prefixes and artifacts from generated text."""
        if not text:
            return text

        # Remove common prefixes (case-insensitive)
        prefixes_to_remove = [
            r"^Brief Summary:\s*",
            r"^Longer Summary:\s*",
            r"^Breaking:\s*",
            r"^Breaking News:\s*",
            r"^News:\s*",
            r"^Update:\s*",
            r"^Alert:\s*",
            r"^BREAKING:\s*",
        ]

        cleaned = text
        for prefix_pattern in prefixes_to_remove:
            cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)

        # Remove emojis (comprehensive Unicode emoji ranges)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA00-\U0001FA6F"  # extended symbols
            "]+",
            flags=re.UNICODE
        )
        cleaned = emoji_pattern.sub("", cleaned)

        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _format_caption_paragraphs(self, caption: str, num_paragraphs: int = 4) -> str:
        """Split caption into paragraphs by character count target (~400 chars each)."""
        if not caption or '\n\n' in caption:
            # Already has paragraph breaks
            return caption

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', caption.strip())
        if len(sentences) <= num_paragraphs:
            return caption

        # Calculate target character count per paragraph
        target_chars = len(caption) // num_paragraphs

        paragraphs = []
        current_para = []
        current_length = 0

        for sentence in sentences:
            current_para.append(sentence)
            current_length += len(sentence)

            # Start new paragraph when target reached (but not for last para)
            if current_length >= target_chars and len(paragraphs) < num_paragraphs - 1:
                paragraphs.append(' '.join(current_para))
                current_para = []
                current_length = 0

        # Add remaining sentences to last paragraph
        if current_para:
            paragraphs.append(' '.join(current_para))

        return '\n\n'.join(paragraphs)

    def _validate_caption_balance(self, caption: str, max_deviation: float = 0.5) -> bool:
        """Check if caption paragraphs are evenly balanced.

        Args:
            caption: Caption text with paragraphs separated by \\n\\n
            max_deviation: Maximum allowed deviation from average (0.5 = 50%)

        Returns:
            True if balanced, False if any paragraph deviates too much
        """
        if not caption or '\n\n' not in caption:
            return False

        paragraphs = [p.strip() for p in caption.split('\n\n') if p.strip()]

        if len(paragraphs) < 2:
            return False

        lengths = [len(p) for p in paragraphs]
        avg_length = sum(lengths) / len(lengths)

        if avg_length < 100:  # Too short overall
            return False

        for i, length in enumerate(lengths):
            deviation = abs(length - avg_length) / avg_length
            if deviation > max_deviation:
                logger.debug(f"Paragraph {i+1} unbalanced: {length} chars (avg: {avg_length:.0f}, deviation: {deviation:.0%})")
                return False

        return True

    def _parse_response(self, response_text: str, original_title: str, feed_item_id: str) -> Optional[SummaryResult]:
        """Parse JSON response from Gemini.

        Args:
            response_text: JSON response from Gemini
            original_title: The original article title
            feed_item_id: The ID of the feed item

        Returns:
            SummaryResult or None
        """
        try:
            # Try to extract JSON from response
            # Sometimes the model wraps JSON in markdown code blocks
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.error(f"No JSON found in response: {response_text[:200]}...")
                    return None

            data = json.loads(json_str)

            # Validate and clean data
            generated_title = self._clean_text(data.get("title", ""))

            # Use original title if it's <= 65 characters, otherwise use Gemini's condensed version
            if len(original_title) <= 65:
                title = original_title[:65]
            else:
                # Original is too long, use Gemini's condensed version but ensure it's <= 65
                title = generated_title[:65]

            description = self._clean_text(data.get("description", ""))

            # Validate description length (should be 170-230 characters, aiming for ~200)
            desc_len = len(description)
            if desc_len < 170:
                logger.warning(f"Description too short ({desc_len} chars, target 170-230): {description[:100]}...")
            elif desc_len > 230:
                logger.warning(f"Description too long ({desc_len} chars, target 170-230): {description[:100]}...")

            caption = self._clean_text(data.get("caption", ""))

            # Hard truncate caption to 1400 chars (model doesn't always follow schema constraints)
            if len(caption) > 1400:
                logger.warning(f"Caption too long ({len(caption)} chars), truncating to 1400")
                # Truncate at sentence boundary if possible
                caption = caption[:1400]
                last_period = caption.rfind('.')
                if last_period > 1200:  # Keep it if we're still above minimum
                    caption = caption[:last_period + 1]
            elif len(caption) < 1200:
                logger.warning(f"Caption too short ({len(caption)} chars, target 1200-1400), skipping")
                return None

            caption = self._format_caption_paragraphs(caption)

            hashtags = data.get("hashtags", [])

            if isinstance(hashtags, str):
                hashtags = [h.strip().strip("#") for h in hashtags.split(",")]

            # Ensure hashtags are clean
            hashtags = [
                h.strip().strip("#").replace(" ", "")
                for h in hashtags
                if h.strip()
            ][:15]  # Max 15 hashtags

            source = self._clean_text(data.get("source", "Unknown"))

            return SummaryResult(
                title=title,
                description=description,
                caption=caption,
                hashtags=hashtags,
                source=source,
                feed_item_id=feed_item_id,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None

    def summarize(self, item: FeedItem, max_retries: int = 3) -> Optional[SummaryResult]:
        """Summarize a single feed item."""
        logger.info(f"Summarizing: {item.title[:50]}...")

        prompt, original_title = self._build_prompt(item)

        # Combine system message + user prompt for Gemini
        full_prompt = f"{self.prompt_config.system_message}\n\n{prompt}"

        current_model = self.model_name
        for attempt in range(max_retries):
            try:
                # Initialize model with generation config
                model = genai.GenerativeModel(
                    model_name=current_model,
                    generation_config={
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_tokens,
                    }
                )

                # Generate response
                response = model.generate_content(full_prompt)

                # Extract text from response
                response_text = response.text

                result = self._parse_response(response_text, original_title, item.id)

                if result:
                    logger.info(f"Successfully summarized: {result.title[:40]}...")
                    return result
                else:
                    logger.warning(f"Attempt {attempt + 1}: Failed to parse response")

            except google_exceptions.ResourceExhausted as e:
                # HTTP 429 - Quota exceeded
                if current_model != self.fallback_model:
                    logger.warning(f"Quota exceeded for {current_model}, switching to {self.fallback_model}")
                    current_model = self.fallback_model
                    # Retry immediately with fallback model
                    continue
                else:
                    logger.error(f"Quota exceeded even for fallback model: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Gemini API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

        logger.error(f"Failed to summarize after {max_retries} attempts")
        return None

    def summarize_items_batch(self, items: list[FeedItem], max_retries: int = 3) -> list[SummaryResult]:
        """Summarize multiple items in a single API call.

        This is more efficient and avoids rate limits by batching all items together.
        """
        if not items:
            return []

        logger.info(f"Batch summarizing {len(items)} items in a single request...")

        # Build batch prompt
        batch_prompt = self.prompt_config.system_message + "\n\n"
        batch_prompt += f"Summarize the following {len(items)} articles. Return a JSON array with {len(items)} objects.\n\n"

        for i, item in enumerate(items, 1):
            source = item.source_name or "Unknown"

            batch_prompt += f"### Article {i}\n"
            batch_prompt += f"Title: {item.title}\n"
            batch_prompt += f"Content: {item.description or 'No description available'}\n"
            batch_prompt += f"Category: {item.category}\n"
            batch_prompt += f"Source: {source}\n\n"

        batch_prompt += f"""
Return a JSON array with exactly {len(items)} objects in the same order. Each object must have:
{{
  "title": "Use EXACT original title if ≤65 chars, otherwise condense to ~60 chars",
  "description": "Intriguing hook (170-230 chars, aim for ~200)",
  "caption": "Detailed summary (no prefixes)",
  "hashtags": ["hashtag1", "hashtag2", ...10-15 hashtags],
  "source": "Clean, readable source name (e.g., 'Bloomberg', 'BBC', 'TechCrunch')"
}}

CRITICAL: Return ONLY a valid JSON array, no markdown code blocks, no extra text."""

        current_model = self.model_name
        for attempt in range(max_retries):
            try:
                # Generate batch response with JSON Schema enforcement
                model = genai.GenerativeModel(
                    model_name=current_model,
                    generation_config={
                        "temperature": self.temperature,
                        "max_output_tokens": self.max_tokens * 2,  # More tokens for batch
                        "response_mime_type": "application/json",
                        "response_schema": self._get_batch_response_schema(),
                    }
                )

                response = model.generate_content(batch_prompt)
                response_text = response.text

                # Parse batch response
                summaries = self._parse_batch_response(response_text, items)

                if summaries:
                    logger.info(f"Successfully batch summarized {len(summaries)} items")
                    return summaries
                else:
                    logger.warning(f"Attempt {attempt + 1}: Failed to parse batch response")

            except google_exceptions.ResourceExhausted as e:
                # HTTP 429 - Quota exceeded
                if current_model != self.fallback_model:
                    logger.warning(f"Quota exceeded for {current_model}, switching to {self.fallback_model}")
                    current_model = self.fallback_model
                    # Retry immediately with fallback model
                    continue
                else:
                    logger.error(f"Quota exceeded even for fallback model: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: Gemini API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        logger.error(f"Failed to batch summarize after {max_retries} attempts")
        return []

    def _parse_batch_response(self, response_text: str, items: list[FeedItem]) -> Optional[list[SummaryResult]]:
        """Parse batch JSON response from Gemini.

        Args:
            response_text: JSON array response from Gemini
            items: Original feed items for fallback titles

        Returns:
            List of SummaryResult or None
        """
        try:
            # Try to extract JSON array from response
            json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON array
                json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.error(f"No JSON array found in response: {response_text[:200]}...")
                    return None

            data_array = json.loads(json_str)

            if not isinstance(data_array, list):
                logger.error("Response is not a JSON array")
                return None

            if len(data_array) != len(items):
                logger.warning(f"Expected {len(items)} summaries, got {len(data_array)}")

            results = []
            for i, (data, item) in enumerate(zip(data_array, items)):
                # Clean and validate data
                generated_title = self._clean_text(data.get("title", ""))

                # Use original title if it's <= 65 characters
                if len(item.title) <= 65:
                    title = item.title[:65]
                else:
                    title = generated_title[:65]

                description = self._clean_text(data.get("description", ""))

                # Validate description length
                desc_len = len(description)
                if desc_len < 170:
                    logger.warning(f"Item {i+1}: Description too short ({desc_len} chars, target 170-230)")
                elif desc_len > 230:
                    logger.warning(f"Item {i+1}: Description too long ({desc_len} chars, target 170-230)")

                caption = self._clean_text(data.get("caption", ""))

                # Hard truncate caption to 1400 chars (model doesn't always follow schema constraints)
                if len(caption) > 1400:
                    logger.warning(f"Item {i+1}: Caption too long ({len(caption)} chars), truncating to 1400")
                    # Truncate at sentence boundary if possible
                    caption = caption[:1400]
                    last_period = caption.rfind('.')
                    if last_period > 1200:  # Keep it if we're still above minimum
                        caption = caption[:last_period + 1]
                elif len(caption) < 1200:
                    logger.warning(f"Item {i+1}: Caption too short ({len(caption)} chars, target 1200-1400), skipping")
                    continue

                caption = self._format_caption_paragraphs(caption)

                hashtags = data.get("hashtags", [])

                if isinstance(hashtags, str):
                    hashtags = [h.strip().strip("#") for h in hashtags.split(",")]

                # Ensure hashtags are clean
                hashtags = [
                    h.strip().strip("#").replace(" ", "")
                    for h in hashtags
                    if h.strip()
                ][:15]

                source = self._clean_text(data.get("source", "Unknown"))

                results.append(SummaryResult(
                    title=title,
                    description=description,
                    caption=caption,
                    hashtags=hashtags,
                    source=source,
                    feed_item_id=item.id,
                ))

            return results

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON array: {e}")
            logger.debug(f"Response was: {response_text[:500]}...")
            return None
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")
            return None

    def summarize_items(self, items: list[FeedItem]) -> list[SummaryResult]:
        """Summarize multiple items using batch processing."""
        return self.summarize_items_batch(items)
