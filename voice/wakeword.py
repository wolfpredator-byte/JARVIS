import numpy as np
import sounddevice as sd

from openwakeword.model import Model
from typing import cast


SAMPLE_RATE = 16000
CHUNK_SIZE = 1280


class WakeWordListener:
    def __init__(self):
        print("Caricamento wake word...")

        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx"
        )

        self.threshold = 0.5

        print("Wake word pronta.")

    def wait_for_wake_word(self):
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
                        return