import re
import os

app_path = r"AI-SudentAssistant/app(1).py"

with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Patch MinuteMind import crash
content = re.sub(
    r"st\.exception\(e\)\s+st\.stop\(\)",
    r"st.exception(e)\n    # st.stop() patched out for UI layout testing",
    content
)

# 2. Add Comfort Controls & Global State + Global CSS injection
global_css_block = '''
def get_unified_css(theme, text_size):
    if theme == "dark":
        bg_primary = "#0D1318"
        bg_surface = "#141C24"
        bg_surface_alt = "#1C2631"
        accent_primary = "#5AA1D1"
        accent_secondary = "#3B6B8A"
        text_primary = "#E6EDF2"
        text_muted = "#8E9CA8"
        border = "#2B3A4A"
    else:
        bg_primary = "#F4F7F9"
        bg_surface = "#FFFFFF"
        bg_surface_alt = "#E8EEF2"
        accent_primary = "#3B6B8A"
        accent_secondary = "#698B9F"
        text_primary = "#1C2A34"
        text_muted = "#526A7A"
        border = "#D1DDE5"

    if text_size == "large":
        base_size = "18px"
        h1_size = "2.5rem"
        chat_size = "1.15rem"
        sm_size = "0.95rem"
    else:
        base_size = "16px"
        h1_size = "2.2rem"
        chat_size = "0.95rem"
        sm_size = "0.8rem"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap');
    
    :root {{
        --bg-primary: {bg_primary};
        --bg-surface: {bg_surface};
        --bg-surface-alt: {bg_surface_alt};
        --accent-primary: {accent_primary};
        --accent-secondary: {accent_secondary};
        --text-primary: {text_primary};
        --text-muted: {text_muted};
        --border: {border};
        
        --font-base: {base_size};
        --font-h1: {h1_size};
        --font-chat: {chat_size};
        --font-sm: {sm_size};
    }}
    
    html, body, [class*="css"] {{ 
        background-color: var(--bg-primary) !important; 
        color: var(--text-primary) !important; 
        font-family: 'DM Sans', sans-serif !important;
        font-size: var(--font-base) !important;
    }}
    
    .stApp {{ background: var(--bg-primary) !important; }}
    [data-testid="stSidebar"] {{ background: var(--bg-surface-alt) !important; border-right: 1px solid var(--border) !important; }}
    [data-testid="stSidebar"] * {{ color: var(--text-primary) !important; }}
    
    h1, h2, h3, .display {{ font-family: 'Outfit', sans-serif !important; color: var(--text-primary) !important; }}
    h1 {{ font-size: var(--font-h1) !important; }}
    
    .stButton>button {{ 
        background-color: var(--bg-surface); 
        color: var(--text-primary) !important; 
        border: 1px solid var(--border); 
        border-radius: 12px; 
        font-family: 'DM Sans', sans-serif; 
        font-weight: 500; 
        transition: all 0.2s ease; 
    }}
    .stButton>button:hover, .stButton>button:focus-visible {{ 
        border-color: var(--accent-primary);
        box-shadow: 0 0 0 2px var(--accent-secondary); 
    }}
    
    .stButton>button[kind="primary"] {{
        background-color: var(--accent-primary) !important;
        color: #ffffff !important;
        border: none !important;
    }}
    
    /* Inputs */
    div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {{ 
        background-color: var(--bg-surface) !important; 
        border: 1px solid var(--border) !important; 
        border-radius: 8px !important; 
    }}
    div[data-baseweb]:focus-within {{ 
        border-color: var(--accent-primary) !important; 
        box-shadow: 0 0 0 2px var(--accent-secondary) !important; 
    }}
    [data-testid="stTextArea"] textarea, [data-testid="stChatInput"] textarea {{ 
        background-color: var(--bg-surface) !important; 
        color: var(--text-primary) !important;
        font-size: var(--font-chat) !important;
    }}
    
    /* MinuteMind Layout */
    .channel {{ 
        background: var(--bg-surface); 
        border: 1px solid var(--border); 
        border-radius: 16px; 
        padding: 1.5rem; 
        margin-bottom: 1.2rem; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); 
    }}
    .channel-tag {{ font-family: 'Outfit', sans-serif; font-size: var(--font-sm); color: var(--accent-secondary); font-weight: 600; text-transform: uppercase; margin-bottom: 0.6rem; }}
    .channel-title {{ font-family: 'Outfit', sans-serif; font-weight: 700; font-size: 1.4rem; color: var(--accent-primary); }}
    .channel-body {{ font-size: var(--font-chat); line-height: 1.7; color: var(--text-primary); }}
    
    /* CourseMate Layout */
    .idx-card, .idx-hero-card, [data-testid="stExpander"] {{ 
        background: var(--bg-surface); 
        border: 1px solid var(--border); 
        border-radius: 12px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }}
    .idx-hero-card {{ padding: 1.5rem; margin-bottom: 1.2rem; }}
    .idx-card {{ padding: 0.8rem; margin-bottom: 0.5rem; }}
    .idx-step-num {{ font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: var(--accent-primary); border: 2px solid var(--accent-primary); border-radius: 50%; width: 1.8rem; height: 1.8rem; display: flex; align-items: center; justify-content: center; }}
    .idx-step-title {{ font-family: 'Outfit', sans-serif; font-size: 1.1rem; font-weight: 600; color: var(--text-primary); }}
    .idx-passage {{ background-color: var(--bg-surface-alt); border-left: 4px solid var(--accent-primary); border-radius: 6px; padding: 0.8rem; margin: 0.4rem 0; font-size: var(--font-sm); color: var(--text-muted); }}
    
    /* Chat bubbles (MM, CM, Socratic) */
    [data-testid="stChatMessage"] {{ background-color: transparent; border: none; padding: 0; margin-bottom: 1rem; }}
    .msg {{ margin-bottom: 1rem; display: flex; flex-direction: column; }}
    .msg-label {{ font-family: 'Outfit', sans-serif; font-size: var(--font-sm); font-weight: 600; margin-bottom: 0.3rem; color: var(--text-muted); flex: unset !important; }}
    .bubble {{ padding: 0.8rem 1.2rem; border-radius: 16px; font-size: var(--font-chat); line-height: 1.6; max-width: 85%; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-top: 0; }}
    .msg.user .bubble {{ background: var(--accent-primary); color: #ffffff !important; border: none; align-self: flex-end; border-bottom-right-radius: 4px; }}
    .msg.assistant .bubble {{ background: var(--bg-surface); color: var(--text-primary) !important; border: 1px solid var(--border); align-self: flex-start; border-bottom-left-radius: 4px; }}
    .msg.user {{ align-items: flex-end; }}
    
    /* Socratic Knowledge Node */
    .knowledge-node-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: 2rem 0;
        position: relative;
        padding: 0 1rem;
    }}
    .knowledge-node-line {{
        position: absolute;
        top: 50%;
        left: 1rem;
        right: 1rem;
        height: 2px;
        background: var(--border);
        transform: translateY(-50%);
        z-index: 0;
    }}
    .knowledge-node {{
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: var(--bg-surface);
        border: 2px solid var(--border);
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.3s ease;
    }}
    .knowledge-node.active {{
        background: var(--accent-primary);
        border-color: var(--accent-primary);
        box-shadow: 0 0 10px var(--accent-secondary);
    }}
    @media (prefers-reduced-motion: reduce) {{
        .knowledge-node {{ transition: none; }}
        .stButton>button {{ transition: none; }}
    }}
    
    /* Clean up empty containers */
    [data-testid="stDecoration"] {{ display: none; }}
    </style>
    """

if "theme" not in st.session_state: st.session_state.theme = "light"
if "text_size" not in st.session_state: st.session_state.text_size = "standard"
st.markdown(get_unified_css(st.session_state.theme, st.session_state.text_size), unsafe_allow_html=True)
'''

# Find initial_sidebar_state="expanded",\n) and inject
content = content.replace(
    'initial_sidebar_state="expanded",\n)',
    'initial_sidebar_state="expanded",\n)\n\n' + global_css_block
)

# 3. Replace old CSS variables
content = re.sub(
    r'MM_CSS\s*=\s*"""[\s\S]*?<\/style>\s*"""',
    'MM_CSS = ""',
    content
)
content = re.sub(
    r'CM_CSS\s*=\s*"""[\s\S]*?<\/style>\s*"""',
    'CM_CSS = ""',
    content
)


# 4. Inject Comfort Sidebar at the very top of navigation
sidebar_repl = '''
st.sidebar.markdown("### 🎛️ Comfort Setup")
theme_choice = st.sidebar.radio("Theme", ["Light", "Dark"], index=0 if st.session_state.theme=="light" else 1, horizontal=True)
size_choice = st.sidebar.radio("Text Size", ["Standard", "Large"], index=0 if st.session_state.text_size=="standard" else 1, horizontal=True)
if theme_choice.lower() != st.session_state.theme or size_choice.lower() != st.session_state.text_size:
    st.session_state.theme = theme_choice.lower()
    st.session_state.text_size = size_choice.lower()
    st.rerun()

st.sidebar.divider()
st.sidebar.title("Navigation Rail")
'''
content = content.replace('st.sidebar.title("Navigation Rail")', sidebar_repl)

# 5. Socratic Node replacement
socratic_prog_regex = r'st\.progress\(st\.session_state\.socratic_hint_level \/ 4, text=f"Hint Level \{st\.session_state\.socratic_hint_level\} of 4"\)'
node_html = '''nodes_html = "<div class='knowledge-node-container'><div class='knowledge-node-line'></div>"
        for i in range(5):
            cls = "knowledge-node active" if i <= st.session_state.socratic_hint_level else "knowledge-node"
            nodes_html += f"<div class='{cls}'></div>"
        nodes_html += "</div>"
        st.markdown(nodes_html, unsafe_allow_html=True)'''
content = re.sub(socratic_prog_regex, node_html, content)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Patch executed successfully.")
