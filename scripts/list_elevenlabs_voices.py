import os
import toml
from elevenlabs.client import ElevenLabs

# Path to the secrets.toml file
SECRETS_PATH = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")

def get_elevenlabs_api_key():
    """Reads the ElevenLabs API key from the .streamlit/secrets.toml file."""
    try:
        with open(SECRETS_PATH, "r") as f:
            secrets = toml.load(f)
        return secrets.get("elabs_key")
    except FileNotFoundError:
        print(f"Error: Secrets file not found at {SECRETS_PATH}")
        print("Please make sure the .streamlit/secrets.toml file exists and contains your API key.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the secrets file: {e}")
        return None

def list_voices():
    """Fetches and lists all available voices from the ElevenLabs API."""
    api_key = get_elevenlabs_api_key()
    if not api_key:
        return

    try:
        client = ElevenLabs(api_key=api_key)
        voices = client.voices.get_all()

        if not voices.voices:
            print("No voices found for your account.")
            return

        print("Available ElevenLabs Voices:")
        print("-" * 50)
        # Sort voices by category, then by name
        sorted_voices = sorted(voices.voices, key=lambda v: (v.category, v.name))
        
        for voice in sorted_voices:
            print(f"Name: {voice.name}")
            print(f"  Voice ID: {voice.voice_id}")
            if voice.description:
                print(f"  Description: {voice.description}")
            if voice.labels:
                # Format labels for better readability
                label_str = ', '.join([f"{k.replace('_', ' ').title()}: {v}" for k, v in voice.labels.items()])
                print(f"  Labels: {label_str}")
            print(f"  Category: {voice.category}")
            print("-" * 20)


        print("-" * 50)
        print(f"Found {len(voices.voices)} voices.")

    except Exception as e:
        print(f"An error occurred while fetching voices from ElevenLabs: {e}")
        print("Please check your API key and network connection.")

if __name__ == "__main__":
    list_voices()
