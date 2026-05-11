import asyncio
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DynamicFetcher:
    """Enhanced fetcher for dynamic and complex JavaScript websites"""
    
    def __init__(self, headless: bool = True, timeout: int = 60000):
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials'
            ]
        )
        self.page = await self.browser.new_page()
        
        # Set user agent to mimic real browser
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Bypass bot detection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
    
    async def fetch_with_retry(self, url: str, max_retries: int = 3) -> str:
        """Fetch HTML with retry logic for unreliable connections"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1}/{max_retries})")
                
                # Navigate with network idle detection
                await self.page.goto(
                    url, 
                    timeout=self.timeout,
                    wait_until='networkidle'  # Wait for network to be mostly idle
                )
                
                # Wait for dynamic content to load
                await self._wait_for_dynamic_content()
                
                # Get the fully rendered HTML
                html = await self.page.content()
                
                # Check if we got meaningful content
                if len(html) < 1000 and "javascript" in html.lower():
                    logger.warning("Page may not have loaded properly, trying additional wait")
                    await self.page.wait_for_timeout(5000)
                    html = await self.page.content()
                
                logger.info(f"Successfully fetched {len(html)} characters")
                return html
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def _wait_for_dynamic_content(self):
        """Wait for various dynamic content patterns"""
        # Wait for common dynamic content indicators
        selectors_to_wait = [
            'div[class*="product"]',
            'div[class*="item"]',
            'div[class*="card"]',
            'article',
            'section',
            'ul li',
            'table',
            'img[src]'
        ]
        
        for selector in selectors_to_wait[:3]:  # Try first few selectors
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                logger.debug(f"Found selector: {selector}")
                break
            except:
                continue
        
        # Additional wait for JavaScript execution
        await self.page.wait_for_timeout(2000)
        
        # Scroll to trigger lazy loading
        await self._scroll_page()
    
    async def _scroll_page(self):
        """Scroll page to trigger lazy loading and infinite scroll"""
        try:
            # Get page height
            page_height = await self.page.evaluate("document.body.scrollHeight")
            
            # Scroll in increments
            scroll_step = 500
            current_position = 0
            
            while current_position < page_height:
                await self.page.evaluate(f"window.scrollTo(0, {current_position})")
                await self.page.wait_for_timeout(500)  # Wait for content to load
                current_position += scroll_step
                
                # Check if page height increased (infinite scroll)
                new_height = await self.page.evaluate("document.body.scrollHeight")
                if new_height > page_height:
                    page_height = new_height
            
            # Scroll back to top
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.warning(f"Scrolling failed: {e}")
    
    async def handle_pagination(self, url: str, max_pages: int = 3) -> str:
        """Handle paginated content by loading multiple pages with various pagination patterns"""
        all_html_parts = []

        for page_num in range(1, max_pages + 1):
            try:
                # First page: try URL construction, subsequent pages: try "Next" button first
                if page_num == 1:
                    # Try URL construction for first page
                    paginated_url = self._construct_paginated_url(url, page_num)
                    logger.info(f"Fetching page {page_num}: {paginated_url}")
                    await self.page.goto(paginated_url, wait_until='networkidle', timeout=30000)
                else:
                    # Try clicking "Next" or "Load More" button first
                    clicked = await self._try_click_pagination_button()
                    if clicked:
                        logger.info(f"Clicked pagination button for page {page_num}")
                        await self.page.wait_for_timeout(3000)
                    else:
                        # Fallback to URL construction
                        paginated_url = self._construct_paginated_url(url, page_num)
                        logger.info(f"No button found, trying URL: {paginated_url}")
                        await self.page.goto(paginated_url, wait_until='networkidle', timeout=30000)
                        await self.page.wait_for_timeout(3000)

                # Scroll to trigger lazy loading
                await self._scroll_page()

                html = await self.page.content()
                all_html_parts.append(f"<!-- Page {page_num} -->\n{html}")
                logger.info(f"Page {page_num} fetched, HTML length: {len(html)}")

                # Check if there's a next page button
                has_next = await self._has_next_page()
                if not has_next:
                    logger.info("No next page button found, stopping pagination")
                    break

            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                break

        return "\n".join(all_html_parts)

    async def _try_click_pagination_button(self) -> bool:
        """Try to click pagination buttons (Next, Load More, Show More, etc.)"""
        button_selectors = [
            # Next buttons
            'a[rel="next"]',
            'a:contains("Next")',
            'button:contains("Next")',
            'button:contains("next")',
            'li.next a',
            'li[class*="next"] a',
            # Load More buttons
            'button:contains("Load More")',
            'button:contains("Show More")',
            'button:contains("View More")',
            'a:contains("Load More")',
            'a:contains("Show More")',
            '[class*="load-more"] button',
            '[class*="load-more"] a',
            '[data-testid*="load-more"]',
            '[data-testid*="LoadMore"]',
            # Infinite scroll trigger
            '[class*="infinite"]',
            # Pagination links
            '.pagination a',
            '[class*="pagination"] a',
            'nav[aria-label="pagination"] a',
        ]

        for selector in button_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.click()
                        await self.page.wait_for_timeout(2000)
                        return True
            except:
                continue
        return False

    async def _has_next_page(self) -> bool:
        """Check if there's a next page available"""
        # Check various pagination patterns
        selectors = [
            'a[rel="next"]',
            'button:contains("Next")',
            'a:contains("Next")',
            'button:contains("Load More")',
            'button:contains("Show More")',
            '[class*="load-more"]',
            'li.next a',
            '.pagination .next a',
            '[aria-label="next page"]',
            '[rel="next"]'
        ]

        for selector in selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        return True
            except:
                continue
        return False
    
    def _construct_paginated_url(self, base_url: str, page_num: int) -> str:
        """Construct paginated URL based on common patterns"""
        import urllib.parse
        
        # Handle different pagination patterns
        if '?' in base_url:
            # URL already has query parameters
            parsed = urllib.parse.urlparse(base_url)
            query = urllib.parse.parse_qs(parsed.query)
            
            # Common pagination parameters
            pagination_params = ['page', 'p', 'pg', 'start', 'offset']
            for param in pagination_params:
                if param in query:
                    query[param] = [str(page_num)]
                    break
            else:
                # Add page parameter
                query['page'] = [str(page_num)]
            
            new_query = urllib.parse.urlencode(query, doseq=True)
            return urllib.parse.urlunparse(parsed._replace(query=new_query))
        else:
            # Simple URL, add page parameter
            separator = '&' if '?' in base_url else '?'
            return f"{base_url}{separator}page={page_num}"

async def fetch_dynamic(url: str, handle_pagination: bool = False, max_pages: int = 3) -> str:
    """
    Fetch HTML from dynamic JavaScript websites with enhanced capabilities

    Args:
        url: Website URL to scrape
        handle_pagination: Whether to handle paginated content
        max_pages: Maximum number of pages to fetch (if pagination enabled)

    Returns:
        HTML content as string
    """
    async with DynamicFetcher() as fetcher:
        if handle_pagination and max_pages > 1:
            return await fetcher.handle_pagination(url, max_pages)
        else:
            return await fetcher.fetch_with_retry(url)

def get_html(url: str, dynamic: bool = True, pagination: bool = False, max_pages: int = 1) -> str:
    """
    Main function to get HTML content

    Args:
        url: Website URL
        dynamic: Use enhanced dynamic fetcher (default: True)
        pagination: Handle pagination (default: False)
        max_pages: Maximum number of pages to fetch (default: 1)

    Returns:
        HTML content
    """
    if dynamic or pagination:
        # Use Playwright for both dynamic and pagination cases
        return asyncio.run(fetch_dynamic(url, handle_pagination=pagination, max_pages=max_pages))
    else:
        # Fallback to simple fetch for static sites
        async def simple_fetch():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=60000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                await browser.close()
                return html
        return asyncio.run(simple_fetch())