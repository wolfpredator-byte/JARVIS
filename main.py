import time

from core.router import handle_command
from voice.listener import VoiceListener
from voice.speaker import VoiceSpeaker


def main():
    print("JARVIS starting...")
    print("System online.")

    listener = VoiceListener()
    speaker = VoiceSpeaker()

    last_voice_end = 0.0

    while True:
        try:
            user_input = input(
                "\n[V] Parla | [Q] Esci | oppure scrivi un comando: "
            ).strip()

            print(f"[DEBUG INPUT]: {repr(user_input)}")

            # Uscita
            if user_input.lower() in ["q", "quit", "exit"]:
                print("JARVIS: Sistema offline.")
                break

            # Modalità vocale
            if user_input.lower() == "v":

                # Blocca eventuale V duplicata rimasta nel buffer
                now = time.monotonic()

                if now - last_voice_end < 1.0:
                    print("[DEBUG] Trigger vocale duplicato ignorato.")
                    continue

                command = listener.listen()

                # Salviamo il momento in cui l'ascolto è terminato
                last_voice_end = time.monotonic()

                if not command:
                    print("JARVIS: Non ho rilevato alcun comando.")
                    continue

            # Input vuoto
            elif user_input == "":
                continue

            # Comando scritto
            else:
                command = user_input

            # Spegnimento tramite voce/testo
            if command.lower() in [
                "esci",
                "chiudi",
                "exit",
                "jarvis chiudi",
                "jarvis, chiudi"
            ]:
                print("JARVIS: Sistema offline.")
                break

            response = handle_command(command)

            speaker.speak(response)
            
        except KeyboardInterrupt:
            print("\nJARVIS: Sistema offline.")
            break


if __name__ == "__main__":
    main()