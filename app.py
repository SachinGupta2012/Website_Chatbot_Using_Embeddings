import streamlit as st
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from src.crawler import WebsiteCrawler
from src.embeddings import EmbeddingsManager
from src.chatbot import WebsiteChatbot

st.set_page_config(
    page_title="Website Chatbot (Groq)",
    page_icon="⚡",
    layout="centered"
)

# Session State
if 'chatbot' not in st.session_state:
    st.session_state.chatbot = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'indexing_done' not in st.session_state:
    st.session_state.indexing_done = False

st.title("⚡ Website Chatbot with Groq")
st.markdown("Fast RAG using **Llama 3.3 70B** via Groq API")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    groq_key = st.text_input(
        "Groq API Key", 
        type="password",
        help="Get free key at console.groq.com",
        value=os.getenv("GROQ_API_KEY", "")
    )
    
    model_choice = st.selectbox(
        "Model",
        ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        index=0
    )
    
    st.divider()
    
    # NEW: JavaScript toggle for sites like GeeksforGeeks
    use_js = st.checkbox(
        "Use JavaScript Rendering", 
        value=False,
        help="Enable for JavaScript-heavy sites (GeeksforGeeks, Medium, etc.). Slower but more reliable."
    )
    
    if use_js:
        st.info("⚠️ Selenium mode: First run will download ChromeDriver (~10MB)")
    
    st.divider()
    
    st.subheader("Text Processing")
    chunk_size = st.slider("Chunk Size", 500, 2000, 1000)
    chunk_overlap = st.slider("Overlap", 0, 500, 200)
    
    st.divider()
    
    if st.session_state.indexing_done:
        if st.button("🗑️ Clear Memory"):
            st.session_state.chat_history = []
            if st.session_state.chatbot:
                st.session_state.chatbot.clear_memory()
            st.rerun()
        
        if st.button("🔄 New Website"):
            st.session_state.chatbot = None
            st.session_state.chat_history = []
            st.session_state.indexing_done = False
            st.rerun()

# Main UI
st.divider()
col1, col2 = st.columns([3, 1])

with col1:
    url = st.text_input(
        "Website URL",
        placeholder="https://www.geeksforgeeks.org/array-data-structure/",
        disabled=st.session_state.indexing_done
    )

with col2:
    index_btn = st.button(
        "⚡ Crawl & Index", 
        type="primary", 
        disabled=not url or st.session_state.indexing_done,
        use_container_width=True
    )

if index_btn:
    if not groq_key:
        st.error("⚠️ Enter Groq API Key in sidebar!")
    else:
        progress = st.progress(0)
        status = st.empty()
        
        try:
            # Initialize crawler with JS support if enabled
            status.text("Initializing crawler...")
            if use_js:
                status.text("Setting up Chrome WebDriver...")
            progress.progress(10)
            
            crawler = WebsiteCrawler(use_selenium=use_js)
            
            # Crawl
            status.text("Crawling website...")
            progress.progress(30)
            
            data = crawler.fetch_content(url)
            
            if not data['success']:
                st.error(f"❌ {data['error']}")
                if "JavaScript" in data['error']:
                    st.info("💡 Tip: Enable 'Use JavaScript Rendering' in the sidebar for this site.")
                st.stop()
            
            method = data.get('method', 'requests')
            status.text(f"Extracted {data['length']} chars ({method})...")
            progress.progress(60)
            
            # Embeddings
            embed_manager = EmbeddingsManager(chunk_size, chunk_overlap)
            vector_store = embed_manager.create_vector_store(data)
            
            # Initialize Chatbot
            status.text(f"Loading {model_choice}...")
            progress.progress(80)
            
            st.session_state.chatbot = WebsiteChatbot(
                vector_store=vector_store,
                groq_api_key=groq_key,
                model_name=model_choice
            )
            
            st.session_state.indexing_done = True
            progress.progress(100)
            status.empty()
            progress.empty()
            
            st.success(f"✅ Indexed: {data['title']}")
            st.caption(f"Method: {method} | Chunks: {len(embed_manager.vector_store.docstore._docs)}")
            
        except Exception as e:
            status.empty()
            progress.empty()
            st.error(f"Error: {str(e)}")

# Chat Interface
if st.session_state.indexing_done:
    st.divider()
    st.subheader("💬 Ask Questions")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if q := st.chat_input("Ask about the website..."):
        st.session_state.chat_history.append({"role": "user", "content": q})
        
        with st.chat_message("user"):
            st.markdown(q)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                ans = st.session_state.chatbot.ask(q)
                st.markdown(ans)
                st.session_state.chat_history.append({"role": "assistant", "content": ans})
else:
    st.info("👆 Enter URL and click 'Crawl & Index'")
    
    # Tips
    with st.expander("📝 Tips for best results"):
        st.markdown("""
        **For static sites (Wikipedia, docs):**
        - Keep "JavaScript Rendering" disabled (faster)
        
        **For dynamic sites (GeeksforGeeks, Medium):**
        - Enable "JavaScript Rendering" 
        - First run downloads ChromeDriver automatically
        
        **Recommended test URLs:**
        - `https://en.wikipedia.org/wiki/Python_(programming_language)`
        - `https://www.geeksforgeeks.org/array-data-structure/` (needs JS)
        """)

st.divider()
st.caption("Built with LangChain + Groq + Selenium + FAISS")