from tools.windows import open_application


def handle_command(command: str):
    command = command.strip().lower()

    # Rimuove il nome Jarvis se viene usato all'inizio
    if command.startswith("jarvis"):
        command = command.removeprefix("jarvis").strip()

        if command.startswith(","):
            command = command[1:].strip()

    if command.startswith("apri "):
        app_name = command.removeprefix("apri ").strip()

        success = open_application(app_name)

        if success:
            return f"Sto aprendo {app_name}."

        return f"Non sono riuscito ad aprire {app_name}."

    return "Comando non riconosciuto."