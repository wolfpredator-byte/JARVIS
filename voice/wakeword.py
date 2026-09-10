from typing import cast

import numpy as np
import sounddevice as sd

from openwakeword.model import Model


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

# Audio che continuiamo a registrare immediatamente
# dopo aver riconosciuto "Hey Jarvis"
POST_WAKE_SECONDS = 0.4
POST_WAKE_CHUNKS = int(
    POST_WAKE_SECONDS / (CHUNK_SIZE / SAMPLE_RATE)
)


class WakeWordListener:
    def __init__(self):
        print("Caricamento wake word...")

        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx"
        )

        self.threshold = 0.5

        print("Wake word pronta.")

    def wait_for_wake_word(self) -> np.ndarray:
        print("\n👂 In attesa di: Hey Jarvis...")

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK_SIZE
        ) as stream:

            while True:
                audio, overflowed = stream.read(CHUNK_SIZE)

                if overflowed:
                    continue

                audio = np.squeeze(audio)

                prediction = cast(
                    dict[str, float],
                    self.model.predict(audio)
                )

                for model_name, score in prediction.items():
                    if score >= self.threshold:
                        print(
                            f"⚡ Wake word rilevata "
                            f"({model_name}: {score:.2f})"
                        )

                        self.model.reset()

                        # Continua subito a registrare ciò che
                        # viene detto dopo "Hey Jarvis"
                        post_wake_audio = []

                        for _ in range(POST_WAKE_CHUNKS):
                            chunk, _ = stream.read(CHUNK_SIZE)
                            post_wake_audio.append(
                                np.squeeze(chunk)
                            )

                        if post_wake_audio:
                            audio_data = np.concatenate(
                                post_wake_audio
                            )

                            # Converte int16 -> float32,
                            # formato usato dal listener
                            return (
                                audio_data.astype(np.float32)
                                / 32768.0
                            )

                        return np.array(
                            [],
                            dtype=np.float32
                        )