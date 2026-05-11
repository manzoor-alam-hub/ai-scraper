import streamlit as st
import requests
import json

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
    
    # Prepare request payload
    payload = {
        "url": url,
        "instruction": instruction,
        "timeout": timeout * 1000  # Convert to milliseconds
    }
    
    # Add dynamic mode configuration
    if dynamic_mode == "enabled":
        payload["dynamic_mode"] = True
    elif dynamic_mode == "disabled":
        payload["dynamic_mode"] = False
    # "auto" means don't include the field (let backend decide)
    
    if pagination:
        payload["pagination"] = True
        payload["max_pages"] = max_pages
    
    # Show configuration
    with st.expander("📋 Request Configuration", expanded=True):
        st.json(payload)
    
    # Make API request
    with st.spinner("🔄 Scraping in progress..."):
        try:
            res = requests.post(
                "http://127.0.0.1:8000/scrape",
                json=payload,
                timeout=timeout + 30  # Add buffer for processing
            )
            
            # Display results
            st.subheader("📊 Results")
            
            if res.status_code == 200:
                try:
                    data = res.json()
                    
                    # Display success message
                    st.success(data.get("message", "Scraping completed!"))
                    
                    # Show summary
                    if "summary" in data:
                        summary = data["summary"]
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Items", summary.get("total_items", 0))
                        with col2:
                            st.metric("Success Rate", f"{summary.get('success_rate', 0)}%")
                        with col3:
                            st.metric("Status", data.get("status", "unknown"))
                    
                    # Show configuration used
                    if "configuration" in data:
                        with st.expander("⚙️ Configuration Used"):
                            st.json(data["configuration"])
                    
                    # Show AI plan
                    if "plan" in data:
                        with st.expander("🤖 AI-Generated Scraping Plan"):
                            st.json(data["plan"])
                    
                    # Show data sample
                    if "data_sample" in data and data["data_sample"]:
                        st.subheader("📋 Extracted Data (Sample)")
                        st.dataframe(data["data_sample"], use_container_width=True)
                        
                        # Show download button for full data
                        if "file_saved" in data:
                            st.info(f"Full data saved to: `{data['file_saved']}`")
                            
                            # Try to load and offer download
                            try:
                                with open(data["file_saved"], "r", encoding="utf-8") as f:
                                    json_data = f.read()
                                
                                st.download_button(
                                    label="📥 Download Full JSON",
                                    data=json_data,
                                    file_name="scraped_data.json",
                                    mime="application/json"
                                )
                            except:
                                pass
                    else:
                        st.warning("No data extracted. The selectors may not have matched any elements.")
                    
                    # Show metadata if available
                    if "metadata" in data:
                        with st.expander("📈 Extraction Metadata"):
                            st.json(data["metadata"])
                    
                    # Show raw response in debug mode
                    if debug_mode:
                        with st.expander("🔍 Raw Response"):
                            st.code(json.dumps(data, indent=2), language="json")
                    
                except json.JSONDecodeError:
                    st.error("Failed to parse JSON response")
                    st.code(res.text)
            else:
                st.error(f"API Error: {res.status_code}")
                st.text("Response:")
                st.code(res.text)
                
        except requests.exceptions.Timeout:
            st.error(f"Request timed out after {timeout + 30} seconds. Try increasing the timeout.")
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to the API server. Make sure the backend is running.")
            st.code("Start the backend with: uvicorn app.main:app --reload")
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Health check
if st.sidebar.button("🔍 Check API Health", type="secondary"):
    try:
        health_res = requests.get("http://127.0.0.1:8000/health", timeout=5)
        if health_res.status_code == 200:
            st.sidebar.success("✅ API is healthy")
            st.sidebar.json(health_res.json())
        else:
            st.sidebar.error(f"API returned {health_res.status_code}")
    except:
        st.sidebar.error("❌ Cannot connect to API")

# Configuration info
if st.sidebar.button("📋 Show Default Config", type="secondary"):
    try:
        config_res = requests.get("http://127.0.0.1:8000/config", timeout=5)
        if config_res.status_code == 200:
            st.sidebar.json(config_res.json())
    except:
        st.sidebar.error("Cannot fetch configuration")

# Footer
st.markdown("---")
st.caption("""
**AI Scraper Tool v2.0** - Now with enhanced dynamic content support for JavaScript websites (React, Angular, Vue, etc.)
""")