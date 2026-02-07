import streamlit as st
import time
import logging
import uuid
from datetime import datetime, timedelta

# Import services from the services layer
from services.services import nlp, get_health_status, db

# Import the new config
from config import APP_CONFIG

# Import the new rethink module
from logic.rethink import rethink_and_learn

# Import the new knowledge_base module
from brain.knowledge_base import generate_response_from_knowledge

# Import advanced learning
from logic.advanced_learning import quick_learn_unknowns, deep_learning, LEARNING_INTERVAL

logging.basicConfig(level=APP_CONFIG.LOG_LEVEL)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Project Seedling v2", layout="centered")
st.title("Project Seedling v2")

# Initialize session state for learning tracking
if "learning_last_run" not in st.session_state:
    st.session_state.learning_last_run = None
if "learning_status" not in st.session_state:
    st.session_state.learning_status = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True

# --- Sidebar --- 
with st.sidebar:
    st.header("AI Teacher Preview")
    health = get_health_status()

    # Show debug info if enabled
    if APP_CONFIG.LOG_LEVEL == "DEBUG" or not health["all_services_ok"]:
        st.write("**System Status:**")
        st.write(f"- Firebase: {'✅ Online' if health['firebase']['online'] else '❌ Offline'}")
        st.write(f"- spaCy NLP: {'✅ Online' if health['spacy']['online'] else '❌ Offline'}")
        st.write(f"- Gemini API: {'✅ Ready' if health['gemini']['configured'] else '⚠️ Not configured'}")
        st.write(f"- Groq API: {'✅ Ready' if health['groq']['configured'] else '⚠️ Not configured'}")

    # Show knowledge base stats if services are online
    if health['all_services_ok']:
        try:
            from scripts.seed_knowledge import get_bootstrap_stats
            stats = get_bootstrap_stats(db)
            if stats:
                st.markdown("---")
                st.subheader("📚 Knowledge Base")
                st.metric("Learned Concepts", stats.get('bootstrapped_concepts', 0))
                st.metric("Sentence Patterns", stats.get('sentence_patterns', 0))
        except Exception as e:
            logger.debug(f"Could not load knowledge stats: {e}")
    else:
        st.error("⚠️ Core services not initialized. Check logs for details.")
    
    # --- Learning Control Panel ---
    st.markdown("---")
    st.subheader("🧠 Learning Control")
    
    # Calculate time until next learning
    if st.session_state.learning_last_run:
        elapsed = time.time() - st.session_state.learning_last_run
        remaining = max(0, LEARNING_INTERVAL - elapsed)
        countdown_secs = int(remaining)
        progress = min(1.0, 1.0 - (remaining / LEARNING_INTERVAL))
    else:
        countdown_secs = LEARNING_INTERVAL
        progress = 0.0
    
    # Display countdown
    countdown_placeholder = st.empty()
    with countdown_placeholder.container():
        col1, col2 = st.columns([2, 1])
        with col1:
            st.metric("Next Quick Learn", f"{countdown_secs}s", delta=f"/{LEARNING_INTERVAL}s")
        with col2:
            st.progress(progress, text="Learning cycle")
    
    # Learning status
    if st.session_state.learning_status:
        status_data = st.session_state.learning_status
        # Show summary and errors (with types) for debugging
        errors = status_data.get('errors', [])
        error_lines = []
        for e in errors[:5]:
            if isinstance(e, dict):
                error_lines.append(f"{e.get('word')}: {e.get('type')} - {e.get('message')[:120]}")
            else:
                error_lines.append(str(e))

        st.info(f"""
**Last Learning:**
- Status: {status_data.get('status')}
- Learned: {status_data.get('learned_count', 0)} concepts
- Errors: {len(errors)}
- Time: {status_data.get('timestamp', '')[:16]}
\nRecent errors:\n{chr(10).join(error_lines)}
        """)
    
    # Deep Learning Button
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Quick Learn Now", use_container_width=True, help="Learn unknown concepts with Groq"):
            with st.spinner("Quick learning in progress..."):
                result = quick_learn_unknowns()
                st.session_state.learning_status = result
                st.session_state.learning_last_run = time.time()
                st.toast(f"✅ Learned {result.get('learned_count', 0)} concepts!", icon="🚀")
                st.rerun()
    
    with col2:
        if st.button("🧠 Deep Learn", use_container_width=True, help="Expand knowledge deeply with Gemini + Groq"):
            with st.spinner("Deep learning in progress..."):
                result = deep_learning()
                st.session_state.learning_status = result
                st.session_state.learning_last_run = time.time()
                learned = result.get('learned_unknown', 0)
                deepened = result.get('deepened_known', 0)
                st.toast(f"✅ Learned {learned} unknowns, deepened {deepened} concepts!", icon="🧠")
                st.rerun()

    # --- Unknown Candidates Review ---
    st.markdown("---")
    st.subheader("📋 Review Unknowns")
    
    try:
        # Fetch recent candidates from needs_review collection
        review_docs = db.collection('needs_review').order_by('timestamp', direction='DESCENDING').limit(1).stream()
        review_entries = list(review_docs)
        
        if review_entries:
            latest_review = review_entries[0].to_dict()
            candidates = latest_review.get('candidates', [])
            
            if candidates:
                st.write(f"**Candidates to learn** ({len(candidates)}):")
                for i, cand in enumerate(candidates[:5]):  # Show top 5
                    col_cand, col_approve, col_reject = st.columns([3, 1, 1])
                    with col_cand:
                        st.write(f"• {cand}")
                    with col_approve:
                        if st.button("✅", key=f"approve_{i}_{cand}", help="Approve and learn"):
                            # Candidate already in unknown_words, will be learned on next cycle
                            st.toast(f"✅ {cand} approved!", icon="👍")
                    with col_reject:
                        if st.button("❌", key=f"reject_{i}_{cand}", help="Reject/skip"):
                            # Remove from unknown_words
                            try:
                                from brain.db import is_known
                                if not is_known(cand):
                                    db.collection('unknown_words').document(cand).delete()
                                    st.toast(f"❌ {cand} rejected!", icon="🚫")
                            except Exception as e:
                                logger.debug(f"Error rejecting {cand}: {e}")
            else:
                st.info("No candidate unknowns pending review.")
        else:
            st.info("No unknowns logged yet. Ask a question!")
    except Exception as e:
        st.warning(f"Could not load review candidates: {str(e)[:100]}")
        logger.debug(f"Error in review UI: {e}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Automatic Learning Loop ---
# Check if it's time to run quick learning
if st.session_state.learning_last_run is None or (time.time() - st.session_state.learning_last_run) >= LEARNING_INTERVAL:
    try:
        result = quick_learn_unknowns()
        if result["status"] == "completed" and result["learned_count"] > 0:
            st.session_state.learning_status = result
            st.session_state.learning_last_run = time.time()
            logger.info(f"🚀 Automatic quick learning triggered: {result['learned_count']} concepts learned")
    except Exception as e:
        logger.error(f"Error in automatic learning: {e}")

# --- Auto-refresh to update countdown every second ---
if st.session_state.auto_refresh:
    try:
        time.sleep(1)
        st.experimental_rerun()
    except Exception:
        # If rerun fails for any reason, do not crash the app
        pass

# --- Functions for handling user feedback ---
def handle_feedback(message_id, is_correct):
    if is_correct:
        st.toast("Thanks for the feedback! 👍", icon="✅")
        # In a real app, you might log this to improve the model
    else:
        st.session_state.rethinking = {"message_id": message_id}
        st.rerun()

# -- Main chat display and interaction
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Add feedback buttons for assistant messages
        if message["role"] == "assistant" and "rethink_of" not in message:
            col1, col2 = st.columns([1, 10])
            with col1:
                st.button("👍", key=f"good_{message['id']}", on_click=handle_feedback, args=(message['id'], True))
            with col2:
                st.button("👎", key=f"bad_{message['id']}", on_click=handle_feedback, args=(message['id'], False))

# Handle the user's prompt
if prompt := st.chat_input("Ask a question..."):
    new_message_id = str(uuid.uuid4())
    new_message = {"role": "user", "content": prompt, "id": new_message_id}
    st.session_state.messages.append(new_message)
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown("🧠 _Thinking..._")
        
        try:
            conversation_context = [
                (msg["role"], msg["content"])
                for msg in st.session_state.messages[:-1]
            ]
            
            response_data = generate_response_from_knowledge(
                prompt, 
                conversation_context=conversation_context
            )
            answer = response_data.get("synthesized_answer")
            
            thinking_placeholder.empty()
            st.markdown(answer)
            # Store the original prompt ID so we can trace back to what question this answers
            new_message = {
                "role": "assistant", 
                "content": answer, 
                "id": str(uuid.uuid4()),
                "original_prompt_id": new_message_id
            }
            st.session_state.messages.append(new_message)

        except Exception as e:
            logger.error(f"Error in generate_response: {e}", exc_info=True)
            thinking_placeholder.empty()
            answer = f"⚠️ Error: {str(e)[:200]}"
            st.markdown(answer)
            new_message = {
                "role": "assistant", 
                "content": answer, 
                "id": str(uuid.uuid4()),
                "original_prompt_id": new_message_id
            }
            st.session_state.messages.append(new_message)

# Handle the rethinking process
if st.session_state.get("rethinking"):
    message_id_to_rethink = st.session_state.rethinking["message_id"]
    
    # Find the assistant message with this ID
    assistant_msg = None
    original_prompt = None
    bad_answer = None
    
    for msg in st.session_state.messages:
        if msg.get('id') == message_id_to_rethink and msg.get('role') == 'assistant':
            assistant_msg = msg
            bad_answer = msg.get('content')
            # Find the original prompt using the stored reference
            original_prompt_id = msg.get('original_prompt_id')
            for user_msg in st.session_state.messages:
                if user_msg.get('id') == original_prompt_id:
                    original_prompt = user_msg.get('content')
                    break
            break

    if original_prompt and bad_answer:
        st.session_state.rethinking = None # Reset the state
        with st.chat_message("assistant"):
            rethink_placeholder = st.empty()
            rethink_placeholder.markdown("🤔 _That wasn't right. Let me research and rethink..._")
            
            try:
                new_answer = rethink_and_learn(original_prompt, bad_answer)
                
                rethink_placeholder.empty()
                st.markdown(new_answer)
                # Add the new answer as a new message, noting it's a correction
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": new_answer, 
                    "id": str(uuid.uuid4()),
                    "rethink_of": message_id_to_rethink,
                    "original_prompt_id": assistant_msg.get('original_prompt_id')
                })
            except Exception as e:
                logger.error(f"Error in rethinking: {e}", exc_info=True)
                rethink_placeholder.empty()
                st.error(f"Rethinking failed: {str(e)[:200]}")
