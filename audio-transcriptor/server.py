import os
import wave
import datetime
from flask import Flask, render_template, send_file
from flask_socketio import SocketIO, emit
from g4f.client import Client
from g4f import Provider
from faster_whisper import WhisperModel

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
RAW_DIR = os.path.join(TRANSCRIPTS_DIR, "raw")
CLEANED_DIR = os.path.join(TRANSCRIPTS_DIR, "cleaned")
AUDIO_PATH = os.path.join(BASE_DIR, "lecture.wav")

os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLEANED_DIR, exist_ok=True)

audio_buffer = bytearray()

print("⏳ Loading faster-whisper model...")
model = WhisperModel("small", device="cpu", compute_type="int8")
print("✅ Model loaded.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download")
def download_transcript():
    files = sorted(
        [f for f in os.listdir(RAW_DIR) if f.startswith("transcript_of_")],
        reverse=True
    )
    if not files:
        return "No transcript found", 404
    return send_file(os.path.join(RAW_DIR, files[0]), as_attachment=True)


@app.route("/download_cleaned")
def download_cleaned():
    files = sorted(
        [f for f in os.listdir(CLEANED_DIR)
         if f.startswith("lecture_cleaned_")],
        reverse=True
    )
    if not files:
        return "No cleaned transcript found", 404
    return send_file(os.path.join(CLEANED_DIR, files[0]), as_attachment=True)


@socketio.on("connect")
def handle_connect():
    print("🔌 Client connected")
    socketio.emit("ready")


@socketio.on("audio")
def handle_audio(data):
    global audio_buffer
    if data:
        audio_buffer += data


@socketio.on("stop")
def handle_stop():
    global audio_buffer

    print("🛑 Received stop. Saving and transcribing...")

    with wave.open(AUDIO_PATH, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(audio_buffer)

    segments, info = model.transcribe(AUDIO_PATH)
    full_text = "".join(segment.text for segment in segments)

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    raw_path = os.path.join(RAW_DIR, f"transcript_of_{ts}.md")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write("# Транскрипт лекции\n\n")
        f.write(full_text)
    print("✅ Saved raw transcript.")

    # Seek valid provider.
    client = None
    for provider in Provider.__providers__:
        try:
            print(f"🔍 Testing provider: {provider.__name__}")
            temp_client = Client(provider=provider)
            temp_response = temp_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Проверка"}],
                web_search=False
            )
            print(f"✅ Provider {provider.__name__} is working!")
            client = temp_client
            break
        except Exception as e:
            print(f"❌ Provider {provider.__name__} is not working!: {e}")

    if not client:
        print("❌ Cannot find a working GPT provider. GPT-processing is disabled.")

    if client:
        try:
            gpt_prompt = (
                f"Преобразуй транскрипт лекции в структурированный конспект "
                f"с абзацами и пунктуацией. "
                f"Учитывай, что лекция может содержать техническую и "
                f"математическую терминологию, включая англоязычные слова, "
                f"буквенные наименования и математические операторы (сумма, "
                f"произведение, интеграл и т.д.). "
                f"Нельзя добавлять новый текст от себя, за исключением случаев, "
                f"когда очевидно, что пропущено какое-то слово (или несколько) "
                f"из-за несовершенства технологии распознавания речи. "
                f"Сразу выведи весь готовый текст. "
                f"\nДалее идет транскрипт лекции:\n\n{full_text}"
            )
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": gpt_prompt}],
                web_search=False
            )
            cleaned = response.choices[0].message.content
            cleaned_path = os.path.join(
                CLEANED_DIR, f"lecture_from_{ts}.md")
            with open(cleaned_path, "w", encoding="utf-8") as f:
                f.write("# Конспект лекции\n\n")
                f.write(cleaned)
            print("✅ Saved clean summary.")
        except Exception as e:
            print(f"⚠️ Error while generating summary: {e}")
    else:
        print("⚠️ Skipping summary generation — no available provider.")

    audio_buffer = bytearray()


@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Client disconnected")


if __name__ == "__main__":
    socketio.run(app, port=5000, debug=True)
