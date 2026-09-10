import time

from core.router import handle_command

from voice.listener import VoiceListener
from voice.speaker import VoiceSpeaker
from voice.wakeword import WakeWordListener


def main():
    print("JARVIS starting...")
    print("System online.")

    listener = VoiceListener()
    speaker = VoiceSpeaker()
    wakeword = WakeWordListener()

    speaker.speak("Sistema online.")

    while True:
        try:
            # Aspetta la wake word
            wakeword.wait_for_wake_word()

            print("JARVIS: Ti ascolto.")

            # Ascolta il comando
            command = listener.listen()

            if not command:
                print("JARVIS: Nessun comando rilevato.")
                continue

            command_lower = command.lower().strip()

            # Comandi per spegnere Jarvis
            if command_lower in [
                "esci",
                "chiudi",
                "spegniti",
                "termina",
                "sistema offline"
            ]:
                speaker.speak("Sistema offline.")
                break

            # Invia il comando al router
            response = handle_command(command)

            print(f"[DEBUG RESPONSE]: {repr(response)}")

            # Lascia al microfono il tempo di rilasciare
            # il dispositivo audio
            time.sleep(0.3)

            # Risposta vocale
            speaker.speak(response)

        except KeyboardInterrupt:
            print("\nJARVIS: Sistema offline.")
            break


if __name__ == "__main__":
    main()