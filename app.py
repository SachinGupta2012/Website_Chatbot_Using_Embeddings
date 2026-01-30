import streamlit as st
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))
from src.crawler import WebsiteCrawler
from src.embeddings import EmbeddingsManager
from src.chatbot import WebsiteChatbot

# Page config
st.set_page_config(
    page_title="Website RAG Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
defaults = {
    'chatbot': None,
    'vector_store': None,  # Store separately for persistence
    'chat_history': [],
    'indexing_done': False,
    'current_url': None,
    'current_title': None,
    'index_path': "./saved_index",
    'crawled_data': None
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

st.title("🤖 Website-Based RAG Chatbot")
st.markdown("Crawl any website, index it with embeddings, and chat with it using **Groq LLM**")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # API Key
    groq_key = st.text_input(
        "Groq API Key", 
        type="password",
        help="Get free key at console.groq.com",
        value=os.getenv("GROQ_API_KEY", "")
    )
    
    # Model Selection
    model = st.selectbox(
        "LLM Model",
        options=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma-7b-it"
        ],
        index=0,
        help="70B = highest quality, 8B = fastest"
    )
    
    st.divider()
    
    # Crawling Options
    st.subheader("🕷️ Crawling Options")
    
    use_js = st.toggle(
        "Use JavaScript Rendering",
        value=False,
        help="Enable for React/SPA sites (GeeksforGeeks, Medium). Slower but handles dynamic content."
    )
    
    if use_js:
        st.info("⚠️ Will use Chrome Selenium (first run downloads ~10MB)")
    
    # Text Processing
    st.divider()
    st.subheader("📝 Text Processing")
    
    col1, col2 = st.columns(2)
    with col1:
        chunk_size = st.number_input("Chunk Size", 500, 2000, 1000, step=100)
    with col2:
        chunk_overlap = st.number_input("Overlap", 0, 500, 200, step=50)
    
    # Memory Management
    st.divider()
    st.subheader("💾 Session Management")
    
    if st.session_state.indexing_done:
        st.success(f"✅ Indexed: {str(st.session_state.current_title)[:30]}...")
        
        if st.button("🔄 Index New Website", type="primary", use_container_width=True):
            st.session_state.chatbot = None
            st.session_state.vector_store = None
            st.session_state.chat_history = []
            st.session_state.indexing_done = False
            st.session_state.current_url = None
            st.session_state.current_title = None
            st.rerun()
        
        if st.button("🗑️ Clear Chat Memory", use_container_width=True):
            st.session_state.chat_history = []
            if st.session_state.chatbot:
                st.session_state.chatbot.clear_memory()
            st.rerun()
    
    # Vector Store Persistence
    st.divider()
    if st.session_state.indexing_done and st.session_state.vector_store:
        if st.button("💾 Save Index to Disk", use_container_width=True):
            try:
                os.makedirs(st.session_state.index_path, exist_ok=True)
                st.session_state.vector_store.save_local(st.session_state.index_path)
                st.success("Index saved! ✅")
            except Exception as e:
                st.error(f"Save failed: {e}")

# Main Area
tab1, tab2 = st.tabs(["🌐 Index Website", "💬 Chat Interface"])

with tab1:
    st.subheader("Step 1: Enter Website URL")
    
    url_col, btn_col = st.columns([4, 1])
    
    with url_col:
        url = st.text_input(
            "Website URL",
            placeholder="https://en.wikipedia.org/wiki/Artificial_intelligence",
            disabled=st.session_state.indexing_done,
            label_visibility="collapsed"
        )
    
    with btn_col:
        crawl_btn = st.button(
            "🚀 Crawl & Index", 
            type="primary",
            disabled=not url or st.session_state.indexing_done,
            use_container_width=True
        )
    
    # Load existing index option
    if not st.session_state.indexing_done:
        st.divider()
        st.subheader("Or Load Existing Index")
        if st.button("📂 Load Saved Index", use_container_width=True):
            try:
                embed_manager = EmbeddingsManager(chunk_size, chunk_overlap)
                vector_store = embed_manager.load_vector_store(st.session_state.index_path)
                
                if not groq_key:
                    st.error("Enter Groq API key first!")
                else:
                    # Initialize chatbot with loaded index
                    st.session_state.chatbot = WebsiteChatbot(
                        vector_store=vector_store,
                        groq_api_key=groq_key,
                        model_name=model
                    )
                    st.session_state.vector_store = vector_store
                    st.session_state.indexing_done = True
                    st.session_state.current_url = "Loaded from disk"
                    st.session_state.current_title = "Saved Index"
                    st.success("Index loaded successfully! ✅")
                    st.rerun()
            except Exception as e:
                st.error(f"No saved index found: {e}")
    
    # Crawling Process
    if crawl_btn:
        if not groq_key:
            st.error("⚠️ Please enter Groq API Key in sidebar!")
        else:
            progress = st.progress(0, text="Initializing...")
            status = st.empty()
            
            try:
                # Step 1: Initialize
                status.info("🕷️ Initializing crawler...")
                progress.progress(10)
                
                crawler = WebsiteCrawler(use_selenium=use_js)
                
                # Step 2: Fetch
                status.info("📡 Fetching website content...")
                progress.progress(30)
                
                data = crawler.fetch_content(url)
                
                if not data['success']:
                    st.error(f"❌ Crawling failed: {data['error']}")
                    if "JavaScript" in data['error'] and not use_js:
                        st.info("💡 **Tip**: Enable 'Use JavaScript Rendering' in sidebar for this site")
                    st.stop()
                
                method = data.get('method', 'requests')
                st.session_state.crawled_data = data
                
                # Step 3: Process
                status.info(f"✂️ Chunking {data['length']:,} characters...")
                progress.progress(50)
                
                embed_manager = EmbeddingsManager(chunk_size, chunk_overlap)
                vector_store = embed_manager.create_vector_store(data)
                
                # Get chunk count safely (handle different FAISS versions)
                try:
                    chunk_count = len(vector_store.docstore._dict)
                except AttributeError:
                    try:
                        chunk_count = len(vector_store.docstore._docs)
                    except:
                        chunk_count = vector_store.index.ntotal if hasattr(vector_store, 'index') else "Unknown"
                
                # Store vector store in session state
                st.session_state.vector_store = vector_store
                
                # Step 4: Initialize LLM
                status.info(f"🤖 Initializing {model}...")
                progress.progress(80)
                
                st.session_state.chatbot = WebsiteChatbot(
                    vector_store=vector_store,
                    groq_api_key=groq_key,
                    model_name=model
                )
                
                # Complete
                st.session_state.indexing_done = True
                st.session_state.current_url = url
                st.session_state.current_title = data['title']
                
                progress.progress(100)
                status.empty()
                
                st.success(f"✅ **{data['title']}** indexed successfully!")
                st.balloons()
                
                # Metadata display
                meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
                with meta_col1:
                    st.metric("Method", method.upper())
                with meta_col2:
                    st.metric("Characters", f"{data['length']:,}")
                with meta_col3:
                    st.metric("Chunks", chunk_count)
                with meta_col4:
                    st.metric("Model", model.split('-')[0].upper())
                
                st.info("👇 Switch to 'Chat Interface' tab to start asking questions")
                
            except Exception as e:
                progress.empty()
                status.empty()
                st.error(f"❌ Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

with tab2:
    if not st.session_state.indexing_done:
        st.info("👈 Please index a website in the 'Index Website' tab first")
        
        # Example suggestions
        st.subheader("📝 Try these example URLs:")
        examples = [
            ("Wikipedia - Python", "https://en.wikipedia.org/wiki/Python_(programming_language)"),
            ("GeeksforGeeks - Arrays", "https://www.geeksforgeeks.org/array-data-structure/"),
            ("Python Docs", "https://docs.python.org/3/tutorial/index.html")
        ]
        for name, ex_url in examples:
            st.code(f"{name}: {ex_url}", language="text")
    
    else:
        # Chat Interface
        st.subheader("💬 Chat with the Website")
        
        # Info banner
        st.caption(f"**Source**: {str(st.session_state.current_url)[:100]}{'...' if len(str(st.session_state.current_url)) > 100 else ''}")
        
        # Chat container
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        
        # Input
        if prompt := st.chat_input("Ask a question about the website...", key="chat_input"):
            # Add user message
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            response = st.session_state.chatbot.ask(prompt)
                            st.markdown(response)
                            st.session_state.chat_history.append(
                                {"role": "assistant", "content": response}
                            )
                        except Exception as e:
                            error_msg = f"Error: {str(e)}"
                            st.error(error_msg)
                            st.session_state.chat_history.append(
                                {"role": "assistant", "content": error_msg}
                            )

# Footer
st.divider()
st.caption("Built with Streamlit + LangChain + Groq + FAISS | Vector embeddings persist during session")