import pyttsx3


class VoiceSpeaker:
    def __init__(self):
        self.engine = pyttsx3.init()

        self.engine.setProperty("rate", 175)
        self.engine.setProperty("volume", 1.0)

        self._set_italian_voice()

    def _set_italian_voice(self):
        voices = self.engine.getProperty("voices")

        for voice in voices:
            name = voice.name.lower()

            languages = " ".join(
                lang.decode(errors="ignore")
                if isinstance(lang, bytes)
                else str(lang)
                for lang in getattr(voice, "languages", [])
            ).lower()

            if (
                "italian" in name
                or "italiano" in name
                or "it-it" in languages
            ):
                self.engine.setProperty("voice", voice.id)

                print(f"Voce italiana selezionata: {voice.name}")
                return

        print(
            "ATTENZIONE: nessuna voce italiana trovata. "
            "Uso la voce predefinita di Windows."
        )

    def speak(self, text: str):
        if not text:
            return

        print(f"JARVIS: {text}")

        self.engine.say(text)
        self.engine.runAndWait()