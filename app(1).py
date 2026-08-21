import os
import re
import html
import io
import random
import tempfile
import shutil
import hashlib
from collections import defaultdict
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

import speech_recognition as sr
from gtts import gTTS
import chromadb

from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings, ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser

# --- Import MinuteMind components ---
try:
    from audio_processor import process_input
    from transcriber import transcribe_all
    from summarise import summarize, generate_title
    from extractor import actionable_items, extract_questions, key_decisions
    from rag_engine import build_rag_chain, ask_questions
except ImportError as e:
    st.error(f"Failed to import MinuteMind modules: {e}")
    st.exception(e)
    st.stop()

load_dotenv()
os.environ.setdefault("USER_AGENT", "unified-ai-hub/1.0")

# ==========================================================================
# Module Level Config & Constants
# ==========================================================================
PERSIST_DIR = "chroma_db"
COLLECTION_NAME = "rag_collection"

SUGGESTED_QUESTIONS = [
    "Summarize this document.",
    "What are the key takeaways?",
    "Explain the main topic simply.",
    "List the most important points.",
    "What questions does this raise?",
    "Are there any limitations or gaps?",
    "Give me a quick overview.",
    "Explain like I'm new to this.",
    "What should I remember most?",
]

VOICE_MODE_LABELS = {
    "auto": "Auto-detect",
    "indian_english": "Indian English",
    "hindi": "Hindi",
}

CM_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant. Use ONLY the provided context to answer the question. If the answer is not present in the context, say: 'I could not find the answer in the document.'"),
    ("human", "Context: {context}\n\nQuestion: {question}"),
])

# ==========================================================================
# Page Config (MUST run first at module level)
# ==========================================================================
st.set_page_config(
    page_title="Unified AI Hub",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==========================================================================
# Styles (MinuteMind & CourseMate)
# ==========================================================================
MM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {
    --bg: #0b0e14; --surface: #12161f; --surface-2: #1a1f2b; --border: #242a38;
    --accent: #6c5ce7; --accent-2: #ffb454; --live: #ff5470; --text: #e7e9f2; --text-muted: #808a9e;
}
html, body, [class*="css"] { background-color: var(--bg) !important; color: var(--text) !important; font-family: 'Inter', sans-serif;}
.stApp { background: var(--bg) !important; }
code, .mono { font-family: 'IBM Plex Mono', monospace !important; }
h1, h2, h3, .display { font-family: 'Space Grotesk', sans-serif !important; }
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] * { color: var(--text) !important; }
.eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.28em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 0.4rem; }
.brand-mark { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.15rem; }
.brand-sub { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase; margin-top: 0.15rem; }
.hero-title { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: clamp(2.1rem, 4.5vw, 3.4rem); background: linear-gradient(120deg, #ffffff 0%, var(--accent-2) 55%, var(--accent) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.hero-tagline { color: var(--text-muted); font-size: 0.92rem; max-width: 460px; line-height: 1.6; }
.hero-wave { display: flex; align-items: flex-end; gap: 3px; height: 46px; margin: 1.1rem 0; }
.hero-wave .hbar { width: 4px; border-radius: 2px; height: var(--h); background: linear-gradient(180deg, var(--accent-2), var(--accent)); transform-origin: bottom; animation: wavepulse infinite ease-in-out; }
@keyframes wavepulse { 0%, 100% { transform: scaleY(0.45); } 50% { transform: scaleY(1); } }
.chain-row { display: flex; align-items: center; gap: 0.6rem; padding: 0.5rem 0.15rem; border-bottom: 1px solid var(--border); font-size: 0.76rem; }
.chain-num { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: var(--text-muted); width: 1.4rem; }
.chain-label { flex: 1; color: var(--text); }
.chain-label.pending { color: var(--text-muted); }
.mini-wave { display: flex; align-items: flex-end; gap: 2px; height: 14px; }
.mini-wave .mbar { width: 3px; border-radius: 1px; }
.mbar.done { background: var(--accent-2); }
.mbar.pending { background: var(--border); }
.channel { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.35rem 1.5rem; margin-bottom: 1rem; position: relative; overflow: hidden; }
.channel::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: linear-gradient(180deg, var(--accent), var(--accent-2)); }
.channel-tag { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: var(--accent-2); margin-bottom: 0.6rem; }
.channel-body { font-size: 0.9rem; line-height: 1.75; }
.channel-body ul { margin: 0.3rem 0 0.3rem 1.1rem; padding: 0; }
.channel-body strong { color: var(--accent-2); }
.channel-title { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.35rem; }
.mm-badge { display: inline-block; padding: 0.28rem 0.7rem; border-radius: 5px; font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; border: 1px solid var(--border); color: var(--text-muted); margin-right: 0.4rem; }
.led { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #ff5470; margin-right: 0.4rem; animation: ledpulse 1.4s infinite; }
@keyframes ledpulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
.chat-log { max-height: 380px; overflow-y: auto; margin-bottom: 0.9rem; }
.msg { margin-bottom: 0.85rem; display: flex; flex-direction: column; }
.msg-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; margin-bottom: 0.2rem; }
.msg.user { align-items: flex-end; }
.msg.user .msg-label { color: var(--accent-2); }
.msg.assistant .msg-label { color: var(--accent); }
.bubble { padding: 0.6rem 0.95rem; border-radius: 9px; font-size: 0.87rem; line-height: 1.6; max-width: 88%; white-space: pre-wrap; }
.msg.user .bubble { background: rgba(255,180,84,0.1); border: 1px solid rgba(255,180,84,0.25); }
.msg.assistant .bubble { background: rgba(108,92,231,0.12); border: 1px solid rgba(108,92,231,0.28); }
.empty-panel { text-align: center; padding: 3.5rem 1.5rem; border: 1px dashed var(--border); border-radius: 10px; }
</style>
"""

CM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;1,6..72,500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {
    --bg: #1B222C; --panel: #1F2733; --panel-2: #171D26; --gold: #D3A360;
    --gold-dim: rgba(211,163,96,0.35); --text: #E8E6E1; --text-dim: #8B93A1; --line: rgba(211,163,96,0.22);
}
[data-testid="stAppViewContainer"] { background-color: var(--bg); }
[data-testid="stHeader"] { background-color: transparent; }
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; color: var(--text); }
.block-container { padding-top: 2rem; }
[data-testid="stSidebar"] { background-color: var(--panel); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] * { color: var(--text) !important; }
.idx-step { display: flex; align-items: center; gap: 0.55rem; margin: 0.2rem 0; }
.idx-step-num { font-family: 'Newsreader', serif; font-size: 1rem; color: var(--gold); border: 1px solid var(--gold); border-radius: 50%; width: 1.6rem; height: 1.6rem; display: flex; align-items: center; justify-content: center; }
.idx-step-title { font-family: 'Newsreader', serif; font-size: 1.1rem; font-weight: 600; color: var(--gold); }
.idx-step-sub { font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; text-transform: uppercase; color: var(--text-dim) !important; margin: 0.1rem 0 0.7rem 2.15rem; }
[data-testid="stSidebar"] .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
[data-testid="stSidebar"] .stTabs [data-baseweb="tab"] { font-family: 'IBM Plex Mono', monospace; font-size: 0.76rem; text-transform: uppercase; color: var(--text-dim) !important; padding: 0.4rem 0.6rem; }
[data-testid="stSidebar"] .stTabs [aria-selected="true"] { color: var(--gold) !important; border-bottom: 2px solid var(--gold); }
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] { background-color: var(--panel-2) !important; border: 1px solid var(--gold-dim) !important; border-radius: 5px !important; }
[data-testid="stTextArea"] textarea { background-color: var(--panel-2) !important; border: 1px solid var(--gold-dim) !important; }
[data-testid="stFileUploaderDropzone"] { background-color: var(--panel-2); border: 1px dashed var(--gold-dim); }
[data-testid="stSlider"] label p, [data-testid="stNumberInput"] label p { font-family: 'IBM Plex Mono', monospace !important; font-size: 0.68rem !important; text-transform: uppercase; color: var(--text-dim) !important; }
.stButton>button { background-color: transparent; color: var(--text) !important; border: 1px solid var(--gold); border-radius: 6px; font-family: 'IBM Plex Sans', sans-serif; font-weight: 500; transition: background-color 0.15s ease; }
.stButton>button:hover { background-color: rgba(211,163,96,0.12); border-color: var(--gold); }
.idx-tag { display: inline-flex; align-items: center; gap: 0.3rem; font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--gold); border: 1px solid var(--gold-dim); border-radius: 4px; padding: 0.15rem 0.55rem; }
.idx-card { position: relative; background: var(--panel-2); border: 1px solid var(--line); border-radius: 4px; padding: 0.55rem 0.7rem; margin-bottom: 0.5rem; }
.idx-card-num { font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; color: var(--gold); }
.idx-card-stamp { float: right; font-family: 'IBM Plex Mono', monospace; font-size: 0.6rem; text-transform: uppercase; color: var(--gold); border: 1px solid var(--gold); border-radius: 20px; padding: 0.03rem 0.4rem; }
.idx-card-name { font-weight: 600; font-size: 0.87rem; margin-top: 0.15rem; word-break: break-word; }
.idx-card-meta { font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; color: var(--text-dim); }
.idx-status { display: inline-flex; align-items: center; gap: 0.4rem; font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; padding: 0.25rem 0.7rem; border-radius: 20px; border: 1px solid var(--line); }
.idx-status-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.idx-hero-card { border: 1px solid var(--line); border-radius: 8px; padding: 1.3rem 1.5rem; margin-bottom: 1.2rem; background: var(--panel); }
.idx-hero-eyebrow { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; color: var(--gold); text-transform: uppercase; margin-bottom: 0.45rem; }
.idx-hero-title { font-family: 'Newsreader', serif; font-size: 1.6rem; font-weight: 600; color: var(--text); }
.idx-hero-sub { color: var(--text-dim); font-size: 0.95rem; }
.idx-stats { display: flex; gap: 0.8rem; margin-bottom: 1.2rem; }
.idx-stat { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 0.5rem 0.85rem; min-width: 8rem; }
.idx-stat-num { font-family: 'Newsreader', serif; font-size: 1.3rem; font-weight: 600; color: var(--gold); }
.idx-stat-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.66rem; color: var(--text-dim); text-transform: uppercase; }
.idx-empty { border: 1px dashed var(--gold-dim); border-radius: 8px; padding: 1.8rem 1.4rem; text-align: center; color: var(--text-dim); background-color: rgba(211,163,96,0.04); }
.idx-empty b { color: var(--gold); }
[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 8px; background-color: var(--panel); }
[data-testid="stChatMessage"] { background-color: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 0.5rem 0.75rem; }
.idx-footnotes { margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed var(--line); }
.idx-footnote-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem; color: var(--text-dim); margin-right: 0.4rem; text-transform: uppercase; }
.idx-badge { display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 0.74rem; background-color: rgba(211,163,96,0.1); border: 1px solid var(--gold-dim); color: var(--gold); padding: 0.05rem 0.5rem; border-radius: 20px; margin-right: 0.3rem; }
.idx-passage { background-color: var(--panel-2); border-left: 3px solid var(--gold); border-radius: 4px; padding: 0.6rem 0.8rem; margin: 0.3rem 0; font-size: 0.88rem; color: var(--text-dim); max-height: 220px; overflow-y: auto; white-space: pre-wrap; }
[data-testid="stBottom"] > div { background-color: var(--bg); border-top: 1px solid var(--line); }
[data-testid="stChatInput"] textarea { background-color: var(--panel-2); color: var(--text); }
[data-testid="stChatInput"] { border: 1px solid var(--line); border-radius: 6px; }
</style>
"""

# ==========================================================================
# CourseMate-AI Functions
# ==========================================================================
@st.cache_resource(show_spinner=False)
def cm_get_embedding_model(provider: str):
    if provider == "Google Gemini":
        return GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    return MistralAIEmbeddings()

@st.cache_resource(show_spinner=False)
def cm_get_llm(provider: str, model_name: str, temperature: float):
    if provider == "Google Gemini":
        return ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
    return ChatMistralAI(model=model_name, temperature=temperature)

def cm_clear_chroma_system_cache():
    try:
        chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass

def cm_load_existing_vectorstore(provider: str):
    if os.path.isdir(PERSIST_DIR) and os.listdir(PERSIST_DIR):
        cm_clear_chroma_system_cache()
        try:
            return Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=cm_get_embedding_model(provider),
                collection_name=COLLECTION_NAME,
            )
        except Exception:
            return None
    return None

def cm_add_chunks_to_store(chunks, provider: str):
    if not chunks:
        return
    cm_clear_chroma_system_cache()
    if st.session_state.cm_vectorstore is None:
        st.session_state.cm_vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=cm_get_embedding_model(provider),
            persist_directory=PERSIST_DIR,
            collection_name=COLLECTION_NAME,
        )
    else:
        st.session_state.cm_vectorstore.add_documents(chunks)

def cm_process_documents(uploaded_files, urls, chunk_size, chunk_overlap, provider: str):
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    added, skipped = [], []
    for uploaded_file in uploaded_files or []:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name
        try:
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()
        except Exception as e:
            skipped.append({"name": uploaded_file.name, "reason": f"Read failed: {e}"})
            os.remove(tmp_path)
            continue
        os.remove(tmp_path)
        if not docs or sum(len(d.page_content.strip()) for d in docs) == 0:
            skipped.append({"name": uploaded_file.name, "reason": "No text (needs OCR)"})
            continue
        chunks = splitter.split_documents(docs)
        for c in chunks:
            c.metadata["source"] = uploaded_file.name
            c.metadata["doc_type"] = "pdf"
        if chunks:
            cm_add_chunks_to_store(chunks, provider)
            added.append({"name": uploaded_file.name, "type": "pdf", "chunks": len(chunks)})
        else:
            skipped.append({"name": uploaded_file.name, "reason": "No chunks generated"})
            
    if urls:
        try:
            loader = WebBaseLoader(urls)
            web_docs = loader.load()
        except Exception as e:
            skipped.append({"name": ", ".join(urls), "reason": f"URL load error: {e}"})
            web_docs = []
        if web_docs:
            chunks = splitter.split_documents(web_docs)
            for c in chunks:
                c.metadata["doc_type"] = "url"
            if chunks:
                cm_add_chunks_to_store(chunks, provider)
                counts = defaultdict(int)
                for c in chunks:
                    counts[c.metadata.get("source", "unknown")] += 1
                for src, count in counts.items():
                    added.append({"name": src, "type": "url", "chunks": count})
            else:
                skipped.append({"name": ", ".join(urls), "reason": "No text generated"})
    return added, skipped

def cm_clear_database():
    vs = st.session_state.cm_vectorstore
    if vs is not None:
        try:
            vs.delete_collection()
        except Exception:
            pass
        st.session_state.cm_vectorstore = None
    cm_clear_chroma_system_cache()
    if os.path.isdir(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR, ignore_errors=True)
    cm_clear_chroma_system_cache()
    st.session_state.cm_messages = []
    st.session_state.cm_processed_files = []

def cm_answer_question(query, k, fetch_k, lambda_mult, provider, model_name, temperature):
    retriever = st.session_state.cm_vectorstore.as_retriever(
        search_type="mmr", search_kwargs={"k": k, "fetch_k": fetch_k, "lambda_mult": lambda_mult}
    )
    docs = retriever.invoke(query)
    context = "\n\n".join(doc.page_content for doc in docs)
    final_prompt = CM_PROMPT.invoke({"context": context, "question": query})
    response = cm_get_llm(provider, model_name, temperature).invoke(final_prompt)
    seen, sources, passages = set(), [], []
    for doc in docs:
        source = doc.metadata.get("source")
        page = doc.metadata.get("page")
        if source is None:
            continue
        label = f"{source} — p.{page + 1}" if page is not None else source
        if label not in seen:
            seen.add(label)
            sources.append(label)
            passages.append({"label": label, "text": doc.page_content})
    return response.content, sources, passages

def cm_transcribe_audio(audio_bytes: bytes) -> Optional[str]:
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data)
    except Exception:
        return None

def cm_synthesize_speech(text: str, voice_mode: str) -> bytes:
    clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    clean = re.sub(r"[*_`#>-]+", " ", clean)
    clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    lang = "hi" if voice_mode == "hindi" or (voice_mode == "auto" and re.search(r"[\u0900-\u097F]", clean)) else "en"
    buf = io.BytesIO()
    gTTS(text=clean or text, lang=lang, tld="co.in").write_to_fp(buf)
    buf.seek(0)
    return buf.read()

def cm_handle_query(query, k, fetch_k, lambda_mult, provider, model_name, temperature, voice_answers, voice_mode):
    st.session_state.cm_messages.append({"role": "user", "content": query})
    with st.chat_message("user", avatar="🧭"):
        st.markdown(query)

    with st.chat_message("assistant", avatar="🖋️"):
        if st.session_state.cm_vectorstore is None:
            answer, sources, passages = "Add a source to the archive first.", [], []
            st.markdown(answer)
        else:
            with st.spinner("Turning pages..."):
                try:
                    answer, sources, passages = cm_answer_question(query, k, fetch_k, lambda_mult, provider, model_name, temperature)
                except Exception as e:
                    answer, sources, passages = f"Error: {e}", [], []
                st.markdown(answer)
                if sources:
                    st.caption(f"Sources: {', '.join(sources)}")
                if passages:
                    with st.expander(f"📄 View source passages ({len(passages)})"):
                        for p in passages:
                            st.markdown(f"**{p['label']}**")
                            st.info(p["text"])
            if voice_answers and answer:
                with st.spinner("🔊 Generating voice..."):
                    try:
                        st.audio(cm_synthesize_speech(answer, voice_mode), format="audio/mp3", autoplay=True)
                    except Exception as e:
                        st.caption(f"Playback unavailable: {e}")
    st.session_state.cm_messages.append({"role": "assistant", "content": answer, "sources": sources, "passages": passages})

# ==========================================================================
# MinuteMind Functions
# ==========================================================================
def mm_hero_waveform(n: int = 26) -> str:
    rnd = random.Random(7)
    bars = []
    for _ in range(n):
        h = rnd.randint(25, 90)
        delay = round(rnd.uniform(0, 1.3), 2)
        dur = round(rnd.uniform(0.9, 1.6), 2)
        bars.append(f'<span class="hbar" style="--h:{h}%; animation-delay:{delay}s; animation-duration:{dur}s;"></span>')
    return f'<div class="hero-wave">{"".join(bars)}</div>'

def mm_mini_wave(done: bool) -> str:
    heights = [40, 70, 55, 85] if done else [20, 20, 20, 20]
    cls = "done" if done else "pending"
    bars = "".join(f'<span class="mbar {cls}" style="height:{h}%"></span>' for h in heights)
    return f'<div class="mini-wave">{bars}</div>'

def mm_esc(text: str) -> str:
    return html.escape(str(text)).replace("\n", "<br>")

def mm_sanitize_content(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text) 
    text = re.sub(r"\n?```\s*$", "", text)
    text = re.sub(r"</?div[^>]*>", "", text, flags=re.IGNORECASE)
    text = text.strip()
    n = len(text)
    if n > 1 and n % 2 == 0 and text[:n // 2] == text[n // 2:]:
        text = text[:n // 2]
    return text.strip()

def mm_render_body(text: str) -> str:
    text = html.escape(mm_sanitize_content(text))
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    out, in_list = [], False
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if line.startswith("* ") or line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{line[2:].strip()}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(line)
    if in_list:
        out.append("</ul>")
    return "<br>".join(out) if out else "—"

def mm_channel_card(tag: str, title_html: str, body: str):
    st.markdown(
        f"""<div class="channel"><div class="channel-tag">{tag}</div>{title_html}<div class="channel-body">{mm_render_body(body)}</div></div>""",
        unsafe_allow_html=True,
    )

MM_DEFAULTS = {
    "processed": False, "title": "", "transcript": "", "summary": "",
    "action_items": "", "key_decisions": "", "open_questions": "",
    "mm_rag_chain": None, "mm_chat_history": [], "is_running": False
}

def mm_reset_state():
    if st.session_state.get("is_running", False):
        st.session_state.is_running = False
        return
    for k, v in MM_DEFAULTS.items():
        st.session_state[k] = v
    if os.path.exists("downloades"):
        try:
            shutil.rmtree("downloades")
        except Exception:
            pass

def mm_run_pipeline(source: str) -> bool:
    st.session_state.is_running = True
    status = st.status("Running the signal chain…", expanded=True)
    try:
        status.write("01 · Capturing audio…")
        chunks = process_input(source)
        status.write("02 · Transcribing speech…")
        transcription = transcribe_all(chunks)
        status.write("03 · Naming the session…")
        title = generate_title(transcription)
        status.write("04 · Summarizing…")
        summary = summarize(transcription)
        status.write("05 · Extracting action items, decisions & questions…")
        actions = actionable_items(transcription)
        decisions = key_decisions(transcription)
        questions = extract_questions(transcription)
        status.write("06 · Indexing for chat…")
        rag_chain = build_rag_chain(transcription)

        status.update(label="Signal locked. Meeting decoded.", state="complete", expanded=False)
        st.session_state.update({
            "processed": True, "title": title, "transcript": transcription, "summary": summary,
            "action_items": actions, "key_decisions": decisions, "open_questions": questions,
            "mm_rag_chain": rag_chain, "mm_chat_history": []
        })
        return True
    except Exception as e:
        status.update(label="Pipeline failed", state="error", expanded=False)
        st.session_state.processed = False
        st.error(f"Error processing: {e}")
        return False
    finally:
        st.session_state.is_running = False

# ==========================================================================
# Main Streamlit Routing
# ==========================================================================
st.sidebar.title("Navigation Rail")
app_mode = st.sidebar.radio("Active Console", ["MinuteMind (Video)", "CourseMate-AI (Documents)"])
st.sidebar.divider()

if app_mode == "MinuteMind (Video)":
    # --- MinuteMind Style & Defaults init ---
    st.markdown(MM_CSS, unsafe_allow_html=True)
    for k, v in MM_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

    with st.sidebar:
        st.markdown('<div class="eyebrow">Audio → Insight</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-mark">▮ MinuteMind</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">Meeting intelligence console</div>', unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown("""
        <div style="background:rgba(255,180,84,0.08);border:1px solid rgba(255,180,84,0.25);border-radius:8px;padding:0.8rem 1rem;margin-bottom:1.2rem;font-size:0.75rem;color:var(--text-muted);line-height:1.6;">
        <strong style="color:var(--accent-2);">ℹ️ How to transcribe YouTube videos</strong><br/>
        YouTube blocks direct URL downloads on cloud hosts. Download locally using <b>yt-dlp</b> first, then upload below.
        </div>""", unsafe_allow_html=True)

        source_value, source_id = None, None
        uploaded = st.file_uploader("Upload File", type=["mp3", "wav", "m4a", "mp4", "mov", "mkv"], label_visibility="collapsed")
        if uploaded is not None:
            source_id = f"file:{uploaded.name}:{uploaded.size}"
            if st.session_state.get("last_source_id") != source_id:
                mm_reset_state()
            tmp_dir = tempfile.mkdtemp()
            tmp_path = os.path.join(tmp_dir, uploaded.name)
            with open(tmp_path, "wb") as f:
                f.write(uploaded.getbuffer())
            source_value = tmp_path

        run_clicked = st.button("▸ Analyze Video", use_container_width=True, disabled=not source_value)
        st.button("Reset Console", use_container_width=True, type="secondary", on_click=mm_reset_state)

        if run_clicked and source_value:
            mm_reset_state()
            st.session_state.last_source_id = source_id
            mm_run_pipeline(source_value)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">Signal chain</div>', unsafe_allow_html=True)
        for num, label in [("01", "Capture audio"), ("02", "Transcribe speech"), ("03", "Name session"), ("04", "Summarize"), ("05", "Extract insights"), ("06", "Index for chat")]:
            done = st.session_state.processed
            st.markdown(f'<div class="chain-row"><span class="chain-num">{num}</span><span class="chain-label {"" if done else "pending"}">{label}</span>{mm_mini_wave(done)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="eyebrow">Signal from your meetings</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">MinuteMind</div>', unsafe_allow_html=True)
    st.markdown(mm_hero_waveform(), unsafe_allow_html=True)
    st.markdown('<div class="hero-tagline">Turns any meeting recording into instant summaries, key decisions, action items, and a chatbot.</div>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    if not st.session_state.processed:
        st.markdown("""<div class="empty-panel"><div class="brand-mark" style="font-size:1.3rem;margin-bottom:0.4rem;">Nothing to play back yet</div><div style="color:var(--text-muted);font-size:0.85rem;max-width:420px;margin:0 auto;">Drop a recording into the console on the left, then hit <b>Analyze Video</b>.</div></div>""", unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="channel-tag">Session</div><div class="channel-title" style="margin-bottom:1rem;">{mm_esc(mm_sanitize_content(st.session_state.title))}</div>', unsafe_allow_html=True)
        mm_channel_card("CH.01 — SUMMARY", "", st.session_state.summary)

        c1, c2, c3 = st.columns(3, gap="medium")
        with c1: mm_channel_card("CH.02 — ACTION ITEMS", "", st.session_state.action_items)
        with c2: mm_channel_card("CH.03 — KEY DECISIONS", "", st.session_state.key_decisions)
        with c3: mm_channel_card("CH.04 — OPEN QUESTIONS", "", st.session_state.open_questions)

        with st.expander("CH.05 — TRANSCRIPT"):
            st.markdown(f'<div class="channel-body mono" style="max-height:340px;overflow-y:auto;white-space:pre-wrap;">{mm_esc(mm_sanitize_content(st.session_state.transcript))}</div>', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="channel-tag"><span class="led"></span>CH.06 — ASK MINUTEMIND</div>', unsafe_allow_html=True)

        if st.session_state.mm_chat_history:
            rows = []
            for role, msg in st.session_state.mm_chat_history:
                label = "You" if role == "user" else "MinuteMind"
                content = mm_esc(msg) if role == "user" else mm_render_body(msg)
                rows.append(f'<div class="msg {role}"><div class="msg-label">{label}</div><div class="bubble">{content}</div></div>')
            st.markdown(f'<div class="chat-log">{"".join(rows)}</div>', unsafe_allow_html=True)

        q_col, btn_col = st.columns([5, 1], gap="small")
        with q_col:
            question = st.text_input("Ask", placeholder="Ask something...", label_visibility="collapsed")
        with btn_col:
            ask_clicked = st.button("Send", use_container_width=True)

        if ask_clicked and question.strip():
            with st.spinner("Retrieving response..."):
                try: answer = ask_questions(st.session_state.mm_rag_chain, question.strip())
                except Exception as e: answer = f"Error: {e}"
            st.session_state.mm_chat_history.append(("user", question.strip()))
            st.session_state.mm_chat_history.append(("assistant", answer))
            st.rerun()

elif app_mode == "CourseMate-AI (Documents)":
    # --- CourseMate Style & Defaults init ---
    st.markdown(CM_CSS, unsafe_allow_html=True)
    if "cm_vectorstore" not in st.session_state: st.session_state.cm_vectorstore = None
    if "cm_messages" not in st.session_state: st.session_state.cm_messages = []
    if "cm_processed_files" not in st.session_state: st.session_state.cm_processed_files = []
    if "cm_last_voice_hash" not in st.session_state: st.session_state.cm_last_voice_hash = None

    # Load existing store on start
    cm_provider_choice = st.sidebar.selectbox("RAG Engine Provider", ["Google Gemini", "Mistral AI"], index=0)
    if st.session_state.cm_vectorstore is None:
        st.session_state.cm_vectorstore = cm_load_existing_vectorstore(cm_provider_choice)

    with st.sidebar:
        st.markdown('<div class="idx-step"><span class="idx-step-num">①</span><span class="idx-step-title">Add your sources</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="idx-step-sub">PDF(s) and/or URLs</div>', unsafe_allow_html=True)

        tab_pdf, tab_url = st.tabs(["📄 PDF", "🌐 URL"])
        with tab_pdf: uploaded_files = st.file_uploader("Drop PDF", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed")
        with tab_url: url_text = st.text_area("One URL per line", placeholder="https://...", height=100, label_visibility="collapsed")

        col_cs, col_co = st.columns(2)
        with col_cs: chunk_size = st.number_input("Chunk size", min_value=200, max_value=4000, value=1000, step=100)
        with col_co: chunk_overlap = st.number_input("Chunk overlap", min_value=0, max_value=1000, value=200, step=50)

        if st.button("📥 Index documents", use_container_width=True):
            urls = [u.strip() for u in url_text.splitlines() if u.strip()]
            if not uploaded_files and not urls:
                st.warning("Please add a PDF or a URL first.")
            else:
                with st.spinner("Reading & Indexing..."):
                    added, skipped = cm_process_documents(uploaded_files, urls, chunk_size, chunk_overlap, cm_provider_choice)
                    st.session_state.cm_processed_files.extend(added)
                    if added: st.success(f"Indexed {len(added)} item(s).")
                    for s in skipped: st.error(f"{s['name']}: {s['reason']}")
        
        if st.session_state.cm_processed_files:
            st.markdown("**Catalog**")
            for i, f in enumerate(st.session_state.cm_processed_files, start=1):
                tag = "URL" if f.get("type") == "url" else "PDF"
                st.markdown(f'<div class="idx-card"><span class="idx-card-stamp">indexed</span><span class="idx-card-num">{i:03d} · {tag}</span><div class="idx-card-name">{f["name"]}</div><div class="idx-card-meta">{f["chunks"]} passages</div></div>', unsafe_allow_html=True)

        st.divider()
        st.markdown('<div class="idx-step"><span class="idx-step-num">②</span><span class="idx-step-title">Analysis settings</span></div>', unsafe_allow_html=True)
        
        # Populate model selection based on provider
        if cm_provider_choice == "Google Gemini":
            cm_models = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-1.5-flash", "gemini-1.5-pro"]
        else:
            cm_models = ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"]
        
        model_name = st.selectbox("Model", cm_models, index=0)
        temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)

        voice_answers = st.checkbox("🔊 Read answers aloud", value=False)
        voice_mode = st.selectbox("Voice style", list(VOICE_MODE_LABELS.keys()), format_func=lambda x: VOICE_MODE_LABELS[x]) if voice_answers else "auto"

        k = st.slider("Chunks returned (k)", 1, 30, 10, 1)
        fetch_k = st.slider("Candidates (fetch_k)", 10, 200, 100, 10)
        lambda_mult = st.slider("Relevance ↔ Diversity", 0.0, 1.0, 0.5, 0.05)

        st.markdown(f'<span class="idx-tag">Vector directory: {PERSIST_DIR}</span>', unsafe_allow_html=True)
        col_wipe, col_clr = st.columns(2)
        with col_wipe:
            if st.button("Reset Archive", use_container_width=True):
                cm_clear_database()
                st.rerun()
        with col_clr:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.cm_messages = []
                st.rerun()

    active_query = None
    st.markdown("""<div class="idx-hero-card"><div class="idx-hero-eyebrow">Reading room · grounded in your sources</div><div class="idx-hero-title">CourseMate-Ai</div><div class="idx-hero-sub">Upload PDFs, web documents or URLs and query them.</div></div>""", unsafe_allow_html=True)

    if st.session_state.cm_processed_files:
        pdf_count = sum(1 for f in st.session_state.cm_processed_files if f.get("type") != "url")
        url_count = sum(1 for f in st.session_state.cm_processed_files if f.get("type") == "url")
        chunk_count = sum(f.get("chunks", 0) for f in st.session_state.cm_processed_files)
        st.markdown(f'<div class="idx-stats"><div class="idx-stat"><div class="idx-stat-num">{pdf_count}</div><div class="idx-stat-label">PDFs</div></div><div class="idx-stat"><div class="idx-stat-num">{url_count}</div><div class="idx-stat-label">URLs</div></div><div class="idx-stat"><div class="idx-stat-num">{chunk_count}</div><div class="idx-stat-label">Indexed Passages</div></div></div>', unsafe_allow_html=True)

    if st.session_state.cm_vectorstore is None:
        st.markdown('<div class="idx-empty"><b>No active documents in source database.</b><br/>Add a PDF file or a URL in the sidebar and index it to start.</div>', unsafe_allow_html=True)
    else:
        with st.expander("💡 Suggested questions", expanded=not st.session_state.cm_messages):
            cols = st.columns(3)
            for i, question in enumerate(SUGGESTED_QUESTIONS):
                with cols[i % 3]:
                    if st.button(question, use_container_width=True, key=f"suggest_{i}"):
                        active_query = question

        for msg in st.session_state.cm_messages:
            avatar = "🧭" if msg["role"] == "user" else "🖋️"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])
                if msg.get("sources"):
                    st.caption(f"Sources: {', '.join(msg['sources'])}")
                if msg.get("passages"):
                    with st.expander(f"View source passages ({len(msg['passages'])})"):
                        for p in msg['passages']:
                            st.markdown(f"**{p['label']}**")
                            st.info(p["text"])

        voice_clip = st.audio_input("🎤 Query by voice")
        if voice_clip is not None:
            audio_bytes = voice_clip.getvalue()
            audio_hash = hashlib.md5(audio_bytes).hexdigest()
            if audio_hash != st.session_state.cm_last_voice_hash:
                st.session_state.cm_last_voice_hash = audio_hash
                with st.spinner("Transcribing..."):
                    transcript = cm_transcribe_audio(audio_bytes)
                if transcript:
                    active_query = transcript
                else:
                    st.warning("Unrecognized audio input. Speak closer to the microphone.")

        if active_query:
            cm_handle_query(active_query, k, fetch_k, lambda_mult, cm_provider_choice, model_name, temperature, voice_answers, voice_mode)

        typed_query = st.chat_input("Ask something about your indexed documents...")
        if typed_query:
            cm_handle_query(typed_query, k, fetch_k, lambda_mult, cm_provider_choice, model_name, temperature, voice_answers, voice_mode)
