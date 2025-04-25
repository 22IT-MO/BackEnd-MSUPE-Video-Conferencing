from flask import Flask, render_template, send_file
from flask_socketio import SocketIO, emit
from vosk import Model, KaldiRecognizer
import numpy as np
from scipy import signal
import json
import os
import datetime

# Настройка Flask + SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Путь к модели (замени на свой путь)
MODEL_PATH = (
    "model/vosk-model-small-ru-0.22"  # например "models/vosk-model-small-ru-0.22"
)

print("⏳ Загружаем модель...")
model = Model(MODEL_PATH)
print("✅ Модель загружена!")

# Создаём распознаватель с частотой 16kHz
rec = KaldiRecognizer(model, 16000)

# Буфер для накопления текста лекции
lecture_transcript = []

# Буфер для накопления аудио потока
full_audio_buffer = bytearray()
current_text_start_time = None


# Маршрут на главную страницу
@app.route("/")
def index():
    return render_template("index.html")


# Маршрут на скачивание готового транскрипта
@app.route("/download")
def download_transcript():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"transcript_of_{timestamp}.md"
    path = os.path.join("transcripts", filename)

    os.makedirs("transcripts", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Транскрипт лекции\n\n")
        for entry in lecture_transcript:
            f.write(f"**{entry['time']}** {entry['text']}\n\n")

    return send_file(path, as_attachment=True)


# Обработчик подключения клиента
@socketio.on("connect")
def handle_connect():
    print("🔌 Клиент подключился")
    emit("server_message", {"message": "Соединение установлено!"})


# Обработчик принятия аудио
@socketio.on("audio")
def handle_audio(data):
    global full_audio_buffer, current_text_start_time

    audio_bytes = data
    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

    number_of_samples = int(len(audio_np) * 16000 / 48000)
    resampled = signal.resample(audio_np, number_of_samples)
    resampled = resampled.astype(np.int16).tobytes()

    full_audio_buffer += resampled

    if len(full_audio_buffer) >= 32000:  # 1 секунда аудио
        if rec.AcceptWaveform(bytes(full_audio_buffer)):
            result = json.loads(rec.Result())
            text = result.get("text", "")
            if text.strip():
                # Используем зафиксированное время начала речи
                if current_text_start_time is None:
                    current_text_start_time = datetime.datetime.now().strftime(
                        "%H:%M:%S"
                    )
                lecture_transcript.append(
                    {"time": current_text_start_time, "text": text}
                )
                emit("text", {"text": text, "time": current_text_start_time})
            current_text_start_time = None  # Сброс после завершения строки
        else:
            partial = json.loads(rec.PartialResult())
            text = partial.get("partial", "")
            if text.strip():
                if current_text_start_time is None:
                    current_text_start_time = datetime.datetime.now().strftime(
                        "%H:%M:%S"
                    )
                emit("partial_text", {"text": text, "time": current_text_start_time})

        full_audio_buffer = bytearray()


# Обработчик окончания лекции
@socketio.on("stop")
def handle_stop():
    print("🛑 Лекция остановлена. Транскрипция сохранена.")


# Обработчик отключения клиента
@socketio.on("disconnect")
def handle_disconnect():
    print("❌ Клиент отключился")


# Запуск сервера
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
