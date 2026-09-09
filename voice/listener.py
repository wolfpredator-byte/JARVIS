import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel


SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 5


class VoiceListener:
    def __init__(self):
        print("Caricamento modello vocale...")

        self.model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8"
        )

        print("Modello vocale pronto.")

    def listen(self) -> str:
        print("\n🎙️ JARVIS sta ascoltando...")

        audio = sd.rec(
            int(RECORD_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32"
        )

        sd.wait()

        print("🧠 Elaborazione voce...")

        audio = np.squeeze(audio)

        segments, info = self.model.transcribe(
            audio,
            language="it",
            beam_size=5
        )

        text = ""

        for segment in segments:
            text += segment.text

        text = text.strip()

        if text:
            print(f"Tu: {text}")
        else:
            print("Non ho capito nulla.")

        return text