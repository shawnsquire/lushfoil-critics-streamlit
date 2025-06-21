import streamlit as st
from openai import OpenAI
from elevenlabs import stream as elevenlabs_stream
from tinydb import TinyDB, Query
from pathlib import Path
import datetime, io, yaml, base64, json

st.set_page_config(page_title="Lushfoil Critics", page_icon="🎨", initial_sidebar_state="collapsed")

# --- config -----------------------------------------------------------------
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

critics = load_critics()
critics_by_name = {c['name']: c for c in critics}

critic_prompt = load_critic_prompt()

cfg = st.sidebar
cfg.title("Settings")

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
if st.button("CRITIQUE!", type="primary"):
    st.session_state.critique_data = None # Clear previous critique
    st.session_state.audio_to_download = None
    prompt = critic_prompt.format(pitch=your_pitch, **selected_critic)

    client = OpenAI(api_key=st.secrets["openai_key"])
    with st.spinner("Thinking..."):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},  # Enforce JSON output
        )
        st.session_state.critique_data = json.loads(response.choices[0].message.content)

# --- display critique from session state --------------------------------------
if st.session_state.critique_data:
    speech_raw = st.session_state.critique_data.get("speech_raw", "I have nothing to say.")
    scores = st.session_state.critique_data.get("scores", {})

    # Display critique in an expander
    with st.expander("View Critique Text", expanded=False):
        st.markdown(speech_raw)

    # Display scores
    if scores:
        st.write("### Scores")
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
                    # ElevenLabs TTS (streaming)
                    for pcm in elevenlabs_stream(
                        text=speech_raw,
                        voice=selected_critic['eleven_voice_id'],
                        api_key=st.secrets["elabs_key"]
                    ):
                        audio_buf.write(pcm)
                    
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


    # --- logging -------------------------------------------------------------
    db = TinyDB("session_log.json")
    db.insert({
        "ts": datetime.datetime.utcnow().isoformat(),
        "prompt": prompt,
        "response": st.session_state.critique_data,  # Log the full JSON object
        "critic": selected_critic_name,
        "voice_service": voice_service
    })
