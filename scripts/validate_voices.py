import os
import yaml
import toml
from elevenlabs.client import ElevenLabs

# --- Configuration ---
SECRETS_PATH = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
CRITICS_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "lushfoil_critics_streamlit", "critics.yaml")

# OpenAI has a fixed set of voices
VALID_OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

# --- Helper Functions ---

def get_api_keys():
    """Reads API keys from the secrets.toml file."""
    try:
        with open(SECRETS_PATH, "r") as f:
            secrets = toml.load(f)
        elevenlabs_key = secrets.get("elabs_key")
        # The script doesn't need the openai key for validation, but this is how you'd get it.
        # openai_key = secrets.get("openai_key") 
        if not elevenlabs_key:
            print("Error: 'elabs_key' not found in secrets.toml")
            return None
        return elevenlabs_key
    except FileNotFoundError:
        print(f"Error: Secrets file not found at {SECRETS_PATH}")
        return None
    except Exception as e:
        print(f"An error occurred while reading secrets: {e}")
        return None

def get_elevenlabs_voices(api_key):
    """Fetches all available voice IDs from ElevenLabs."""
    try:
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()
        return {voice.voice_id for voice in voices.voices}
    except Exception as e:
        print(f"Error fetching ElevenLabs voices: {e}")
        return None

def load_critics():
    """Loads critic data from the YAML file."""
    try:
        with open(CRITICS_PATH, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Critics file not found at {CRITICS_PATH}")
        return None
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None

# --- Main Validation Logic ---

def validate_voices():
    """Validates all voice IDs in the critics.yaml file."""
    print("Starting voice ID validation...")
    
    api_key = get_api_keys()
    if not api_key:
        return

    print("Fetching available voices from ElevenLabs...")
    elevenlabs_voice_ids = get_elevenlabs_voices(api_key)
    if elevenlabs_voice_ids is None:
        return
    print(f"Found {len(elevenlabs_voice_ids)} voices in your ElevenLabs account.")

    critics = load_critics()
    if not critics:
        return

    print("\n--- Validation Report ---")
    all_valid = True

    for critic in critics:
        name = critic.get('name', 'Unknown Critic')
        openai_id = critic.get('openai_voice_id')
        eleven_id = critic.get('eleven_voice_id')
        
        # Validate OpenAI Voice ID
        if openai_id in VALID_OPENAI_VOICES:
            print(f"[V] {name}: OpenAI voice '{openai_id}' is valid.")
        else:
            print(f"[X] {name}: OpenAI voice '{openai_id}' is INVALID.")
            all_valid = False

        # Validate ElevenLabs Voice ID
        if eleven_id in elevenlabs_voice_ids:
            print(f"[V] {name}: ElevenLabs voice '{eleven_id}' is valid.")
        else:
            print(f"[X] {name}: ElevenLabs voice '{eleven_id}' is INVALID.")
            all_valid = False
        print("-" * 25)

    print("\n--- Summary ---")
    if all_valid:
        print("Success! All voice IDs in critics.yaml are valid.")
    else:
        print("Validation failed. One or more invalid voice IDs were found.")

if __name__ == "__main__":
    validate_voices()
