import asyncio
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_with_httpx(url: str) -> str:
    """Fetch HTML using httpx (works on Streamlit Cloud)"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            logger.info(f"Fetched {len(response.text)} characters from {url}")
            return response.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        raise


def get_html(url: str, dynamic: bool = True, pagination: bool = False, max_pages: int = 1) -> str:
    """
    Main function to get HTML content.
    Uses httpx for HTTP fetching (compatible with Streamlit Cloud).
    """

    # Try httpx first (works everywhere)
    try:
        html = asyncio.run(fetch_with_httpx(url))
        if html and len(html) > 100:
            return html
    except Exception as e:
        logger.warning(f"httpx fetch failed: {e}")

    # Fallback - return a minimal HTML
    logger.error(f"Could not fetch {url}")
    return "<html><body><p>Failed to fetch URL</p></body></html>"
