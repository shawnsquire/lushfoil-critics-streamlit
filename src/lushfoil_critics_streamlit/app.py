import streamlit as st
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from tinydb import TinyDB, Query
from pathlib import Path
import datetime, io, yaml, base64, json

st.set_page_config(page_title="Lushfoil Critics", page_icon="🎨", initial_sidebar_state="collapsed")

# Hide the default Streamlit page navigation in the sidebar
st.markdown("""
<style>
    [data-testid="stSidebarNavItems"] {display: none;}
</style>
""", unsafe_allow_html=True)


# --- Custom Sidebar Navigation ---
st.sidebar.page_link("app.py", label="Lushfoil Critic", icon="🎨")
st.sidebar.page_link("pages/log_viewer.py", label="Log Viewer", icon="📝")
st.sidebar.divider()

cfg = st.sidebar
cfg.title("Settings")

# --- config -----------------------------------------------------------------
elabs = ElevenLabs(api_key=st.secrets["elabs_key"]) if "elabs_key" in st.secrets else None
CRITICS_FILE = Path(__file__).parent / "critics.yaml"
CRITIC_PROMPT_FILE = Path(__file__).parent / "critic_prompt.txt"

def autoplay_audio(buffer: io.BytesIO, format: str = "audio/mpeg"):
    """Autoplays audio from a buffer of bytes without showing the player."""
    buffer.seek(0)
    audio_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    audio_tag = f'<audio autoplay="true" src="data:{format};base64,{audio_base64}">'
    st.markdown(audio_tag, unsafe_allow_html=True)


# @st.cache_data
def load_critics():
    """Loads critics from the YAML file."""
    with open(CRITICS_FILE, 'r') as f:
        return yaml.safe_load(f)

# @st.cache_resource
def load_critic_prompt():
    with open(CRITIC_PROMPT_FILE, 'r') as f:
        return f.read()

def calculate_price(scores, snootiness):
    """Calculates the offer price based on scores and critic snootiness."""
    if not scores:
        return 0

    total_score = sum(scores.values())
    # Volatility factor makes the price swing more for snootier critics.
    volatility_factor = 1 + (snootiness / 100.0)  # Range 1.1 to 2.0

    # Score delta from the average of 15 (for 3x 0-10 scores).
    score_delta = total_score - 15

    # Each point of score delta is worth $500, modified by volatility.
    price_adjustment = score_delta * 500 * volatility_factor

    final_price = 10000 + price_adjustment

    # Ensure the price is at least a minimum value (e.g., $500).
    return max(500, int(final_price))

critics = load_critics()
critics_by_name = {c['name']: c for c in critics}

critic_prompt = load_critic_prompt()

# Critic selection
selected_critic_name = cfg.selectbox("Critic", options=list(critics_by_name.keys()))
selected_critic = critics_by_name[selected_critic_name] 

# Voice service selection
voice_service = cfg.selectbox(
    "Voice Service",
    options=["No Voice", "OpenAI Voice", "ElevenLabs Voice"],
    index=0 # Default to No Voice
)

# --- session state initialization -------------------------------------------
if 'critique_data' not in st.session_state:
    st.session_state.critique_data = None
if 'audio_to_download' not in st.session_state:
    st.session_state.audio_to_download = None

# --- drag-and-drop -----------------------------------------------------------
if 'upload' not in st.session_state:
    st.session_state.upload = None

if st.session_state.upload:
    st.image(st.session_state.upload, use_container_width=True)
    if st.button("Remove Image"):
        st.session_state.upload = None
        st.session_state.critique_data = None # Clear critique on image removal
        st.session_state.audio_to_download = None
        st.rerun()
else:
    st.session_state.upload = st.file_uploader(
        "Drop an image here or click to browse",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=False,
    )
    if st.session_state.upload:
        st.rerun()

# --- chat-&-voice ------------------------------------------------------------
your_pitch = st.text_area("Your Pitch")
if st.button("CRITIQUE!", type="primary", disabled=not st.session_state.upload):
    st.session_state.critique_data = None # Clear previous critique
    st.session_state.audio_to_download = None
    
    # Prepare the prompt for the LLM
    critic_data_for_prompt = selected_critic.copy()
    scoring_categories_str = "\n".join([f"- **{cat}**" for cat in selected_critic['scoring_categories']])
    critic_data_for_prompt['scoring_categories'] = scoring_categories_str
    prompt = critic_prompt.format(pitch=your_pitch, **critic_data_for_prompt)
    
    # Encode the image
    image_bytes = st.session_state.upload.getvalue()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = st.session_state.upload.type

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                },
            ],
        }
    ]

    client = OpenAI(api_key=st.secrets["openai_key"])
    with st.spinner("Critiquing..."):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},  # Enforce JSON output
        )
        critique_json = json.loads(response.choices[0].message.content)
        
        # Calculate and add the price to the critique data
        scores = critique_json.get("scores", {})
        price = calculate_price(scores, selected_critic['snootiness'])
        critique_json['price'] = price
        st.session_state.critique_data = critique_json

        # --- logging -------------------------------------------------------------
        LOGS_DIR = Path("logs")
        LOGS_DIR.mkdir(exist_ok=True)
        db = TinyDB(LOGS_DIR / "session_log.json")
        db.insert({
            "ts": datetime.datetime.utcnow().isoformat(),
            "pitch": your_pitch,
            "filename": st.session_state.upload.name if st.session_state.upload else None,
            "response": st.session_state.critique_data,
            "critic": selected_critic_name,
            "voice_service": voice_service
        })

# --- display critique from session state --------------------------------------
if st.session_state.critique_data:
    speech_raw = st.session_state.critique_data.get("speech_raw", "I have nothing to say.")
    scores = st.session_state.critique_data.get("scores", {})
    price = st.session_state.critique_data.get("price", 0)

    # Display the final offer price
    st.subheader("The Verdict")
    st.metric(label="Offer Price", value=f"${price:,}")

    # Display critique in an expander
    with st.expander("View Full Critique & Scores", expanded=False):
        st.markdown("#### Full Monologue")
        st.markdown(speech_raw)
        st.markdown("---")
        # Display scores
        if scores:
            st.markdown("#### Scores")
            cols = st.columns(len(scores))
            for i, (key, value) in enumerate(scores.items()):
                with cols[i]:
                    st.metric(label=key, value=f"{value}/10")


    # --- Voice Generation & Download ---
    if voice_service != "No Voice" and st.session_state.critique_data and not st.session_state.audio_to_download:
        with st.spinner("Generating audio..."):
            if voice_service == "ElevenLabs Voice":
                try:
                    audio_buf = io.BytesIO()
                    if not elabs:
                        st.error("ElevenLabs API key not found. Please add it to your secrets.")
                        st.stop()

                    # ElevenLabs TTS (streaming)
                    audio_stream = elabs.text_to_speech.stream(
                        text=speech_raw,
                        voice_id=selected_critic['eleven_voice_id']
                    )
                    for chunk in audio_stream:
                        audio_buf.write(chunk)
                    
                    audio_buf.seek(0)
                    st.session_state.audio_to_download = audio_buf.read() # For download button
                    
                    # We need a new buffer for autoplay since read() consumed the other one
                    autoplay_buf = io.BytesIO(st.session_state.audio_to_download)
                    autoplay_audio(autoplay_buf)
                except Exception as e:
                    st.error(f"Error with ElevenLabs: {e}")

            elif voice_service == "OpenAI Voice":
                try:
                    # OpenAI TTS
                    response = client.audio.speech.create(
                        model="tts-1",
                        voice=selected_critic['openai_voice_id'],
                        input=speech_raw,
                    )
                    st.session_state.audio_to_download = response.content
                    # OpenAI API returns the audio content directly
                    autoplay_audio(io.BytesIO(st.session_state.audio_to_download))
                except Exception as e:
                    st.error(f"Error with OpenAI TTS: {e}")

    if st.session_state.audio_to_download:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="Download Critique (MP3)",
            data=st.session_state.audio_to_download,
            file_name=f"critique_{selected_critic_name.lower().replace(' ', '_')}_{ts}.mp3",
            mime="audio/mpeg"
        )



