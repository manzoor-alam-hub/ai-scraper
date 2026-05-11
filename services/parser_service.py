from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_likely_product(item) -> bool:
    """
    AI-based semantic check to determine if an element is likely a product.
    Products typically have: name (heading/link) + price + image.
    Sidebar items often lack 2+ of these.
    """
    if item is None:
        return False

    # Get text content
    text = item.get_text(strip=True)
    if not text or len(text) < 20:
        return False

    # Check for price (strong indicator of product)
    has_price = False
    price_text = ""
    price_patterns = [
        r'[\$£\€]\s*\d+[\.,]?\d*',
        r'\d+\s*[\$£\€]',
        r'(?:price|cost|amount)[:\s]+\d+',
    ]
    for pattern in price_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            has_price = True
            price_text = match.group(0)
            break

    if not has_price:
        return False

    # Check for product name (heading or link with substantial text)
    has_name = False
    name_patterns = [
        r'h[1-4]',  # Heading tags
        r'class=["\'][^"\']*(?:name|title|product|item)[^"\']*["\']',
        r'class=["\'][^"\']*(?:product-name|productName|item-name)[^"\']*["\']',
    ]
    for pattern in name_patterns:
        if re.search(pattern, str(item), re.IGNORECASE):
            has_name = True
            break

    # Check for link with product-like href
    links = item.find_all('a', href=True)
    for link in links:
        href = link.get('href', '')
        # Product links often contain: product, item, p/, /product/, etc.
        if any(kw in href.lower() for kw in ['product', 'item', '/p/', 'pid=', 'sku=']):
            has_name = True
            break
        # Or link text looks like product name
        link_text = link.get_text(strip=True)
        if len(link_text) > 10 and not any(nav in link_text.lower() for nav in ['menu', 'home', 'about', 'contact', 'login', 'cart']):
            has_name = True
            break

    # Check for image
    has_image = False
    images = item.find_all('img')
    for img in images:
        src = img.get('src', '') or img.get('data-src', '')
        if src and not any(bad in src.lower() for bad in ['logo', 'icon', 'placeholder', 'spacer', 'clear']):
            if len(src) > 20:  # Real image URLs are longer
                has_image = True
                break

    # Product should have at least 2 of: name, image, substantial text content
    text_words = len(text.split())
    indicators = sum([has_name, has_image, text_words > 15])

    return indicators >= 2


def _is_sidebar_container(container) -> bool:
    """Check if a container is likely a sidebar (should be excluded)"""
    container_str = str(container).lower()

    # Check for sidebar indicators in class names
    sidebar_indicators = [
        'sidebar', 'aside', 'related', 'recommended', 'popular',
        'trending', 'featured', 'recent', 'similar', 'you-might',
        'bestseller', 'most-popular', 'top-rated', 'also-like'
    ]

    for indicator in sidebar_indicators:
        if indicator in container_str:
            return True

    # Check for navigation/header/footer parent elements
    parent_tags = ['nav', 'header', 'footer', 'aside']
    for tag in parent_tags:
        if container.find_parent(tag):
            return True

    return False


def _get_main_content_area(soup: BeautifulSoup) -> Optional:
    """Find the main content area, excluding sidebar/nav/footer"""
    # Try semantic HTML first
    main = soup.find('main')
    if main:
        logger.info("Found <main> element as primary content area")
        return main

    # Try common patterns for main product area
    main_selectors = [
        'section[class*="main"]',
        'section[class*="content"]',
        'section[class*="products"]',
        'section[class*="catalog"]',
        'section[class*="collection"]',
        'div[class*="main"]',
        'div[class*="content"]',
        'div[id*="main"]',
        'div[id*="content"]',
        'div[class*="product-grid"]',
        'div[class*="products-grid"]',
        'div[class*="catalog"]',
        'article',
    ]

    for selector in main_selectors:
        elements = soup.select(selector)
        for elem in elements:
            # Skip if it's a sidebar
            if _is_sidebar_container(elem):
                continue
            # Check if it has many items (likely main content)
            items = elem.find_all(['div', 'li', 'article'], recursive=False)
            if len(items) >= 5:
                logger.info(f"Found main content area with selector: {selector}")
                return elem

    # Fallback: find the largest grid/list structure
    grids = soup.find_all(['div', 'section'], class_=lambda x: x and any(x in str(x).lower() for x in ['grid', 'list', 'row']))
    for grid in grids:
        if not _is_sidebar_container(grid):
            direct_children = len(grid.find_all(['div', 'li', 'article'], recursive=False))
            if direct_children >= 10:
                return grid

    logger.warning("Could not identify main content area, using full page")
    return soup


def parse_data(html: str, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse HTML data using the AI-generated plan with enhanced dynamic content support.
    Focuses on MAIN product content, ignoring sidebar/navigation/ads.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Extract container and fields from plan
        container = plan.get("container", "div[class*='item'], div[class*='product'], article")
        fields = plan.get("fields", {})

        if not fields:
            logger.warning("No fields defined in plan, using default fields")
            fields = {
                "title": "h1, h2, h3, [class*='title']",
                "content": "p, div[class*='content']"
            }

        # Get main content area first (ignore sidebar/nav/footer)
        main_area = _get_main_content_area(soup)
        if main_area:
            logger.info(f"Using main content area: {type(main_area).__name__}")

        # Try primary container selector in main area
        items = _find_items(main_area or soup, container)

        if not items:
            logger.warning(f"No items found with primary selector: {container}")
            logger.info("Trying alternative container selectors...")
            alternative_containers = [
                "div[class*='card']",
                "div[class*='item']",
                "article",
                "div[role='listitem']",
                "div[data-testid*='item']",
                "li",
                "tr"
            ]

            for alt_container in alternative_containers:
                items = _find_items(main_area or soup, alt_container)
                if items:
                    logger.info(f"Found {len(items)} items with alternative selector: {alt_container}")
                    container = alt_container
                    break

        if not items:
            logger.error("No items found with any container selector")
            return []

        logger.info(f"Found {len(items)} candidate items, filtering for products...")

        # Filter items using semantic product identification
        product_items = []
        for item in items:
            if _is_likely_product(item):
                product_items.append(item)

        logger.info(f"Filtered to {len(product_items)} likely products")

        if not product_items:
            # If semantic filter removed everything, fall back to all items
            logger.warning("Semantic filter removed all items, using all candidates")
            product_items = items

        results = []
        max_items = 50

        for idx, item in enumerate(product_items[:max_items]):
            try:
                row = _extract_item_data(item, fields, idx)
                if row:
                    results.append(row)
            except Exception as e:
                logger.warning(f"Failed to parse item {idx}: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(results)} items")
        return results

    except Exception as e:
        logger.error(f"Parsing failed: {str(e)}", exc_info=True)
        return []


def _find_items(soup: BeautifulSoup, container_selector: str) -> List:
    """
    Find items using container selector with fallback strategies
    """
    try:
        items = soup.select(container_selector)
        
        # If selector returns too many items (might be too generic), try to filter
        if len(items) > 100:
            logger.warning(f"Selector '{container_selector}' returned {len(items)} items, may be too generic")
            # Try to filter to only items that look like content containers
            filtered_items = []
            for item in items:
                # Check if item has some content
                text = item.get_text(strip=True)
                if text and len(text) > 10:
                    filtered_items.append(item)
            
            if filtered_items:
                items = filtered_items[:100]  # Limit to 100
        
        return items
        
    except Exception as e:
        logger.warning(f"Selector '{container_selector}' failed: {str(e)}")
        return []


def _normalize_field_name(field_name: str) -> str:
    """Normalize field names to target format"""
    field_mapping = {
        'name': 'offerName',
        'title': 'offerName',
        'product_name': 'offerName',
        'productName': 'offerName',
        'price': 'offerPrice',
        'current_price': 'offerPrice',
        'sale_price': 'offerPrice',
        'offer_price': 'offerPrice',
        'original_price': 'actualPrice',
        'originalPrice': 'actualPrice',
        'was_price': 'actualPrice',
        'list_price': 'actualPrice',
        'image': 'offerImageUrl',
        'image_url': 'offerImageUrl',
        'productImage': 'offerImageUrl',
        'link': 'offerSource',
        'url': 'offerSource',
        'productUrl': 'offerSource',
        'href': 'offerSource',
        'desc': 'description',
        'product_description': 'description',
        'discount': 'offer',
        'offer_percent': 'offer',
        'discount_percent': 'offer',
        'stars': 'rating',
        'score': 'rating',
        'review_count': 'ratedBy',
        'reviews': 'ratedBy'
    }
    return field_mapping.get(field_name, field_name)


def _extract_item_data(item, fields: Dict[str, str], item_index: int) -> Dict[str, Any]:
    """
    Extract data from a single item using field selectors, with normalized field names
    """
    row = {"_item_index": item_index}
    
    for field_name, selector in fields.items():
        try:
            # Handle multiple selectors separated by commas
            selectors = [s.strip() for s in selector.split(',')]
            
            value = None
            for sel in selectors[:3]:  # Try first 3 selectors
                try:
                    element = item.select_one(sel)
                    if element:
                        value = _extract_value_from_element(element, field_name)
                        if value:
                            break
                except Exception:
                    continue
            
            # If no value found with selectors, try to find by common patterns
            if not value and field_name in ["title", "name", "offerName", "productName"]:
                # Try heading tags first
                value = _find_by_pattern(item, ["h1", "h2", "h3", "h4"])
                # If still no value, look for text inside anchor tags with product links
                if not value:
                    links = item.find_all("a")
                    for link in links:
                        href = link.get("href", "")
                        if "product" in href.lower():
                            text = link.get_text(strip=True)
                            if text and len(text) > 2:
                                value = text
                                break

            if not value and field_name in ["price", "cost", "offerPrice"]:
                value = _find_price(item)

            if not value and field_name in ["original_price", "actualPrice", "originalPrice"]:
                value = _find_original_price(item)

            if not value and field_name in ["description", "content", "desc"]:
                value = _find_description(item)

            if not value and field_name in ["image", "image_url", "offerImageUrl", "productImage"]:
                value = _find_image(item)

            if not value and field_name in ["link", "url", "offerSource", "productUrl"]:
                value = _find_link(item)

            if not value and field_name in ["rating", "stars", "score"]:
                value = _find_rating(item)

            if not value and field_name in ["reviews", "review_count", "ratedBy"]:
                value = _find_review_count(item)

            if not value and field_name in ["discount", "offer", "offer_percent"]:
                value = _find_discount(item)
            
            row[field_name] = value
            
        except Exception as e:
            logger.debug(f"Failed to extract field '{field_name}': {str(e)}")
            row[field_name] = None
    
    # Remove empty rows (where all fields are None)
    if all(v is None for k, v in row.items() if k != "_item_index"):
        return {}
    
    return row


def _extract_value_from_element(element, field_name: str) -> Optional[str]:
    """
    Extract value from element based on field type
    """
    try:
        # For images, get src attribute
        if field_name in ["image", "image_url", "img", "offerImageUrl", "productImage"] and element.name == "img":
            src = element.get("src", "") or element.get("data-src", "") or element.get("data-lazy", "")
            if src and not src.startswith("data:"):
                return src

        # For links, get href attribute
        if field_name in ["link", "url", "href", "offerSource", "productUrl"] and element.name == "a":
            href = element.get("href", "")
            if href and not href.startswith(("javascript:", "#")):
                return href

        # For other elements, get text with cleaning
        text = element.get_text(strip=True)

        # Clean text based on field type
        if field_name in ["price", "cost", "amount", "offerPrice", "actualPrice"]:
            # Keep the full text for later price parsing
            return text.strip()

        if field_name in ["rating", "stars", "score"]:
            # Extract rating (e.g., 4.5, 5 stars)
            rating_match = re.search(r'(\d+(?:[\.,]\d*)?)', text)
            if rating_match:
                return rating_match.group(1)

        # Default: return cleaned text
        if text:
            # Remove extra whitespace and normalize
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        # Try to get value attribute for form elements
        value_attr = element.get("value")
        if value_attr:
            return str(value_attr).strip()

        return None

    except Exception:
        return None


def _find_by_pattern(item, tag_names: List[str]) -> Optional[str]:
    """Find text by tag names"""
    for tag in tag_names:
        element = item.find(tag)
        if element:
            text = element.get_text(strip=True)
            if text:
                return text
    return None


def _find_price(item) -> Optional[str]:
    """Find price using common patterns"""
    # Look for elements with price-related classes
    price_selectors = [
        "[class*='price']",
        "[class*='cost']",
        "[class*='amount']",
        "[data-testid*='price']",
        "[data-qa*='price']",
        "span:contains('$')",
        "span:contains('€')",
        "span:contains('£')"
    ]
    
    for selector in price_selectors:
        try:
            element = item.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                price_match = re.search(r'[\$\£\€]?\s*\d+[\.,]?\d*', text)
                if price_match:
                    return price_match.group(0).strip()
        except:
            continue
    
    return None


def _find_description(item) -> Optional[str]:
    """Find description text"""
    # Try common description elements
    desc_selectors = [
        "p",
        "div[class*='description']",
        "div[class*='content']",
        "span[class*='desc']",
        "[data-testid*='description']"
    ]
    
    descriptions = []
    for selector in desc_selectors:
        try:
            elements = item.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 10 and len(text) < 500:
                    descriptions.append(text)
        except:
            continue
    
    if descriptions:
        # Return the longest description
        return max(descriptions, key=len)
    
    return None


def _find_image(item) -> Optional[str]:
    """Find image URL"""
    img_selectors = [
        "img[src]",
        "img[data-src]",
        "picture img",
        "[class*='image'] img",
        "[data-testid*='image']"
    ]
    
    for selector in img_selectors:
        try:
            element = item.select_one(selector)
            if element:
                src = element.get("src") or element.get("data-src")
                if src and not src.startswith("data:"):  # Skip data URIs
                    return src
        except:
            continue
    
    return None


def _find_link(item) -> Optional[str]:
    """Find link URL"""
    link_selectors = [
        "a[href]",
        "[class*='link']",
        "[data-testid*='link']",
        "[href]:not([href^='javascript:']):not([href^='#'])"
    ]

    for selector in link_selectors:
        try:
            element = item.select_one(selector)
            if element:
                href = element.get("href")
                if href and not href.startswith(("javascript:", "#")):
                    return href
        except:
            continue

    return None


def _find_original_price(item) -> Optional[str]:
    """Find original/strikethrough price"""
    price_selectors = [
        "del",
        "[class*='original']",
        "[class*='was']",
        "[class*='list-price']",
        "[class*='strike']",
        "[class*='regular-price']",
        "[class*='original-price']",
        "span[class*='was']",
        "span[class*='original']"
    ]

    for selector in price_selectors:
        try:
            element = item.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                price_match = re.search(r'[\$\£\€]?\s*\d+[\.,]?\d*', text)
                if price_match:
                    return price_match.group(0).strip()
        except:
            continue

    return None


def _find_rating(item) -> Optional[str]:
    """Find rating score"""
    rating_selectors = [
        "[class*='rating']",
        "[class*='star']",
        "[class*='score']",
        "[data-testid*='rating']",
        "[aria-label*='rating']",
        "[aria-label*='star']"
    ]

    for selector in rating_selectors:
        try:
            element = item.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                rating_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:\/|out of)?\s*(\d+)?', text)
                if rating_match:
                    return rating_match.group(1)
                # Also check aria-label
                aria = element.get("aria-label", "")
                rating_match = re.search(r'(\d+(?:\.\d+)?)', aria)
                if rating_match:
                    return rating_match.group(1)
        except:
            continue

    return None


def _find_review_count(item) -> Optional[str]:
    """Find review count"""
    review_selectors = [
        "[class*='review']",
        "[class*='count']",
        "[data-testid*='review']",
        "[data-qa*='review']",
        "span:contains('review')",
        "[aria-label*='review']"
    ]

    for selector in review_selectors:
        try:
            element = item.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                count_match = re.search(r'(\d+(?:[\d,]*))', text)
                if count_match:
                    return count_match.group(1).replace(',', '')
        except:
            continue

    return None


def _find_discount(item) -> Optional[str]:
    """Find discount percentage"""
    discount_selectors = [
        "[class*='discount']",
        "[class*='save']",
        "[class*='off']",
        "[class*='offer']",
        "[class*='percent']",
        "span:contains('%')",
        "[data-testid*='discount']"
    ]

    for selector in discount_selectors:
        try:
            elements = item.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                discount_match = re.search(r'(\d+)%?\s*(?:off|save)?', text, re.IGNORECASE)
                if discount_match:
                    return discount_match.group(1)
        except:
            continue

    return None


def parse_dynamic_data(html: str, plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced parser for dynamic content with additional metadata
    
    Args:
        html: HTML content
        plan: AI-generated scraping plan
    
    Returns:
        Dictionary with data and metadata
    """
    data = parse_data(html, plan)
    
    result = {
        "data": data,
        "metadata": {
            "total_items": len(data),
            "fields_extracted": list(data[0].keys()) if data else [],
            "success_rate": _calculate_success_rate(data) if data else 0,
            "plan_used": {
                "container": plan.get("container"),
                "fields": list(plan.get("fields", {}).keys())
            }
        }
    }
    
    # Add dynamic notes if present in plan
    if "dynamic_notes" in plan:
        result["metadata"]["dynamic_notes"] = plan["dynamic_notes"]
    
    return result


def _calculate_success_rate(data: List[Dict]) -> float:
    """Calculate success rate of data extraction"""
    if not data:
        return 0.0
    
    total_fields = 0
    successful_fields = 0
    
    for item in data:
        for key, value in item.items():
            if key != "_item_index":
                total_fields += 1
                if value is not None:
                    successful_fields += 1
    
    return round(successful_fields / total_fields * 100, 2) if total_fields > 0 else 0.0