# AI Web Scraper

An intelligent web scraping tool that uses AI to automatically detect and extract product data from e-commerce websites.

## Features

- **AI-Powered Plan Generation** - Uses Google Gemini to analyze HTML and create optimal scraping selectors
- **Dynamic Content Support** - Handles JavaScript-rendered pages with Playwright
- **Smart Product Detection** - Identifies main product areas while excluding sidebars/navigation
- **Normalized Output** - Standardizes extracted data into a consistent format
- **Pagination Support** - Automatically handles multi-page scraping
- **REST API** - FastAPI backend for programmatic access
- **Web UI** - Streamlit interface for easy use

## Tech Stack

- **FastAPI** - Web framework
- **Playwright** - Dynamic content rendering
- **BeautifulSoup** - HTML parsing
- **Google Gemini** - AI for scraping plan generation
- **Streamlit** - User interface
- **Pydantic** - Data validation

## Installation

```bash
pip install -r requirements.txt
playwright install
```

## Configuration

Create a `.env` file with your API key:

```
GEMINI_API_KEY=your_gemini_api_key
```

## Usage

### Web Interface (Recommended)

```bash
streamlit run ui/app.py
```

### API Server

```bash
uvicorn app.main:app --reload
```

API endpoints:
- `GET /` - Health check
- `POST /scrape` - Scrape a URL with instructions

## Test URLs

| URL | Description |
|-----|-------------|
| [https://www.softwalkshoes.com/sale](https://www.softwalkshoes.com/sale) | E-commerce sale page |
| [https://books.toscrape.com/](https://books.toscrape.com/) | Books catalog for scraping practice |

## Deploy to Streamlit Cloud

1. Push this code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Deploy!

Note: For Streamlit Cloud, you'll need to set the `GEMINI_API_KEY` in Secrets.