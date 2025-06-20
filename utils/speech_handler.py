import assemblyai as aai # type: ignore
import os

# Set the API key from environment variables
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

def transcribe_audio(file_path):
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(file_path)
    return transcript.text
