import json
import subprocess
import sys

from tools.projects import (
    find_file_in_project,
    find_project_path,
)


def get_file_diagnostics(
    project_name: str,
    file_name: str
) -> list[dict]:

    project_path = find_project_path(project_name)

    if project_path is None:
        return []

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return []

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

        if not result.stdout.strip():
            return []

        data = json.loads(result.stdout)

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
                    # Pyright parte da zero
                    "line": start.get("line", 0) + 1,
                    "character": (
                        start.get("character", 0) + 1
                    )
                }
            )

        return diagnostics

    except (
        OSError,
        json.JSONDecodeError
    ) as error:

        print(
            f"[PYRIGHT ERROR]: {error}"
        )

        return []


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