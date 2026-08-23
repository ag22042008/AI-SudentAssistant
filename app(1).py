from typing import Optional

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

import speech_recognition as sr
@@ -32,11 +33,18 @@
    from summarise import summarize, generate_title
    from extractor import actionable_items, extract_questions, key_decisions
    from rag_engine import build_rag_chain, ask_questions
    from hint_engine import get_next_hint, extract_topic
except ImportError as e:
    st.error(f"Failed to import MinuteMind modules: {e}")
    st.exception(e)
    st.stop()

import pandas as pd
try:
    from hint_engine import get_next_hint, extract_topic
except ImportError as e:
    st.error(f"Failed to import Socratic modules: {e}")

load_dotenv()
os.environ.setdefault("USER_AGENT", "unified-ai-hub/1.0")

@@ -564,7 +572,7 @@ def mm_run_pipeline(source: str) -> bool:
# Main Streamlit Routing
# ==========================================================================
st.sidebar.title("Navigation Rail")
app_mode = st.sidebar.radio("Active Console", ["MinuteMind (Video)", "CourseMate-AI (Documents)"])
app_mode = st.sidebar.radio("Active Console", ["MinuteMind (Video)", "CourseMate-AI (Documents)", "🎓 Socratic Tutor"])
st.sidebar.divider()

if app_mode == "MinuteMind (Video)":
@@ -779,3 +787,202 @@ def mm_run_pipeline(source: str) -> bool:
        typed_query = st.chat_input("Ask something about your indexed documents...")
        if typed_query:
            cm_handle_query(typed_query, k, fetch_k, lambda_mult, cm_provider_choice, model_name, temperature, voice_answers, voice_mode)
elif app_mode == "🎓 Socratic Tutor":
    # Reset function
    def socratic_reset_session():
        st.session_state.socratic_messages = []
        st.session_state.socratic_hint_level = 0
        st.session_state.socratic_current_question = ""
        st.session_state.socratic_current_topic = ""
        st.session_state.socratic_completed = False
        st.session_state.socratic_completion_message = ""
    
    # Initialize session state variables
    if "socratic_messages" not in st.session_state:
        socratic_reset_session()
    if "socratic_current_subject" not in st.session_state:
        st.session_state.socratic_current_subject = "General"
    if "socratic_history" not in st.session_state:
        st.session_state.socratic_history = []
    
    # Sidebar for settings and resetting
    with st.sidebar:
        st.header("Settings")
        
        # We maintain a separate key for changes to trigger without relying solely on manual state sync
        subject = st.selectbox(
            "Subject", 
            ["Math", "Physics", "History", "Computer Science", "General"], 
            index=["Math", "Physics", "History", "Computer Science", "General"].index(st.session_state.socratic_current_subject)
        )
        
        # Subject change detection
        if subject != st.session_state.socratic_current_subject:
            st.session_state.socratic_current_subject = subject
            socratic_reset_session()
            st.rerun()
    
        st.write("---")
        
        if st.button("Start New Topic"):
            socratic_reset_session()
            st.rerun()
    
        st.write("---")
        st.header("📊 Your Progress")
        
        if not st.session_state.socratic_history:
            st.write("No questions attempted yet.")
        else:
            st.write(f"**Total questions attempted this session:** {len(st.session_state.socratic_history)}")
            
            # Aggregate logic
            df = pd.DataFrame(st.session_state.socratic_history)
            
            # Group by Subject and Topic, averaging hints_used, and keeping any self_solved as max/any
            agg_df = df.groupby(["subject", "topic"]).agg(
                hints_used=("hints_used", "mean"),
                self_solved=("self_solved", "any")
            ).reset_index()
            
            # Display grouping per subject
            subjects = agg_df["subject"].unique()
            for sub in subjects:
                st.subheader(f"Subject: {sub}")
                sub_df = agg_df[agg_df["subject"] == sub]
                display_df = sub_df[["topic", "hints_used", "self_solved"]].copy()
                display_df["hints_used"] = display_df["hints_used"].round(1)
                st.dataframe(display_df, hide_index=True)
    
            # Identify Weak and Strong Areas
            weak_areas = agg_df[agg_df["hints_used"] >= 3]
            strong_areas = agg_df[(agg_df["hints_used"] <= 1) & (agg_df["self_solved"] == True)]
            
            if not weak_areas.empty:
                st.write("🔴 **Weak Areas**")
                for _, row in weak_areas.iterrows():
                    st.write(f"- You're needing more help with {row['topic']} ({row['subject']}) — consider reviewing the basics here.")
                    
            if not strong_areas.empty:
                st.write("🟢 **Strong Areas**")
                for _, row in strong_areas.iterrows():
                    st.write(f"- You've got a solid grip on {row['topic']} ({row['subject']}).")
    
    # Hint Level Indicator
    if st.session_state.socratic_current_question and not st.session_state.socratic_completed:
        st.progress(st.session_state.socratic_hint_level / 4, text=f"Hint Level {st.session_state.socratic_hint_level} of 4")
    
    # Display chat history
    for message in st.session_state.socratic_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Completion State UX
    if st.session_state.socratic_completed:
        st.success(st.session_state.socratic_completion_message)
        if st.button("Ask a New Question", type="primary"):
            socratic_reset_session()
            st.rerun()
    
    else:
        # State flags for buttons
        action_hint = False
        action_reveal = False
        action_chat = None
    
        # Buttons (only show if we have an active question)
        if st.session_state.socratic_current_question:
            col1, col2, _ = st.columns([1, 1, 2])
            with col1:
                if st.button("💡 Give me a hint", use_container_width=True):
                    action_hint = True
            with col2:
                if st.button("🔍 Reveal Answer", type="secondary", use_container_width=True):
                    action_reveal = True
    
        # Chat input
        prompt = st.chat_input("Ask a question or reply to the hint...")
        
        if prompt:
            action_chat = prompt
    
        # Process input
        student_input = None
        override_level = None
        is_first_turn = False
    
        if action_reveal:
            student_input = ""
            override_level = 4
        elif action_hint:
            student_input = ""
        elif action_chat:
            student_input = action_chat
    
        if student_input is not None:
            if not st.session_state.socratic_current_question and student_input.strip() != "":
                st.session_state.socratic_current_question = student_input
                is_first_turn = True
    
            if action_hint:
                display_text = "*(Asked for a hint)*"
                st.session_state.socratic_messages.append({"role": "user", "content": display_text})
                with st.chat_message("user"):
                    st.markdown(display_text)
            elif action_reveal:
                display_text = "*(Asked to reveal the answer)*"
                st.session_state.socratic_messages.append({"role": "user", "content": display_text})
                with st.chat_message("user"):
                    st.markdown(display_text)
            elif action_chat:
                st.session_state.socratic_messages.append({"role": "user", "content": action_chat})
                with st.chat_message("user"):
                    st.markdown(action_chat)
    
            with st.spinner("Thinking..."):
                effective_level = override_level if override_level is not None else st.session_state.socratic_hint_level
                
                if is_first_turn:
                    # Extract topic before hints start
                    st.session_state.socratic_current_topic = extract_topic(
                        st.session_state.socratic_current_question, 
                        st.session_state.socratic_current_subject
                    )
    
                hint_student_input = "" if is_first_turn else student_input
    
                understood, reply_text = get_next_hint(
                    question=st.session_state.socratic_current_question,
                    subject=st.session_state.socratic_current_subject,
                    hint_level=effective_level,
                    student_input=hint_student_input
                )
    
                # Record history on completion
                resolved_just_now = False
                if understood:
                    st.session_state.socratic_completed = True
                    st.session_state.socratic_completion_message = "🎉 You got it!"
                    resolved_just_now = True
                elif effective_level == 4:
                    st.session_state.socratic_completed = True
                    st.session_state.socratic_completion_message = "Here's the full explanation above."
                    resolved_just_now = True
                else:
                    st.session_state.socratic_hint_level = min(4, st.session_state.socratic_hint_level + 1)
                
                if resolved_just_now:
                    st.session_state.socratic_history.append({
                        "subject": st.session_state.socratic_current_subject,
                        "topic": st.session_state.socratic_current_topic,
                        "question": st.session_state.socratic_current_question,
                        "hints_used": effective_level,
                        "self_solved": understood  # If it became True before/at completion
                    })
                
            st.session_state.socratic_messages.append({"role": "assistant", "content": reply_text})
            with st.chat_message("assistant"):
                st.markdown(reply_text)
            
            st.rerun()
