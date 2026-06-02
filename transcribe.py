import whisper
import sys
import os

def main(audio_file):
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} not found.")
        return

    model = whisper.load_model("small")
    print(f"Transcribing {audio_file}...")
    result = model.transcribe(audio_file)
    print("\n--- Transcription Result ---")
    print(result["text"])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: docker run ... <audio_file>")
    else:
        main(sys.argv[1])