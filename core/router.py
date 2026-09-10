import re
import unicodedata

from core.context import get_active_window_context
from core.session import session
from difflib import SequenceMatcher
from tools.windows import open_application
from tools.projects import (
    open_project_folder,
    list_project_files,
    read_project_file,
    write_project_file
)
from tools.diagnostics import (
    get_file_diagnostics,
    format_diagnostics
)
from core.ai import (
    analyze_code,
    generate_code_fix
)


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

    command = "".join(
        char
        for char in unicodedata.normalize("NFD", command)
        if unicodedata.category(char) != "Mn"
    )

    command = "".join(
    char
    for char in unicodedata.normalize("NFD", command)
    if unicodedata.category(char) != "Mn"
    )

    return command

def similar_to(
    command: str,
    target: str,
    threshold: float = 0.78
) -> bool:

    score = SequenceMatcher(
        None,
        command,
        target
    ).ratio()

    return score >= threshold

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
    context = get_active_window_context()

    context_phrases = [
        "cosa sto usando",
        "che programma sto usando",
        "quale programma sto usando",
        "che app sto usando",
        "che finestra ho aperta",
        "quale finestra ho aperta",
        "cosa ho aperto",
        "dove sono",
    ]

    project_phrases = [
        "che progetto sto usando",
        "quale progetto sto usando",
        "su che progetto sto lavorando",
        "a che progetto sto lavorando",
        "qual è il progetto aperto",
    ]

    file_phrases = [
        "che file sto usando",
        "quale file sto usando",
        "che file ho aperto",
        "quale file ho aperto",
        "su che file sto lavorando",
    ]

    # -------------------------
    # PROGETTO
    # -------------------------

    if any(
        phrase in command
        for phrase in project_phrases
    ):
        if context is None:
            return "Non riesco a rilevare il contesto."

        if context.project_name:
            return (
                f"Stai lavorando sul progetto "
                f"{context.project_name} in "
                f"{context.application_name}."
            )

        return (
            f"Stai usando {context.application_name}, "
            "ma non riesco ancora a identificare il progetto."
        )

    # -------------------------
    # FILE
    # -------------------------

    if any(
        phrase in command
        for phrase in file_phrases
    ):
        if context is None:
            return "Non riesco a rilevare il contesto."

        if context.current_file:
            return (
                f"Il file aperto è "
                f"{context.current_file}."
            )

        return "Non riesco a identificare il file aperto."

    # -------------------------
    # PROGRAMMA / FINESTRA
    # -------------------------

    if any(
        phrase in command
        for phrase in context_phrases
    ):
        if context is None:
            return "Non riesco a rilevare la finestra attiva."

        if context.title:
            return (
                f"Stai usando {context.application_name}. "
                f"La finestra attiva è {context.title}."
            )

        return (
            f"Stai usando "
            f"{context.application_name}."
        )

    return None


def handle_command(command: str):
    command = normalize_command(command)

    print(
        f"[DEBUG NORMALIZED]: {repr(command)}"
    )

    # ----------------------------
    # CONFERMA FIX
    # ----------------------------

    confirmation_phrases = [
        "si",
        "vai",
        "procedi",
        "applicalo",
        "applica la modifica",
        "fallo",
    ]

    if (
        session.pending_fix is not None
        and any(
            phrase == command
            or phrase in command
            for phrase in confirmation_phrases
        )
    ):
        if not session.last_project or not session.last_file:
            return "Ho perso il contesto della modifica."

        success = write_project_file(
            session.last_project,
            session.last_file,
            session.pending_fix
        )

        if not success:
            return "Non sono riuscito a modificare il file."

        session.pending_fix = None

        diagnostics = get_file_diagnostics(
            session.last_project,
            session.last_file
        )

        diagnostics_text = format_diagnostics(
            diagnostics
        )

        print(
            "\n[POST-FIX PYRIGHT]\n"
            + diagnostics_text
        )

        session.last_diagnostics = diagnostics_text

        if not diagnostics:
            return (
                "Correzione applicata. "
                "Pyright non rileva più problemi nel file."
            )

        return (
            "Ho applicato la correzione, "
            f"ma Pyright segnala ancora "
            f"{len(diagnostics)} problemi."
        )

    # ----------------------------
    # PREPARA FIX
    # ---------------------------- 

    if (
        similar_to(command, "sistemalo")
        or "correggilo" in command
        or "risolvi il problema" in command
    ):
        if not session.last_project or not session.last_file:
            return (
                "Non ho un problema precedente "
                "da correggere."
            )

        code = read_project_file(
            session.last_project,
            session.last_file
        )

        if code is None:
            return "Non riesco a leggere il file."

        fix = generate_code_fix(
            code=code,
            file_name=session.last_file,
            project_name=session.last_project,
            diagnostics=(
                session.last_diagnostics
                or "Nessuna diagnostica disponibile."
            )
        )

        if not fix:
            return (
                "Non sono riuscito a preparare "
                "la correzione."
            )

        session.pending_fix = fix

        return (
            f"Ho preparato una correzione per "
            f"{session.last_file}. "
            "Vuoi che la applichi?"
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
    # PROGETTO ATTUALE
    # ----------------------------

    if (
        "apri la cartella del progetto" in command
        or "apri cartella progetto" in command
        or "apri la cartella di questo progetto" in command
    ):

        context = get_active_window_context()

        if context is None:
           return "Non riesco a rilevare il progetto attuale."

        if not context.project_name:
           return "Non riesco a capire su quale progetto stai lavorando."

        success = open_project_folder(
            context.project_name
        )

        if success:
           return (
               f"Apro la cartella del progetto "
               f"{context.project_name}."
           )

        return (
           f"Ho riconosciuto il progetto "
           f"{context.project_name}, "
           "ma non conosco ancora la sua posizione."
        )

    # ----------------------------
    # FILE DEL PROGETTO
    # ----------------------------

    if (
        "quali file ci sono nel progetto" in command
        or "che file ci sono nel progetto" in command
        or "mostrami i file del progetto" in command
    ):

        context = get_active_window_context()

        if context is None or not context.project_name:
            return "Non riesco a identificare il progetto."

        files = list_project_files(
            context.project_name
        )

        if not files:
            return (
                f"Non riesco a trovare i file del progetto "
                f"{context.project_name}."
            )

        print(
           "\n[PROJECT FILES]\n"
           + "\n".join(files)
        )

        return (
           f"Ho trovato {len(files)} file. "
           "Li ho mostrati nel terminale."
        )

    # ----------------------------
    # LEGGI FILE ATTUALE
    # ----------------------------

    read_file_phrases = [
        "leggi il file aperto",
        "leggi il file che ho aperto",
        "leggi questo file",
        "mostrami il file aperto",
        "mostrami il contenuto del file",
        "mostrami il contenuto di questo file",
    ]

    if any(
        phrase in command
        for phrase in read_file_phrases
    ):
        context = get_active_window_context()
   
        if context is None:
           return "Non riesco a rilevare il contesto attuale."

        if not context.project_name:
           return "Non riesco a identificare il progetto."

        if not context.current_file:
           return "Non riesco a identificare il file aperto."

        content = read_project_file(
           context.project_name,
           context.current_file
        )
  
        if content is None:
           return (
               f"Ho riconosciuto {context.current_file}, "
               "ma non riesco a leggerlo."
           )

        print(
            "\n"
            + "=" * 60
            + f"\nFILE: {context.current_file}\n"
            + "=" * 60
            + "\n"
            + content
            + "\n"
            + "=" * 60
        )

        line_count = len(content.splitlines())

        return (
            f"Ho letto {context.current_file}. "
            f"Contiene {line_count} righe. "
            "Ho mostrato il contenuto nel terminale."
       )


    # ----------------------------
    # CODING ASSISTANT
    # ----------------------------

    coding_phrases = [
        "spiegami questo file",
        "spiegami il file",
        "analizza questo file",
        "analizza il file",
        "controlla questo file",
        "trova bug",
        "trova il bug",
        "cosa non va in questo file",
        "cosa c'è che non va",
        "ci sono errori in questo file",
    ]

    if any(
        phrase in command
        for phrase in coding_phrases
    ):
        context = get_active_window_context()

        if context is None:
            return "Non riesco a rilevare il contesto."

        if not context.project_name:
            return "Non riesco a identificare il progetto."

        if not context.current_file:
            return "Non riesco a identificare il file aperto."

        content = read_project_file(
            context.project_name,
            context.current_file
        )

        if content is None:
            return (
                f"Non riesco a leggere "
                f"{context.current_file}."
            )

        print(
            f"\n[AI] Analisi di "
            f"{context.current_file}..."
        )

        diagnostics = get_file_diagnostics(
            context.project_name,
            context.current_file
        )

        diagnostics_text = format_diagnostics(
            diagnostics
        )

        print(
            "\n[PYRIGHT DIAGNOSTICS]\n"
            + diagnostics_text
        )

        response = analyze_code(
            code=content,
            file_name=context.current_file,
            project_name=context.project_name,
            request=command,
            diagnostics=diagnostics_text
        )

        session.last_project = context.project_name
        session.last_file = context.current_file
        session.last_request = command
        session.last_diagnostics = diagnostics_text
        session.last_ai_response = response
        

        print(
            "\n"
            + "=" * 60
            + "\nJARVIS AI\n"
            + "=" * 60
            + "\n"
            + response
            + "\n"
            + "=" * 60
        )

        return response

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
