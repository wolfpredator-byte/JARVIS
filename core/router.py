import re

from core.context import get_active_window_context
from tools.windows import open_application


def normalize_command(command: str) -> str:
    command = command.strip().lower()

    command = re.sub(
        r"[,.:;!?]",
        " ",
        command
    )

    command = re.sub(
        r"\s+",
        " ",
        command
    ).strip()

    # Correzioni comuni di Whisper
    command = re.sub(
        r"\ba\s+pri\b",
        "apri",
        command
    )

    return command

def is_shutdown_command(command: str) -> bool:
    command = normalize_command(command)

    # Elimina eventuale wake word rimasta nella trascrizione
    command = re.sub(
        r"\bhey\s+jarvis\b",
        "",
        command
    )

    command = re.sub(
        r"\bjarvis\b",
        "",
        command
    )

    command = re.sub(
        r"\s+",
        " ",
        command
    ).strip()

    shutdown_commands = {
        "spegniti",
        "esci",
        "termina",
        "chiudi",
        "vai offline",
        "sistema offline",
        "spegni il sistema",
        "spegni jarvis",
    }

    return command in shutdown_commands


def handle_context_command(command: str) -> str | None:

    context_phrases = [
        "cosa sto usando",
        "che programma sto usando",
        "quale programma sto usando",
        "che app sto usando",
        "quale app sto usando",
        "che finestra ho aperta",
        "quale finestra ho aperta",
        "cosa ho aperto",
        "dove sono",
    ]

    if not any(
        phrase in command
        for phrase in context_phrases
    ):
        return None

    context = get_active_window_context()

    if context is None:
        return "Non riesco a rilevare la finestra attiva."

    if context.title:
        return (
            f"Stai usando {context.application_name}. "
            f"La finestra attiva è {context.title}."
        )

    return (
        f"Stai usando {context.application_name}."
    )


def handle_command(command: str):
    command = normalize_command(command)

    print(
        f"[DEBUG NORMALIZED]: {repr(command)}"
    )

    # ----------------------------
    # CONTEXT AWARENESS
    # ----------------------------

    context_response = handle_context_command(
        command
    )

    if context_response is not None:
        return context_response

    # ----------------------------
    # APERTURA APPLICAZIONI
    # ----------------------------

    match = re.search(
        r"apri\s*(.+)",
        command
    )

    if match:
        app_name = match.group(1).strip()

        if not app_name:
            return "Quale applicazione devo aprire?"

        success = open_application(
            app_name
        )

        if success:
            return (
                f"Sto aprendo {app_name}."
            )

        return (
            f"Non sono riuscito ad aprire {app_name}."
        )

    return "Comando non riconosciuto."