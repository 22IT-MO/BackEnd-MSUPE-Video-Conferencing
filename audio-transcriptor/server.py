from flask import Flask, render_template, send_file
from flask_socketio import SocketIO, emit
from vosk import Model, KaldiRecognizer
import numpy as np
from scipy import signal
import json
import os
import datetime
from g4f.client import Client

# Setting up Flask + SocketIO.
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Path to the model.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "vosk-model-small-ru-0.22")


# Buffer size threshold in bytes (e.g., 1 second of audio at 16kHz, 16-bit).
BUFFER_THRESHOLD = 32000

print("⏳ Loading model...")
model = Model(MODEL_PATH)
print("✅ Model loaded!")

# Create a recognizer with 16kHz frequency.
rec = KaldiRecognizer(model, 16000)

# Buffer for accumulating lecture text.
lecture_transcript = []

# Buffer for accumulating the audio stream.
full_audio_buffer = bytearray()
current_text_start_time = None


# Route to the main page.
@app.route("/")
def index():
    return render_template("index.html")


# Route to download the ready transcript.
@app.route("/download")
def download_transcript():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"transcript_of_{timestamp}.md"
    path = os.path.join("transcripts", filename)

    os.makedirs("transcripts", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Lecture Transcript\n\n")
        for entry in lecture_transcript:
            f.write(f"**[{entry['time']}]** {entry['text']}\n\n")

    return send_file(path, as_attachment=True)


@app.route("/download_cleaned")
def download_cleaned_transcript():
    files = sorted(
        [f for f in os.listdir("transcripts")
         if f.startswith("lecture_cleaned_")],
        reverse=True,
    )
    if not files:
        return "No cleaned transcripts available", 404
    path = os.path.join("transcripts", files[0])
    return send_file(path, as_attachment=True)


def improve_transcript(raw_text):
    client = Client()
    content = f"Отформатируй этот транскрипт в связный конспект, добавь абзацы и пунктуацию. Игнорируй тайм-коды. Выдай сразу конспект:\n\n{raw_text}"
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        web_search=False,
    )
    return response.choices[0].message.content


# Client connection handler.
@socketio.on("connect")
def handle_connect():
    print("🔌 Client connected")
    emit("server_message", {"message": "Connection established!"})


# Audio reception handler.
@socketio.on("audio")
def handle_audio(data):
    global full_audio_buffer, current_text_start_time

    audio_bytes = data
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

    number_of_samples = int(len(audio_np) * 16000 / 48000)
    resampled = signal.resample(audio_np, number_of_samples)
    resampled = resampled.astype(np.int16).tobytes()

    full_audio_buffer += resampled

    if len(full_audio_buffer) >= BUFFER_THRESHOLD:  # 1 second of audio.
        if rec.AcceptWaveform(bytes(full_audio_buffer)):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text.strip():
                # Use the fixed start time of speech.
                if current_text_start_time is None:
                    current_text_start_time = datetime.datetime.now().strftime(
                        "%H:%M:%S"
                    )
                lecture_transcript.append(
                    {"time": current_text_start_time, "text": text}
                )
                emit("text", {"text": text, "time": current_text_start_time})
            current_text_start_time = None  # Reset after finishing the line.
        else:
            partial = json.loads(rec.PartialResult())
            text = partial.get("partial", "")
            if text.strip():
                if current_text_start_time is None:
                    current_text_start_time = datetime.datetime.now().strftime(
                        "%H:%M:%S"
                    )
                emit("partial_text", {"text": text,
                     "time": current_text_start_time})

        full_audio_buffer = bytearray()


# Lecture stop handler.
@socketio.on("stop")
def handle_stop():
    global lecture_transcript

    print("🛑 Lecture stopped. Improving transcript...")

    # Glue all text together.
    full_text = "\n".join(
        f"[{entry['time']}] {entry['text']}" for entry in lecture_transcript
    )

    # Generating improved text through ChatGPT.
    improved_text = improve_transcript(full_text)

    # Saving.
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs("transcripts", exist_ok=True)
    path = os.path.join("transcripts", f"lecture_cleaned_{timestamp}.md")

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Конспект лекции\n\n")
        f.write(improved_text)

    print("✅ Improved transcript saved!")


# Client disconnection handler.
@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Client disconnected")


# Run server.
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
