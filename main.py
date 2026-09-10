import time

from core.router import handle_command, is_shutdown_command

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

            initial_audio = wakeword.wait_for_wake_word()

            print("JARVIS: Ti ascolto.")

            command = listener.listen(
                initial_audio=initial_audio
            )

            if not command:
                print("JARVIS: Nessun comando rilevato.")
                continue

            if is_shutdown_command(command):
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