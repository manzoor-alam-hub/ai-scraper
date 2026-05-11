import streamlit as st
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.scraper_service import run_ai_scraper

st.set_page_config(page_title="AI Scraper Tool", page_icon="🧠", layout="wide")

st.title("🧠 AI Scraper Tool - Dynamic Content Support")
st.markdown("""
This tool uses AI to scrape data from websites, including dynamic JavaScript sites (React, Angular, Vue, etc.).
""")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")

    st.subheader("Dynamic Content Settings")
    dynamic_mode = st.selectbox(
        "Dynamic Mode",
        ["auto", "enabled", "disabled"],
        help="Auto: Detect dynamic content automatically\nEnabled: Force dynamic mode\nDisabled: Use static mode"
    )

    pagination = st.checkbox(
        "Handle Pagination",
        value=False,
        help="Enable to scrape multiple pages (if detected)"
    )

    if pagination:
        max_pages = st.slider(
            "Max Pages",
            min_value=1,
            max_value=10,
            value=3,
            help="Maximum number of pages to scrape"
        )
    else:
        max_pages = 1

    timeout = st.slider(
        "Timeout (seconds)",
        min_value=10,
        max_value=300,
        value=60,
        help="Page load timeout in seconds"
    )

    st.subheader("Advanced Options")
    debug_mode = st.checkbox("Debug Mode", value=False)

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 Scraping Parameters")

    # Initialize session state for URL
    if "url_input" not in st.session_state:
        st.session_state["url_input"] = ""

    url = st.text_input(
        "Enter Website URL",
        value=st.session_state["url_input"],
        placeholder="https://example.com/products",
        help="Enter the full URL of the website to scrape"
    )

    # Test URLs buttons
    st.subheader("🧪 Test URLs")
    st.markdown("Click to auto-fill:")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("👟 SoftWalk Shoes (Sale)", use_container_width=True):
            st.session_state["url_input"] = "https://www.softwalkshoes.com/sale"
            st.rerun()

    with c2:
        if st.button("📚 Books to Scrape", use_container_width=True):
            st.session_state["url_input"] = "https://books.toscrape.com/"
            st.rerun()

    instruction = st.text_area(
        "What do you want to scrape?",
        placeholder="Example: Extract product names, prices, and ratings",
        help="Describe in natural language what data you want to extract"
    )

    examples = st.expander("📋 Example Instructions")
    with examples:
        st.markdown("""
        **E-commerce:**
        - "Get product names, prices, and images"
        - "Extract book titles, authors, and prices"
        - "Scrape customer reviews with ratings and dates"

        **News/Blogs:**
        - "Extract article titles, summaries, and publication dates"
        - "Get news headlines with links"
        - "Scrape blog post titles and authors"

        **Social Media:**
        - "Extract post content, likes, and comments count"
        - "Get user profiles with names and bios"
        """)

with col2:
    st.subheader("ℹ️ Tips for Dynamic Sites")
    st.info("""
    **For JavaScript-heavy sites:**
    - Enable Dynamic Mode
    - Increase timeout for slow-loading sites
    - Use pagination for multi-page content

    **Common dynamic sites:**
    - React/Angular/Vue applications
    - Single Page Applications (SPA)
    - Infinite scroll pages
    - Lazy-loaded content

    **Troubleshooting:**
    - If scraping fails, try increasing timeout
    - Check browser console for errors
    - Verify the site doesn't block bots
    """)

# Run scraper button
if st.button("🚀 Run Scraper", type="primary", use_container_width=True):
    if not url:
        st.error("Please enter a URL")
        st.stop()

    if not instruction:
        st.error("Please enter scraping instructions")
        st.stop()

    # Prepare parameters
    dynamic_mode_param = None
    if dynamic_mode == "enabled":
        dynamic_mode_param = True
    elif dynamic_mode == "disabled":
        dynamic_mode_param = False

    timeout_ms = timeout * 1000

    # Show configuration
    config_display = {
        "url": url,
        "instruction": instruction,
        "dynamic_mode": dynamic_mode if dynamic_mode == "auto" else dynamic_mode_param,
        "pagination": pagination,
        "max_pages": max_pages,
        "timeout_ms": timeout_ms
    }

    with st.expander("📋 Request Configuration", expanded=True):
        st.json(config_display)

    # Run scraper directly (no API call needed)
    with st.spinner("🔄 Scraping in progress... This may take a minute."):
        try:
            result = run_ai_scraper(
                url=url,
                instruction=instruction,
                dynamic_mode=dynamic_mode_param,
                pagination=pagination,
                max_pages=max_pages,
                timeout=timeout_ms
            )

            # Display results
            st.subheader("📊 Results")

            if result.get("status") == "success" or result.get("status") == "fallback":
                # Display success message
                st.success(result.get("message", "Scraping completed!"))

                # Show summary
                if "summary" in result:
                    summary = result["summary"]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Items", summary.get("total_items", 0))
                    with col2:
                        st.metric("Success Rate", f"{summary.get('success_rate', 0)}%")
                    with col3:
                        st.metric("Status", result.get("status", "unknown"))

                # Show configuration used
                if "configuration" in result:
                    with st.expander("⚙️ Configuration Used"):
                        st.json(result["configuration"])

                # Show AI plan
                if "plan" in result:
                    with st.expander("🤖 AI-Generated Scraping Plan"):
                        st.json(result["plan"])

                # Show data sample
                data_sample = result.get("data_sample", result.get("data", []))
                if data_sample:
                    st.subheader("📋 Extracted Data (Sample)")
                    st.dataframe(data_sample[:10], use_container_width=True)

                    # Show download button for full data
                    normalized_data = result.get("normalized_sample", result.get("normalized_data", []))

                    if normalized_data:
                        st.download_button(
                            label="📥 Download Full JSON",
                            data=json.dumps(normalized_data, indent=2),
                            file_name="scraped_data.json",
                            mime="application/json"
                        )
                    elif data_sample:
                        st.download_button(
                            label="📥 Download Full JSON",
                            data=json.dumps(data_sample, indent=2),
                            file_name="scraped_data.json",
                            mime="application/json"
                        )
                else:
                    st.warning("No data extracted. The selectors may not have matched any elements.")

                # Show metadata if available
                if "metadata" in result:
                    with st.expander("📈 Extraction Metadata"):
                        st.json(result["metadata"])

                # Show raw response in debug mode
                if debug_mode:
                    with st.expander("🔍 Raw Response"):
                        st.code(json.dumps(result, indent=2), language="json")

            else:
                st.error(f"Scraping failed: {result.get('message', 'Unknown error')}")
                if "error" in result:
                    st.code(str(result["error"]))

        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("If you're running this on Streamlit Cloud, the site may be blocking requests or requires a longer timeout.")

# Footer
st.markdown("---")
st.caption("""
**AI Scraper Tool v2.0** - Now with enhanced dynamic content support for JavaScript websites (React, Angular, Vue, etc.)
""")