import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


SAMPLE_RATE = 16000
CHANNELS = 1

# Ogni blocco audio dura 100 ms
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

# Sensibilità del microfono
SILENCE_THRESHOLD = 0.012

# Dopo quanto silenzio consideriamo finita la frase
SILENCE_DURATION = 0.8

# Tempo massimo di una frase
MAX_RECORD_SECONDS = 10

# Quanto aspettiamo che l'utente inizi a parlare
START_TIMEOUT_SECONDS = 4


class VoiceListener:
    def __init__(self):
        print("Caricamento modello vocale...")

        self.model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8"
        )

        print("Modello vocale pronto.")

    def listen(self) -> str:
        print("\n🎙️ JARVIS sta ascoltando...")

        audio_chunks = []

        speech_started = False
        silence_time = 0.0

        start_time = time.monotonic()

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_SIZE
        ) as stream:

            while True:
                chunk, overflowed = stream.read(CHUNK_SIZE)

                if overflowed:
                    continue

                chunk = np.squeeze(chunk)

                # Volume medio del blocco
                rms = float(
                    np.sqrt(
                        np.mean(
                            np.square(chunk)
                        )
                    )
                )

                elapsed = time.monotonic() - start_time

                # -------------------------
                # Non hai ancora parlato
                # -------------------------
                if not speech_started:
                    if rms > SILENCE_THRESHOLD:
                        speech_started = True
                        audio_chunks.append(chunk)

                        print("🗣️ Voce rilevata.")

                    elif elapsed >= START_TIMEOUT_SECONDS:
                        print("JARVIS: Non ho rilevato la tua voce.")
                        return ""

                    continue

                # -------------------------
                # Hai iniziato a parlare
                # -------------------------
                audio_chunks.append(chunk)

                if rms < SILENCE_THRESHOLD:
                    silence_time += CHUNK_DURATION
                else:
                    silence_time = 0.0

                # Fine frase
                if silence_time >= SILENCE_DURATION:
                    print("✅ Fine frase rilevata.")
                    break

                # Protezione: massimo 10 secondi
                if elapsed >= MAX_RECORD_SECONDS:
                    print("⏱️ Tempo massimo raggiunto.")
                    break

        if not audio_chunks:
            return ""

        # Unisce tutti i blocchi registrati
        audio = np.concatenate(audio_chunks)

        print("🧠 Elaborazione voce...")

        segments, info = self.model.transcribe(
            audio,
            language="it",
            beam_size=5,
            initial_prompt=(
                "Jarvis è un assistente per computer. "
                "Comandi comuni: apri Blender, "
                "apri Visual Studio Code, "
                "apri Notepad, apri Calc."
            )
        )

        text = "".join(
            segment.text
            for segment in segments
        ).strip()

        if text:
            print(f"Tu: {text}")
        else:
            print("JARVIS: Non ho capito nulla.")

        return text