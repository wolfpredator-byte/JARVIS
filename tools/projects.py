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