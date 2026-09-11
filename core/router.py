import re
import unicodedata

from core.code_agent import find_verified_fix
from core.context import get_active_window_context
from core.session import session
from difflib import SequenceMatcher
from tools.windows import open_application
from tools.projects import (
    open_project_folder,
    list_project_files,
    read_project_file,
    find_file_in_project,
    find_project_path,
    write_project_file,
    restore_project_file
    
)
from tools.diagnostics import (
    get_file_diagnostics,
    get_preflight_diagnostics,
    format_diagnostics,
    diagnostics_score
)
from core.ai import analyze_code

from tools.code_edit import (
    prepare_edits,
    create_backup,
    apply_content_if_unchanged,
    restore_content
)
from core.response import (
    JarvisResponse,
    build_spoken_summary
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
    # CONFERMA STRUCTURED EDIT
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
        session.pending_new_content
        is not None
        and any(
            phrase == command
            or phrase in command
            for phrase in confirmation_phrases
        )
    ):

        if (
            not session.last_project
            or not session.last_file
            or session.pending_original_content
            is None
        ):
            session.clear_pending_edit()

            return (
                "Ho perso il contesto "
                "della modifica."
            )

        # Backup PRIMA di toccare il file
        backup_path = create_backup(
            session.last_project,
            session.last_file
        )

        if backup_path is None:
            return (
                "Non sono riuscito a creare "
                "il backup. Per sicurezza "
                "non ho modificato il file."
            )

        success, error = (
            apply_content_if_unchanged(
                project_name=(
                    session.last_project
                ),
                file_name=(
                    session.last_file
                ),
                expected_original=(
                    session.pending_original_content
                ),
                new_content=(
                    session.pending_new_content
                )
            )
        )

        if not success:
            session.clear_pending_edit()

            print(
                f"[EDIT ERROR]: {error}"
            )

            return (
                "Non ho applicato la modifica. "
                + error
            )

        # ----------------------------
        # VERIFICA POST-MODIFICA
        # ----------------------------

        after_diagnostics = (
            get_file_diagnostics(
                session.last_project,
                session.last_file
            )
        )

        after_score = diagnostics_score(
            after_diagnostics
        )

        before_score = (
            session.pending_before_score
            if session.pending_before_score
            is not None
            else 0
        )

        diagnostics_text = (
            format_diagnostics(
                after_diagnostics
            )
        )

        print(
            "\n[POST-FIX PYRIGHT]\n"
            + diagnostics_text
        )

        # Se la situazione peggiora,
        # rollback AUTOMATICO
        if after_score > before_score:
            session.last_failed_edits = session.pending_edits
            session.last_failed_diagnostics = diagnostics_text

            restored = restore_content(
                session.last_project,
                session.last_file,
                session.pending_original_content
            )

            session.clear_pending_edit()

            if restored:
                return (
                    "La modifica peggiorava "
                    "la diagnostica. "
                    "L'ho annullata automaticamente."
                )

            return (
                "La modifica ha peggiorato "
                "la diagnostica e il rollback "
                "automatico non è riuscito."
            )

        session.last_diagnostics = (
            diagnostics_text
        )

        session.clear_pending_edit()

        if after_score == 0:
            session.last_failed_edits = None
            session.last_failed_diagnostics = None

            return (
                "Modifica applicata. "
                "Pyright non rileva più problemi."
            )

        if after_score < before_score:
            session.last_failed_edits = None
            session.last_failed_diagnostics = None

            return (
                "Modifica applicata. "
                "La diagnostica è migliorata, "
                "ma restano ancora alcuni problemi."
            )

        return (
            "Modifica applicata. "
            "La diagnostica non è peggiorata, "
            "ma il problema deve essere "
            "controllato ancora."
        )

        # ----------------------------
    # CODING AGENT V0.2
    # AUTO RETRY + MODEL ESCALATION
    # ----------------------------

    retry_requested = (
        similar_to(command, "riprova")
        or "prova ancora" in command
        or "ritenta" in command
        or "prova un altra soluzione" in command
        or "prova un'altra soluzione" in command
    )

    fix_requested = (
        similar_to(command, "sistemalo")
        or "correggilo" in command
        or "risolvi il problema" in command
    )

    if retry_requested or fix_requested:

        if (
            not session.last_project
            or not session.last_file
        ):
            return (
                "Non ho un problema precedente "
                "da correggere."
            )

        code = read_project_file(
            session.last_project,
            session.last_file
        )

        if code is None:
            return (
                "Non riesco a leggere il file."
            )

        before_diagnostics = (
            get_file_diagnostics(
                session.last_project,
                session.last_file
            )
        )

        diagnostics_text = (
            format_diagnostics(
                before_diagnostics
            )
        )

        print(
            "\n"
            + "=" * 60
            + "\nCODING AGENT V0.2\n"
            + "=" * 60
        )

        result = find_verified_fix(
            project_name=(
                session.last_project
            ),
            file_name=(
                session.last_file
            ),
            code=code,
            before_diagnostics=(
                before_diagnostics
            ),
            diagnostics_text=(
                diagnostics_text
            ),
            analysis_context=(
                session.last_ai_response
            ),
            previous_failed_edits=(
                session.last_failed_edits
                if retry_requested
                else None
            ),
            previous_failed_diagnostics=(
                session.last_failed_diagnostics
                if retry_requested
                else None
            )
        )

        # ----------------------------
        # NESSUNA SOLUZIONE
        # ----------------------------

        if not result.success:

            session.last_failed_edits = (
                result.last_failed_edits
            )

            session.last_failed_diagnostics = (
                result.last_failed_diagnostics
            )

            return JarvisResponse(
                display=result.report,
                speech=(
                    "Ho testato automaticamente "
                    "diverse correzioni e ho anche "
                    "aumentato progressivamente "
                    "il modello utilizzato, ma non "
                    "ho trovato una soluzione "
                    "verificata."
                )
            )

        # ----------------------------
        # SOLUZIONE VERIFICATA
        # ----------------------------

        if (
            result.edits is None
            or result.new_content is None
            or result.diff is None
        ):
            return (
                "Ho trovato una possibile "
                "correzione, ma il risultato "
                "interno non è valido."
            )

        session.pending_edits = (
            result.edits
        )

        session.pending_original_content = (
            code
        )

        session.pending_new_content = (
            result.new_content
        )

        session.pending_diff = (
            result.diff
        )

        session.pending_before_score = (
            result.before_score
        )

        session.last_failed_edits = None
        session.last_failed_diagnostics = None

        print(
            "\n"
            + "=" * 60
            + "\nCORREZIONE VERIFICATA\n"
            + "=" * 60
            + "\n"
            + f"Modello: "
            + f"{result.model_name}\n"
            + f"Candidato: "
            + f"{result.attempt_number}\n"
            + f"Pyright: "
            + f"{result.before_score} "
            + "→ "
            + f"{result.after_score}\n"
            + "=" * 60
        )

        print(
            "\n"
            + "=" * 60
            + "\nMODIFICA PROPOSTA\n"
            + "=" * 60
            + "\n"
            + result.diff
            + "\n"
            + "=" * 60
        )

        return (
            f"Ho trovato una correzione "
            f"verificata usando "
            f"{result.model_name}. "
            "La diagnostica migliora. "
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
        session.fix_retry_count = 0
        session.last_failed_edits = None
        session.last_failed_diagnostics = None

        spoken_response = build_spoken_summary(
            full_text=response,
            file_name=context.current_file,
            issue_count=len(diagnostics)
        )

        return JarvisResponse(
            display=response,
            speech=spoken_response
        )

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

