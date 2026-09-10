import json
import os
from pathlib import Path


SETTINGS_PATH = Path("config/settings.json")


def load_projects() -> dict[str, str]:
    if not SETTINGS_PATH.exists():
        return {}

    try:
        with open(
            SETTINGS_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            settings = json.load(file)

        return settings.get("projects", {})

    except (
        json.JSONDecodeError,
        OSError
    ) as error:
        print(
            f"[PROJECT ERROR] "
            f"Impossibile leggere settings.json: {error}"
        )

        return {}


def find_project_path(
    project_name: str
) -> Path | None:

    projects = load_projects()

    requested_name = (
        project_name
        .strip()
        .lower()
        .replace("_", " ")
    )

    for name, path in projects.items():

        normalized_name = (
            name
            .strip()
            .lower()
            .replace("_", " ")
        )

        if normalized_name == requested_name:
            project_path = Path(path)

            if project_path.exists():
                return project_path

    return None


def open_project_folder(
    project_name: str
) -> bool:

    path = find_project_path(project_name)

    if path is None:
        return False

    os.startfile(path)

    return True


def list_project_files(
    project_name: str,
    limit: int = 20
) -> list[str]:

    path = find_project_path(project_name)

    if path is None:
        return []

    files = []

    ignored_folders = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
    }

    for item in path.rglob("*"):

        if any(
            ignored in item.parts
            for ignored in ignored_folders
        ):
            continue

        if item.is_file():

            try:
                relative_path = item.relative_to(path)
                files.append(str(relative_path))

            except ValueError:
                continue

        if len(files) >= limit:
            break

    return files

def find_file_in_project(
    project_name: str,
    file_name: str
) -> Path | None:

    project_path = find_project_path(project_name)

    if project_path is None:
        return None

    ignored_folders = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
    }

    matches = []

    for item in project_path.rglob(file_name):

        if any(
            ignored in item.parts
            for ignored in ignored_folders
        ):
            continue

        if item.is_file():
            matches.append(item)

    if not matches:
        return None

    # Per ora, se ce n'è uno solo,
    # sappiamo esattamente quale usare
    if len(matches) == 1:
        return matches[0]

    # Se esistono più file con lo stesso nome,
    # evitiamo di scegliere a caso
    print(
        f"[PROJECT WARNING] "
        f"Trovati più file chiamati {file_name}:"
    )

    for match in matches:
        print(f" - {match}")

    return None


def read_project_file(
    project_name: str,
    file_name: str
) -> str | None:

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return None

    try:
        return file_path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:
        print(
            f"[PROJECT ERROR] "
            f"{file_path.name} non sembra essere "
            f"un file di testo."
        )
        return None

    except OSError as error:
        print(
            f"[PROJECT ERROR] "
            f"Impossibile leggere il file: {error}"
        )
        return None

def write_project_file(
    project_name: str,
    file_name: str,
    content: str
) -> bool:

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return False

    try:
        file_path.write_text(
            content,
            encoding="utf-8"
        )

        return True

    except OSError as error:
        print(
            f"[WRITE ERROR]: {error}"
        )

        return False

def restore_project_file(
    project_name: str,
    file_name: str,
    original_content: str
) -> bool:

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return False

    try:
        file_path.write_text(
            original_content,
            encoding="utf-8"
        )

        return True

    except OSError as error:
        print(
            f"[RESTORE ERROR]: {error}"
        )

        return False    