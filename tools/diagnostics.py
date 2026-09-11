import json
import subprocess
import sys

from pathlib import Path
from uuid import uuid4

from tools.projects import (
    find_file_in_project,
    find_project_path,
)

def _run_pyright_on_path(
    project_path: Path,
    file_path: Path
) -> tuple[list[dict] | None, str]:

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pyright",
                "--outputjson",
                str(file_path)
            ],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

    except OSError as error:
        return (
            None,
            f"Errore durante l'avvio di Pyright: {error}"
        )

    # ATTENZIONE:
    # Pyright può restituire un exit code != 0
    # semplicemente perché ha trovato errori.
    # Quindi NON controlliamo returncode.

    if not result.stdout.strip():
        error_text = (
            result.stderr.strip()
            or "Pyright non ha restituito nessun output."
        )

        return None, error_text

    try:
        data = json.loads(
            result.stdout
        )

    except json.JSONDecodeError as error:
        return (
            None,
            f"Output Pyright non valido: {error}"
        )

    diagnostics = []

    for diagnostic in data.get(
        "generalDiagnostics",
        []
    ):
        start = (
            diagnostic
            .get("range", {})
            .get("start", {})
        )

        diagnostics.append(
            {
                "severity": diagnostic.get(
                    "severity",
                    "unknown"
                ),
                "message": diagnostic.get(
                    "message",
                    ""
                ),
                "line": (
                    start.get("line", 0) + 1
                ),
                "character": (
                    start.get(
                        "character",
                        0
                    ) + 1
                )
            }
        )

    return diagnostics, ""

def get_file_diagnostics(
    project_name: str,
    file_name: str
) -> list[dict]:

    project_path = find_project_path(
        project_name
    )

    if project_path is None:
        print(
            "[PYRIGHT ERROR]: "
            "Progetto non trovato."
        )
        return []

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        print(
            "[PYRIGHT ERROR]: "
            f"File non trovato: {file_name}"
        )
        return []

    diagnostics, error = (
        _run_pyright_on_path(
            project_path,
            file_path
        )
    )

    if diagnostics is None:
        print(
            f"[PYRIGHT ERROR]: {error}"
        )
        return []

    return diagnostics


def format_diagnostics(
    diagnostics: list[dict]
) -> str:

    if not diagnostics:
        return "Nessun errore o warning rilevato."

    lines = []

    for diagnostic in diagnostics:
        severity = diagnostic["severity"].upper()
        line = diagnostic["line"]
        message = diagnostic["message"]

        lines.append(
            f"[{severity}] Riga {line}: {message}"
        )

    return "\n".join(lines)

def diagnostics_score(
    diagnostics: list[dict]
) -> int:

    weights = {
        "error": 100,
        "warning": 10,
        "information": 1,
        "unknown": 1,
    }

    score = 0

    for diagnostic in diagnostics:
        severity = diagnostic.get(
            "severity",
            "unknown"
        ).lower()

        score += weights.get(
            severity,
            1
        )

    return score

def get_preflight_diagnostics(
    project_name: str,
    file_name: str,
    new_content: str
) -> tuple[list[dict] | None, str]:

    project_path = find_project_path(
        project_name
    )

    if project_path is None:
        return (
            None,
            "Non riesco a trovare il progetto."
        )

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return (
            None,
            "Non riesco a trovare il file originale."
        )

    # Niente file nascosto con "." davanti.
    # Usiamo un nome temporaneo normale.
    temp_name = (
        f"_jarvis_preflight_"
        f"{file_path.stem}_"
        f"{uuid4().hex}.py"
    )

    temp_path = file_path.with_name(
        temp_name
    )

    try:
        print(
            f"[PREFLIGHT] Creo file temporaneo: "
            f"{temp_path.name}"
        )

        temp_path.write_text(
            new_content,
            encoding="utf-8"
        )

        # IMPORTANTISSIMO:
        # NON richiamiamo più get_file_diagnostics()
        # e NON ricerchiamo il file per nome.
        #
        # Abbiamo già il Path esatto.
        diagnostics, error = (
            _run_pyright_on_path(
                project_path,
                temp_path
            )
        )

        if diagnostics is None:
            return (
                None,
                error
            )

        print(
            f"[PREFLIGHT] Pyright completato: "
            f"{len(diagnostics)} diagnostiche."
        )

        return diagnostics, ""

    except OSError as error:
        return (
            None,
            str(error)
        )

    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()

                print(
                    "[PREFLIGHT] "
                    "File temporaneo eliminato."
                )

        except OSError as error:
            print(
                f"[PREFLIGHT CLEANUP ERROR]: "
                f"{error}"
            )