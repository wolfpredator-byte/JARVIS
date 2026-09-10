from core.router import (
    handle_command,
    is_shutdown_command
)

from core.response import JarvisResponse

from voice.listener import VoiceListener
from voice.speaker import VoiceSpeaker
from voice.wakeword import WakeWordListener


def output_response(
    speaker: VoiceSpeaker,
    response: str | JarvisResponse
):
    # Risposta avanzata:
    # terminale lungo + voce corta
    if isinstance(response, JarvisResponse):

        print(
            "\n"
            + "=" * 60
            + "\nJARVIS\n"
            + "=" * 60
            + "\n"
            + response.display
            + "\n"
            + "=" * 60
        )

        speaker.speak(
            response.speech
        )

        return

    # Risposta normale
    print(
        f"\nJARVIS: {response}"
    )

    speaker.speak(response)


def main():
    print("JARVIS starting...")
    print("System online.")

    listener = VoiceListener()
    speaker = VoiceSpeaker()
    wakeword = WakeWordListener()

    speaker.speak(
        "Sistema online."
    )

    while True:
        try:
            initial_audio = (
                wakeword.wait_for_wake_word()
            )

            # IMPORTANTISSIMO:
            # se Jarvis sta ancora parlando,
            # "Hey Jarvis" lo interrompe subito
            speaker.stop()

            print(
                "JARVIS: Ti ascolto."
            )

            command = listener.listen(
                initial_audio=initial_audio
            )

            if not command:
                continue

            if is_shutdown_command(command):
                speaker.speak(
                    "Sistema offline."
                )

                break

            response = handle_command(
                command
            )

            output_response(
                speaker,
                response
            )

        except KeyboardInterrupt:
            speaker.stop()

            print(
                "\nJARVIS: Sistema offline."
            )

            break


if __name__ == "__main__":
    main()