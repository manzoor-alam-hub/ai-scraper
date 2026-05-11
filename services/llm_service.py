import os
import json
import re
import logging
from google import genai
from google.genai import Client

try:
    import streamlit as st
    # Use Streamlit secrets on cloud
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
except:
    # Fallback for local development without streamlit
    from dotenv import load_dotenv
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Gemini client
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None


def load_prompt():
    """Load the scraping prompt template"""
    import sys
    import os

    # Try multiple possible paths for the prompt file
    possible_paths = [
        "prompts/scraper_prompt.txt",
        os.path.join(os.path.dirname(__file__), "..", "prompts", "scraper_prompt.txt"),
        "/mount/src/ai-scraper/prompts/scraper_prompt.txt"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    # If no file found, use a minimal default prompt
    return DEFAULT_PROMPT

DEFAULT_PROMPT = '''
You are an expert web scraper. Extract product data from this HTML based on the instruction.

Instruction: {instruction}

HTML: {html}

Return JSON with fields: offerName, offerPrice, offerImageUrl, offerSource, description
'''


def extract_json(text):
    """Extract and fix JSON from Gemini response"""
    try:
        text = re.sub(r"```json|```", "", text).strip()
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")

        json_text = text[start_idx:end_idx + 1]
        json_text = re.sub(r',\s*}', '}', json_text)
        json_text = re.sub(r',\s*]', ']', json_text)

        json.loads(json_text)
        return json_text

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        try:
            json_text = re.sub(r'//.*?\n', '', json_text)
            json_text = re.sub(r'/\*.*?\*/', '', json_text, flags=re.DOTALL)
            json.loads(json_text)
            return json_text
        except:
            raise ValueError(f"Could not extract valid JSON from response: {str(e)}")


def _infer_fields_from_instruction(instruction):
    """
    Infer which fields to extract based on keywords in the instruction.
    Works with ANY website - detects what user wants and extracts those fields.

    Returns fields mapped to target format names with comprehensive selectors.
    """
    instruction_lower = instruction.lower()
    fields = {}

    # === PRODUCT/NAME FIELD ===
    # Look for name, title, product name in instruction
    if any(word in instruction_lower for word in ['name', 'title', 'product', 'item', 'brand']):
        fields['offerName'] = (
            "h1, h2, h3, h4, "
            "[class*='name'], "
            "[class*='title'], "
            "[class*='product'], "
            "[class*='heading'], "
            "[data-testid*='name'], "
            "[data-testid*='title'], "
            "a[class*='name'], "
            "[itemprop='name'], "
            ".product-title, "
            ".item-name"
        )

    # === PRICE FIELD (REQUIRED for product validation) ===
    if any(word in instruction_lower for word in ['price', 'cost', 'amount', '$', 'sale', 'discount']):
        fields['offerPrice'] = (
            "[class*='price'], "
            "[class*='cost'], "
            "[class*='sale'], "
            "[class*='amount'], "
            "[data-testid*='price'], "
            "[itemprop='price'], "
            "span[class*='price'], "
            "div[class*='price'], "
            ".current-price, "
            ".sale-price, "
            ".special-price, "
            "[data-price]"
        )

        # Original price (was/strikethrough)
        fields['actualPrice'] = (
            "[class*='original'], "
            "[class*='was'], "
            "[class*='regular'], "
            "del, "
            "s[class*='price'], "
            "[class*='strike'], "
            "[itemprop='price'], "
            ".old-price, "
            ".list-price, "
            ".was-price"
        )

    # === DISCOUNT FIELD ===
    if any(word in instruction_lower for word in ['discount', 'off', 'save', '%', 'percent', 'deal']):
        fields['offer'] = (
            "[class*='discount'], "
            "[class*='save'], "
            "[class*='off'], "
            "[class*='deal'], "
            "[class*='sale'], "
            "span:contains('%'), "
            "[data-discount], "
            ".discount-badge, "
            ".sale-badge"
        )

    # === IMAGE FIELD ===
    if any(word in instruction_lower for word in ['image', 'picture', 'photo', 'img', 'thumbnail']):
        fields['offerImageUrl'] = (
            "img[src]:not([src*='logo']):not([src*='icon']):not([src*='placeholder']), "
            "picture img, "
            "[class*='image'] img, "
            "[class*='photo'] img, "
            "[class*='product'] img, "
            "[data-testid*='image'], "
            "[data-src], "
            "[data-lazy], "
            "[itemprop='image'], "
            ".product-image img, "
            ".item-image img"
        )

    # === LINK/SOURCE FIELD ===
    if any(word in instruction_lower for word in ['link', 'url', 'source', 'href', 'product page']):
        fields['offerSource'] = (
            "a[href]:not([href^='javascript']):not([href^='#']):not([href^='mailto']),"
            "a[href*='product'], "
            "a[href*='item'], "
            "a[href*='/p/'], "
            "a[href*='pid='], "
            "[class*='product'] a, "
            "h1 a, h2 a, h3 a, "
            "[itemprop='url'], "
            ".product-link a, "
            ".item-link a"
        )

    # === DESCRIPTION FIELD ===
    if any(word in instruction_lower for word in ['description', 'desc', 'details', 'info', 'spec', 'specs']):
        fields['description'] = (
            "p[class*='desc'], "
            "div[class*='description'], "
            "div[class*='details'], "
            "div[class*='detail'], "
            "span[class*='desc'], "
            "[class*='summary'], "
            "[itemprop='description'], "
            "[data-testid*='description'], "
            ".product-desc, "
            ".product-description"
        )

    # === RATING FIELD ===
    if any(word in instruction_lower for word in ['rating', 'star', 'score', 'review']):
        fields['rating'] = (
            "[class*='rating'], "
            "[class*='star'], "
            "[class*='score'], "
            "[data-testid*='rating'], "
            "[aria-label*='rating'], "
            "[itemprop='rating'], "
            ".stars, "
            ".rating-value"
        )

    # === REVIEW COUNT FIELD ===
    if any(word in instruction_lower for word in ['review', 'reviews', 'rated', 'feedback']):
        fields['ratedBy'] = (
            "[class*='review'], "
            "[class*='count'], "
            "[data-testid*='review'], "
            "[aria-label*='review'], "
            "[itemprop='review'], "
            "span:contains('review'), "
            "a:contains('review'), "
            ".review-count, "
            ".reviews-count"
        )

    # === DEFAULT FIELDS (if no specific fields detected) ===
    # Try to extract whatever looks like products
    if not fields:
        logger.info("No specific fields requested, using default product fields")
        fields = {
            "offerName": (
                "h1, h2, h3, h4, "
                "[class*='name'], [class*='title'], [class*='product'], "
                "a[href*='product'], a[href*='item'], [itemprop='name']"
            ),
            "offerPrice": (
                "[class*='price'], [class*='cost'], [class*='amount'], "
                "span[class*='price'], [data-price], [itemprop='price']"
            ),
            "offerImageUrl": (
                "img[src]:not([src*='logo']):not([src*='icon']), "
                "picture img, [class*='image'] img, [data-src], [itemprop='image']"
            ),
            "offerSource": (
                "a[href]:not([href^='javascript']):not([href^='#']):not([href^='/']), "
                "[class*='product'] a, [itemprop='url']"
            ),
            "description": (
                "p, div[class*='desc'], div[class*='description'], [itemprop='description']"
            ),
            "rating": (
                "[class*='rating'], [class*='star'], [aria-label*='rating'], [itemprop='ratingValue']"
            ),
            "ratedBy": (
                "[class*='review'], [class*='count'], [aria-label*='review'], [itemprop='reviewCount']"
            )
        }

    return fields


def generate_plan(html, instruction):
    """
    Generate scraping plan using AI with enhanced error handling.

    Focuses on main content area, excludes sidebar/nav/ads.
    Uses semantic understanding + CSS selectors for robust extraction.
    """
    try:
        if client is None:
            raise ValueError("GEMINI_API_KEY is not configured. Please set it in Streamlit secrets.")

        prompt_template = load_prompt()

        # Truncate HTML if too long (Gemini has token limits)
        html_preview = html[:15000]

        prompt = prompt_template.format(
            instruction=instruction,
            html=html_preview
        )

        logger.info(f"Generating AI plan for instruction: {instruction[:100]}...")
        logger.debug(f"HTML preview length: {len(html_preview)} chars")

        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "thinking_config": {
                    "thinking_budget": 1024
                }
            }
        )

        logger.info("AI response received, extracting JSON...")

        # Extract and parse JSON
        json_text = extract_json(response.text)
        plan = json.loads(json_text)

        # Validate plan structure
        if not isinstance(plan, dict):
            raise ValueError("AI response is not a dictionary")

        # Ensure required fields exist with fallbacks
        if "container" not in plan:
            plan["container"] = "div[class*='item'], div[class*='product'], article"

        if "fields" not in plan:
            plan["fields"] = _infer_fields_from_instruction(instruction)

        # Handle main_content_area - use it to scope container search
        if "main_content_area" not in plan:
            plan["main_content_area"] = None  # Will be detected by parser

        # Add dynamic_notes if missing
        if "dynamic_notes" not in plan:
            plan["dynamic_notes"] = {
                "framework_detected": "Unknown",
                "main_area_found": False,
                "items_in_main_area": "unknown",
                "recommendations": "Using semantic filtering for product identification"
            }

        logger.info(f"AI plan generated successfully: container={plan.get('container')}, fields={list(plan.get('fields', {}).keys())}")
        return plan

    except Exception as e:
        logger.error(f"❌ Gemini failed: {str(e)}")
        logger.info("Using fallback scraping plan")

        # Enhanced fallback using semantic understanding
        return {
            "main_content_area": "main, section[class*='main'], section[class*='content'], section[class*='products']",
            "container": "div[class*='item'], div[class*='product'], article, div[role='listitem']",
            "fields": _infer_fields_from_instruction(instruction),
            "exclude_containers": ["aside", "[class*='sidebar']", "[class*='related']", "[class*='recommended']"],
            "ai_extraction_hints": {
                "how_to_find_products": "Look for elements with name + price + image. Products must have price.",
                "price_pattern": r'[\$\£\€]\s*\d+[\.,]?\d*',
                "name_pattern": "Title-case text, product names typically 3+ words"
            },
            "dynamic_notes": {
                "framework_detected": "Unknown",
                "main_area_found": True,
                "items_in_main_area": "10-50 expected",
                "sidebar_excluded": True,
                "recommendations": "Using semantic filtering for product identification"
            }
        }


def analyze_html_complexity(html):
    """
    Analyze HTML to detect dynamic content patterns
    
    Args:
        html: HTML content to analyze
    
    Returns:
        Dictionary with complexity analysis
    """
    complexity = {
        "is_dynamic": False,
        "has_react": False,
        "has_vue": False,
        "has_angular": False,
        "has_data_attrs": False,
        "has_aria_attrs": False,
        "script_tags": 0,
        "div_count": 0,
        "classless_elements": 0
    }
    
    # Check for React
    if 'react' in html.lower() or 'react-' in html or '__react' in html:
        complexity["has_react"] = True
        complexity["is_dynamic"] = True
    
    # Check for Vue
    if 'vue' in html.lower() or 'v-' in html or '__vue' in html:
        complexity["has_vue"] = True
        complexity["is_dynamic"] = True
    
    # Check for Angular
    if 'ng-' in html or 'angular' in html.lower():
        complexity["has_angular"] = True
        complexity["is_dynamic"] = True
    
    # Check for data attributes
    if 'data-' in html:
        complexity["has_data_attrs"] = True
    
    # Check for ARIA attributes
    if 'aria-' in html:
        complexity["has_aria_attrs"] = True
    
    # Count script tags
    complexity["script_tags"] = html.count('<script')
    
    # Count div elements (common in dynamic frameworks)
    complexity["div_count"] = html.count('<div')
    
    # Count elements without classes (common in component frameworks)
    classless_pattern = r'<(\w+)(?![^>]*\bclass\b)[^>]*>'
    complexity["classless_elements"] = len(re.findall(classless_pattern, html, re.IGNORECASE))
    
    # Determine if likely dynamic
    if (complexity["has_react"] or complexity["has_vue"] or complexity["has_angular"] or 
        complexity["script_tags"] > 10 or complexity["classless_elements"] > 50):
        complexity["is_dynamic"] = True
    
    return complexity