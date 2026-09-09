import re

from tools.windows import open_application


def normalize_command(command: str) -> str:
    command = command.strip().lower()

    # Rimuove punteggiatura
    command = re.sub(r"[,.:;!?]", " ", command)

    # Riduce spazi multipli
    command = re.sub(r"\s+", " ", command).strip()

    # Errori comuni di Whisper
    command = re.sub(r"\ba\s+pri\b", "apri", command)

    return command


def handle_command(command: str):
    command = normalize_command(command)

    print(f"[DEBUG NORMALIZED]: {repr(command)}")

    match = re.search(r"apri\s*(.+)", command)

    if match:
        app_name = match.group(1).strip()

        if not app_name:
            return "Quale applicazione devo aprire?"

        success = open_application(app_name)

        if success:
            return f"Sto aprendo {app_name}."

        return f"Non sono riuscito ad aprire {app_name}."

    return "Comando non riconosciuto."