import json
import os
import logging
import re
from datetime import datetime
from urllib.parse import urljoin
from typing import Dict, Any, Optional, List
from utils.html_fetcher import get_html
from services.llm_service import generate_plan
from services.parser_service import parse_dynamic_data, parse_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_data(data: List[Dict], base_url: str) -> List[Dict]:
    """
    Normalize scraped data to target format with proper field mapping and URL handling

    Args:
        data: Raw scraped data from parser
        base_url: Base URL for converting relative URLs to absolute

    Returns:
        List of normalized items in target format
    """
    normalized = []

    for item in data:
        if item.get("_item_index") is None:
            continue

        normalized_item = {
            "offerName": None,
            "actualPrice": None,
            "offerPrice": None,
            "offer": None,
            "offerImageUrl": None,
            "offerSource": None,
            "description": None,
            "rating": None,
            "ratedBy": None
        }

        # Extract and normalize offerName (product title)
        name_candidates = [
            item.get("offerName"),
            item.get("name"),
            item.get("title"),
            item.get("product_name"),
            item.get("productName"),
        ]
        for name in name_candidates:
            if name and isinstance(name, str) and name.strip():
                normalized_item["offerName"] = re.sub(r'\s+', ' ', name.strip()).strip('"\'')
                break

        # Extract and preserve original price string format (e.g., "$159.95$119.99")
        price_candidates = [
            item.get("offerPrice"),
            item.get("price"),
            item.get("current_price"),
            item.get("sale_price"),
        ]

        original_price_str = None
        for p in price_candidates:
            if p and isinstance(p, str) and p.strip():
                original_price_str = p.strip()
                break

        # Add original price if available (e.g., was $159.95 now $119.99)
        orig_price_candidates = [
            item.get("actualPrice"),
            item.get("original_price"),
            item.get("originalPrice"),
            item.get("was_price"),
        ]
        for p in orig_price_candidates:
            if p and isinstance(p, str) and p.strip():
                if original_price_str:
                    # Combine both prices: "$159.95$119.99"
                    original_price_str = f"{p.strip()}{original_price_str}"
                else:
                    original_price_str = p.strip()
                break

        # Keep original price format in offerPrice field
        if original_price_str:
            normalized_item["offerPrice"] = original_price_str

        # Also extract numeric values for calculation (for offer/discount)
        raw_prices = []
        for p in price_candidates + orig_price_candidates:
            if p and isinstance(p, str):
                price_matches = re.findall(r'[\$\£\€]?\s*(\d+[\.,]?\d*)', p)
                for match in price_matches:
                    try:
                        price_val = float(match.replace(',', '.'))
                        if price_val > 0:
                            raw_prices.append(price_val)
                    except ValueError:
                        pass

        raw_prices = list(dict.fromkeys(raw_prices))

        # Set actualPrice for internal calculations if needed
        if len(raw_prices) >= 2:
            sorted_prices = sorted(raw_prices, reverse=True)
            normalized_item["actualPrice"] = sorted_prices[0]
            # Calculate discount percentage
            if sorted_prices[0] > 0:
                discount = round(((sorted_prices[0] - sorted_prices[1]) / sorted_prices[0]) * 100)
                normalized_item["offer"] = discount
        elif len(raw_prices) == 1:
            normalized_item["actualPrice"] = raw_prices[0]

        # Extract discount percentage if present
        discount_candidates = [
            item.get("offer"),
            item.get("discount"),
            item.get("discount_percent"),
        ]
        for d in discount_candidates:
            if d and isinstance(d, str):
                match = re.search(r'(\d+)', d)
                if match:
                    normalized_item["offer"] = int(match.group(1))
                    break

        # Extract image URL
        image_candidates = [
            item.get("offerImageUrl"),
            item.get("image"),
            item.get("image_url"),
            item.get("productImage"),
            item.get("img"),
        ]
        for img in image_candidates:
            if img and isinstance(img, str) and img.strip():
                img_url = img.strip()
                if not img_url.startswith(("http://", "https://", "data:")):
                    img_url = urljoin(base_url, img_url)
                normalized_item["offerImageUrl"] = img_url
                break

        # Extract product link
        link_candidates = [
            item.get("offerSource"),
            item.get("link"),
            item.get("url"),
            item.get("productUrl"),
        ]
        for link in link_candidates:
            if link and isinstance(link, str) and link.strip():
                link_url = link.strip()
                if not link_url.startswith(("http://", "https://")):
                    link_url = urljoin(base_url, link_url)
                normalized_item["offerSource"] = link_url
                break

        # Extract description
        desc_candidates = [
            item.get("description"),
            item.get("desc"),
            item.get("details"),
            item.get("product_description"),
        ]
        for desc in desc_candidates:
            if desc and isinstance(desc, str) and desc.strip():
                normalized_item["description"] = re.sub(r'\s+', ' ', desc.strip())
                break

        # Extract rating
        rating_candidates = [
            item.get("rating"),
            item.get("stars"),
            item.get("score"),
        ]
        for rating in rating_candidates:
            if rating and isinstance(rating, str):
                match = re.search(r'(\d+(?:\.\d+)?)', rating)
                if match:
                    normalized_item["rating"] = float(match.group(1))
                    break

        # Extract review count
        review_candidates = [
            item.get("ratedBy"),
            item.get("reviews"),
            item.get("review_count"),
        ]
        for review in review_candidates:
            if review and isinstance(review, str):
                # Match number before "Ratings" or standalone number
                match = re.search(r'(\d+(?:[\d,]*))', review.replace(',', ''))
                if match:
                    normalized_item["ratedBy"] = int(match.group(1).replace(',', ''))
                    break

        # Only add items that have at least one useful field
        if normalized_item["offerName"] or normalized_item["offerPrice"] or normalized_item["offerImageUrl"] or normalized_item["offerSource"]:
            normalized.append(normalized_item)

    logger.info(f"Normalized {len(normalized)} items to target format")
    return normalized


def save_result(data: Dict[str, Any]) -> str:
    """
    Save scraping results to a JSON file

    Args:
        data: Dictionary containing scraping results

    Returns:
        Path to the saved file
    """
    os.makedirs("outputs", exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save full result
    filename = f"outputs/result_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    logger.info(f"Full results saved to {filename}")

    # Save normalized data separately if available
    if "normalized_data" in data and data["normalized_data"]:
        normalized_filename = f"outputs/normalized_{timestamp}.json"
        with open(normalized_filename, "w", encoding="utf-8") as f:
            json.dump(data["normalized_data"], f, indent=4, ensure_ascii=False)
        logger.info(f"Normalized data saved to {normalized_filename}")

    return filename


def analyze_url_complexity(url: str) -> Dict[str, bool]:
    """
    Analyze URL to determine if it's likely to have dynamic content

    Args:
        url: Website URL

    Returns:
        Dictionary with complexity flags
    """
    complexity_flags = {
        "is_dynamic": False,
        "needs_pagination": False,
        "is_spa": False,  # Single Page Application
        "has_query_params": False,
        "is_ecommerce": False
    }

    url_lower = url.lower()

    # Check for common SPA patterns
    spa_patterns = ['#!', '#/', '#!/', '?_escaped_fragment_=']
    for pattern in spa_patterns:
        if pattern in url:
            complexity_flags["is_spa"] = True
            complexity_flags["is_dynamic"] = True

    # Check for query parameters (common in dynamic sites)
    if '?' in url and '=' in url:
        complexity_flags["has_query_params"] = True

    # Check for common dynamic site indicators
    dynamic_keywords = ['search', 'filter', 'sort', 'page', 'ajax', 'api', 'product', 'shop', 'store', 'catalog']
    for keyword in dynamic_keywords:
        if keyword in url_lower:
            complexity_flags["is_dynamic"] = True

    # Check for e-commerce indicators (likely to have pagination)
    ecommerce_keywords = ['product', 'shop', 'store', 'catalog', 'category', 'collection', 'sale', 'offer']
    for keyword in ecommerce_keywords:
        if keyword in url_lower:
            complexity_flags["is_ecommerce"] = True
            complexity_flags["needs_pagination"] = True

    # Check for pagination indicators
    pagination_keywords = ['page=', 'p=', 'pg=', 'start=', 'offset=', 'limit=']
    for keyword in pagination_keywords:
        if keyword in url_lower:
            complexity_flags["needs_pagination"] = True

    # Modern web frameworks - assume dynamic
    modern_frameworks = ['react', 'angular', 'vue', 'next', 'nuxt', 'svelte']
    for fw in modern_frameworks:
        if fw in url_lower:
            complexity_flags["is_dynamic"] = True

    logger.info(f"URL complexity analysis for {url}: {complexity_flags}")
    return complexity_flags


def run_ai_scraper(
    url: str, 
    instruction: str,
    dynamic_mode: Optional[bool] = None,
    pagination: bool = False,
    max_pages: int = 3,
    timeout: int = 60000
) -> Dict[str, Any]:
    """
    Enhanced AI scraper with dynamic content support
    
    Args:
        url: Website URL to scrape
        instruction: Natural language instruction for what to scrape
        dynamic_mode: Whether to use dynamic fetcher (auto-detected if None)
        pagination: Whether to handle paginated content
        max_pages: Maximum number of pages to scrape (if pagination enabled)
        timeout: Timeout in milliseconds for page loading
    
    Returns:
        Dictionary with scraping results
    """
    try:
        logger.info(f"Starting AI scraper for URL: {url}")
        logger.info(f"Instruction: {instruction}")
        
        # Step 0: Analyze URL complexity
        complexity = analyze_url_complexity(url)
        
        # Determine dynamic mode if not specified
        if dynamic_mode is None:
            dynamic_mode = complexity["is_dynamic"] or complexity["is_spa"]
        
        # Determine pagination if not specified
        if pagination is False:
            pagination = complexity["needs_pagination"]
        
        logger.info(f"Configuration - Dynamic: {dynamic_mode}, Pagination: {pagination}")
        
        # Step 1: Fetch HTML with appropriate configuration
        logger.info("Fetching HTML content...")
        html = get_html(
            url=url,
            dynamic=dynamic_mode,
            pagination=pagination,
            max_pages=max_pages if pagination else 1
        )
        
        if not html or len(html.strip()) < 100:
            raise ValueError(f"Failed to fetch meaningful content from {url}")
        
        logger.info(f"Fetched {len(html)} characters of HTML")
        
        # Step 2: Generate AI scraping plan
        logger.info("Generating AI scraping plan...")
        plan = generate_plan(html, instruction)
        logger.info(f"AI plan generated: {json.dumps(plan, indent=2)}")
        
        # Step 3: Extract data using the plan
        logger.info("Parsing data with generated selectors...")
        parsed_result = parse_dynamic_data(html, plan)
        data = parsed_result.get("data", [])
        metadata = parsed_result.get("metadata", {})
        logger.info(f"Extracted {len(data)} items with success rate: {metadata.get('success_rate', 0)}%")
        
        # Step 4: Normalize data to target format
        logger.info("Normalizing data to target format...")
        normalized_data = normalize_data(data, url)

        # Step 5: Prepare result
        result = {
            "url": url,
            "instruction": instruction,
            "configuration": {
                "dynamic_mode": dynamic_mode,
                "pagination": pagination,
                "max_pages": max_pages if pagination else 1,
                "timeout": timeout,
                "complexity_analysis": complexity
            },
            "plan": plan,
            "data": data,
            "normalized_data": normalized_data,
            "metadata": metadata,
            "summary": {
                "total_items": len(data),
                "normalized_items": len(normalized_data),
                "successful_items": sum(1 for item in data if any(item.values())),
                "fields_extracted": metadata.get("fields_extracted", []),
                "success_rate": metadata.get("success_rate", 0)
            }
        }
        
        # Step 4: Save to file
        logger.info("Saving results to file...")
        file_path = save_result(result)
        
        # Prepare API response
        response_data = {
            "message": "Scraping completed successfully ✅",
            "status": "success",
            "file_saved": file_path,
            "summary": result["summary"],
            "configuration": result["configuration"],
            "plan": plan,
            "data_sample": data[:5] if data else [],
            "normalized_sample": normalized_data[:5] if normalized_data else [],
            "total_items": len(data),
            "normalized_count": len(normalized_data)
        }
        
        logger.info(f"Scraping completed. Extracted {len(data)} items.")
        return response_data
        
    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}", exc_info=True)
        
        # Fallback: Try with simple static fetch
        try:
            logger.info("Attempting fallback with static fetch...")
            html = get_html(url=url, dynamic=False, pagination=False)
            if html and len(html) > 1000:
                plan = generate_plan(html, instruction)
                data = parse_data(html, plan)
                
                result = {
                    "url": url,
                    "instruction": instruction,
                    "plan": plan,
                    "data": data
                }
                
                file_path = save_result(result)
                
                return {
                    "message": "Scraping completed with fallback mode ⚠️",
                    "status": "fallback",
                    "file_saved": file_path,
                    "plan": plan,
                    "data_sample": data[:10] if data else [],
                    "total_items": len(data),
                    "warning": f"Dynamic scraping failed, used static mode: {str(e)}"
                }
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
        
        # Return error response
        return {
            "message": "Scraping failed ❌",
            "status": "error",
            "error": str(e),
            "url": url,
            "instruction": instruction,
            "suggestion": "Try a simpler URL or check if the site requires authentication"
        }