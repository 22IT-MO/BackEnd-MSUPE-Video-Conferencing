import pyaudio
import json
from vosk import Model, KaldiRecognizer
from datetime import datetime
import os


def get_speaker_name(pyaudio_instance):
    # Get the name of the default input device
    info = pyaudio_instance.get_host_api_info_by_index(0)
    num_devices = info.get("deviceCount")
    for i in range(0, num_devices):
        device_info = pyaudio_instance.get_device_info_by_index(i)
        if device_info.get("maxInputChannels") > 0:
            # Return the name of the first active input source found
            return device_info.get("name")
    return "Unknown Speaker"


def main():
    # Path to the model directory
    model_path = "model/vosk-model-ru-0.42"
    # Initialize model
    model = Model(model_path)
    # Create Recognizer, 16 kHz frequency
    recognizer = KaldiRecognizer(model, 16000)
    # Setup PyAudio
    audio_channel = pyaudio.PyAudio()
    microphone_name = get_speaker_name(audio_channel)
    stream = audio_channel.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=8000,
    )
    stream.start_stream()
    print("System initialized. Listening...")
    # Create a new markdown file with a start-point timestamp
    start_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"transcript/transcript_of_{start_timestamp}.md"
    with open(filename, "w", encoding="utf-8") as trancript_file:
        trancript_file.write(f"# Transcript of Conversation\n\n")
        trancript_file.write(f"## Started at {start_timestamp}\n\n")

        recognized_any_text = False  # Flag to track if any text was recognized
        try:
            while True:
                # Read audio from microphone
                data = stream.read(4000, exception_on_overflow=False)
                # Check for silence
                if len(data) == 0:
                    continue
                # Send data to recognizer
                if recognizer.AcceptWaveform(data):
                    result = recognizer.Result()
                    # Convert result to JSON
                    text_json = json.loads(result)
                    # Output recognized text
                    recognized_text = text_json.get("text", "")
                    if recognized_text:
                        print(f"Recognized (full phrase): {recognized_text}")
                        # Create timestamp for the recognized phrase
                        phrase_timestamp = datetime.now().strftime(
                            "%Y.%m.%d -- %H:%M:%S"
                        )
                        # Use the microphone name as the speaker label
                        trancript_file.write(
                            f"- **{microphone_name} [{phrase_timestamp}]**: {recognized_text}\n"
                        )
                        recognized_any_text = (
                            True  # Set flag to True if text is recognized
                        )
                else:
                    # Partial result (speaking in progress)
                    partial_result = recognizer.PartialResult()
                    partial_json = json.loads(partial_result)
                    partial_text = partial_json.get("partial", "")
                    if partial_text:
                        print(f"Partial text (speaking): {partial_text}", end="\r")
        except KeyboardInterrupt:
            print("\nEnd session: Aborted by user.")
        finally:
            # Stop audiostream
            stream.stop_stream()
            stream.close()
            audio_channel.terminate()
    # Check if the file is empty or no text was recognized and delete if necessary
    if os.path.getsize(filename) == 0 or not recognized_any_text:
        os.remove(filename)
        print(f"Deleted empty file: {filename}")
    else:
        print(f"Saved recognized text to: {filename}")


if __name__ == "__main__":
    main()
