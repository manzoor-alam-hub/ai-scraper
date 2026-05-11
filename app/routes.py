from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from services.scraper_service import run_ai_scraper

router = APIRouter()


class RequestModel(BaseModel):
    """Request model for scraping with dynamic content support"""
    url: str = Field(..., description="Website URL to scrape")
    instruction: str = Field(..., description="Natural language instruction for what to scrape")
    dynamic_mode: Optional[bool] = Field(
        None, 
        description="Whether to use dynamic fetcher (auto-detected if None)"
    )
    pagination: Optional[bool] = Field(
        False, 
        description="Whether to handle paginated content"
    )
    max_pages: Optional[int] = Field(
        3, 
        description="Maximum number of pages to scrape (if pagination enabled)",
        ge=1, 
        le=20
    )
    timeout: Optional[int] = Field(
        60000, 
        description="Timeout in milliseconds for page loading",
        ge=10000, 
        le=300000
    )


@router.post("/scrape")
def scrape(req: RequestModel):
    """Scrape data from URL using AI-generated selectors"""
    try:
        result = run_ai_scraper(
            url=req.url,
            instruction=req.instruction,
            dynamic_mode=req.dynamic_mode,
            pagination=req.pagination,
            max_pages=req.max_pages,
            timeout=req.timeout
        )
        return result
    except Exception as e:
        return {
            "error": str(e),
            "status": "failed",
            "suggestion": "Try adjusting parameters or check if the site requires authentication"
        }


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "AI Scraper"}


@router.get("/config")
def get_default_config():
    """Get default configuration for scraping"""
    return {
        "default_configuration": {
            "dynamic_mode": "auto (detected from URL)",
            "pagination": False,
            "max_pages": 3,
            "timeout_ms": 60000,
            "features": {
                "javascript_rendering": True,
                "bot_detection_bypass": True,
                "lazy_loading": True,
                "infinite_scroll": True,
                "spa_support": True
            }
        },
        "recommendations": {
            "dynamic_sites": ["React", "Angular", "Vue", "Next.js", "Nuxt.js", "Svelte"],
            "use_dynamic_mode": True,
            "use_pagination": "When URL contains page parameters or site has pagination controls"
        }
    }