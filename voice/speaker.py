from typing import Any, cast

import pyttsx3


class VoiceSpeaker:
    def __init__(self):
        self.voice_id = self._find_italian_voice()

    def _find_italian_voice(self):
        engine = pyttsx3.init()

        voices = cast(
            list[Any],
            engine.getProperty("voices")
        )

        selected_voice = None

        for voice in voices:
            name = str(getattr(voice, "name", "")).lower()

            raw_languages = getattr(voice, "languages", []) or []

            if not isinstance(raw_languages, (list, tuple)):
                raw_languages = [raw_languages]

            languages = " ".join(
                lang.decode(errors="ignore")
                if isinstance(lang, bytes)
                else str(lang)
                for lang in raw_languages
            ).lower()

            if (
                "italian" in name
                or "italiano" in name
                or "it-it" in languages
            ):
                selected_voice = voice.id
                print(f"Voce italiana selezionata: {voice.name}")
                break

        engine.stop()

        return selected_voice

    def speak(self, text: str):
        if not text:
            return

        print(f"JARVIS: {text}")

        try:
            # Ricreiamo il motore per evitare problemi
            # dopo l'utilizzo del microfono
            engine = pyttsx3.init()

            engine.setProperty("rate", 175)
            engine.setProperty("volume", 1.0)

            if self.voice_id:
                engine.setProperty("voice", self.voice_id)

            engine.say(text)
            engine.runAndWait()
            engine.stop()

        except Exception as error:
            print(f"[TTS ERROR]: {error}")