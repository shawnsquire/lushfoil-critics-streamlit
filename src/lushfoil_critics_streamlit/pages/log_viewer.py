import streamlit as st
from tinydb import TinyDB
from pathlib import Path
import datetime

st.set_page_config(page_title="Log Viewer", page_icon="📝")

st.sidebar.page_link("app.py", label="Lushfoil Critic", icon="🎨")
st.sidebar.page_link("pages/log_viewer.py", label="Log Viewer", icon="📝")
st.sidebar.divider()

st.title("Critique History")

LOG_FILE = Path("logs") / "session_log.json"

if LOG_FILE.exists():
    db = TinyDB(LOG_FILE)
    logs = db.all()
    if logs:
        # Show most recent first
        for log in reversed(logs):
            response = log.get("response", {})
            if not response:  # Skip if no response data
                continue

            speech_raw = response.get("speech_raw", "I have nothing to say.")
            scores = response.get("scores", {})
            price = response.get("price", 0)
            pitch = log.get("pitch", "No pitch provided.")
            critic = log.get("critic", "Unknown Critic")
            
            try:
                # Attempt to parse the ISO format timestamp
                ts_iso = log.get("ts", "")
                dt_object = datetime.datetime.fromisoformat(ts_iso)
                # Format it nicely
                timestamp = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Fallback for old or invalid timestamps
                timestamp = log.get("ts", "Unknown Time")

            filename = log.get("filename", "N/A")

            # Use an expander for each log entry
            expander_title = f"{timestamp} - {critic} on '{filename}'"
            with st.expander(expander_title):
                image_path_str = log.get("image_path")
                audio_path_str = log.get("audio_path")

                # Display image and audio if they exist
                if image_path_str and Path(image_path_str).exists():
                    st.image(image_path_str, caption=f"Image for {filename}")
                
                if audio_path_str and Path(audio_path_str).exists():
                    st.audio(audio_path_str, format='audio/mpeg')

                st.metric(label="Offer Price", value=f"${price:,}")
                if pitch and pitch != "No pitch provided.":
                    st.markdown(f"**Your Pitch:** {pitch}")
                st.markdown("---")
                st.markdown("#### Full Monologue")
                st.markdown(speech_raw)

                if scores:
                    st.markdown("---")
                    st.markdown("#### Scores")
                    cols = st.columns(len(scores))
                    for i, (key, value) in enumerate(scores.items()):
                        with cols[i]:
                            st.metric(label=key, value=f"{value}/10")
    else:
        st.info("No logs found.")
else:
    st.warning(f"Log file not found at: {LOG_FILE}")
