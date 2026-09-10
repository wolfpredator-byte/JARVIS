import subprocess
from pathlib import Path

from tools.projects import find_project_path


def validate_patch(
    project_name: str,
    patch: str,
    expected_file: str | None = None
) -> tuple[bool, str]:

    project_path = find_project_path(
        project_name
    )

    if project_path is None:
        return False, "Progetto non trovato."

    if expected_file:
        expected_file = expected_file.replace(
            "\\",
            "/"
        )

        expected_old = f"--- a/{expected_file}"
        expected_new = f"+++ b/{expected_file}"

        if (
            expected_old not in patch
            or expected_new not in patch
        ):
            return (
                False,
                "La patch tenta di modificare "
                "un percorso diverso dal file atteso."
            )

    try:
        result = subprocess.run(
            [
                "git",
                "apply",
                "--check",
                "--whitespace=nowarn",
                "-"
            ],
            cwd=str(project_path),
            input=patch,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode == 0:
            return True, ""

        error = (
            result.stderr.strip()
            or result.stdout.strip()
        )

        return False, error

    except OSError as error:
        return False, str(error)


def apply_patch(
    project_name: str,
    patch: str
) -> tuple[bool, str]:

    project_path = find_project_path(
        project_name
    )

    if project_path is None:
        return False, "Progetto non trovato."

    try:
        result = subprocess.run(
            [
                "git",
                "apply",
                "--whitespace=nowarn",
                "-"
            ],
            cwd=str(project_path),
            input=patch,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace"
        )

        if result.returncode == 0:
            return True, ""

        error = (
            result.stderr.strip()
            or result.stdout.strip()
        )

        return False, error

    except OSError as error:
        return False, str(error)