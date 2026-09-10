import win32com.client


# SAPI speech flags
SPEAK_ASYNC = 1
PURGE_BEFORE_SPEAK = 2


class VoiceSpeaker:
    def __init__(self):
        self.voice = win32com.client.Dispatch(
            "SAPI.SpVoice"
        )

        self.voice.Volume = 100

        # SAPI usa una scala diversa da pyttsx3:
        # circa -10 / +10
        self.voice.Rate = 0

        self._set_italian_voice()

    def _set_italian_voice(self):
        voices = self.voice.GetVoices()

        for index in range(voices.Count):
            token = voices.Item(index)

            description = (
                token.GetDescription()
                .lower()
            )

            try:
                language = (
                    token.GetAttribute("Language")
                    .lower()
                )
            except Exception:
                language = ""

            if (
                "italian" in description
                or "italiano" in description
                or language in ["410", "0410"]
            ):
                self.voice.Voice = token

                print(
                    "Voce italiana selezionata: "
                    f"{token.GetDescription()}"
                )

                return

        print(
            "[TTS] Nessuna voce italiana "
            "identificata automaticamente."
        )

    def speak(self, text: str):
        if not text:
            return

        # Cancella una frase precedente,
        # poi parte in background
        self.stop()

        self.voice.Speak(
            text,
            SPEAK_ASYNC
        )

    def stop(self):
        try:
            self.voice.Speak(
                "",
                SPEAK_ASYNC | PURGE_BEFORE_SPEAK
            )

        except Exception as error:
            print(
                f"[TTS STOP ERROR]: {error}"
            )