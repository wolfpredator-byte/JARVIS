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
            # Rimane in attesa finché non sente la wake word
            wakeword.wait_for_wake_word()

            print("JARVIS: Ti ascolto.")

            # Ora ascolta il comando vero
            command = listener.listen()

            if not command:
                print("JARVIS: Nessun comando rilevato.")
                continue

            command_lower = command.lower().strip()

            if command_lower in [
                "esci",
                "chiudi",
                "spegniti",
                "termina",
                "sistema offline"
            ]:
                speaker.speak("Sistema offline.")
                break

            response = handle_command(command)

            speaker.speak(response)

        except KeyboardInterrupt:
            print("\nJARVIS: Sistema offline.")
            break


if __name__ == "__main__":
    main()