import difflib
import os
import shutil

from datetime import datetime
from pathlib import Path

from tools.projects import (
    find_file_in_project,
    find_project_path
)


BASE_DIR = Path(__file__).resolve().parent.parent


def prepare_edits(
    original_content: str,
    edits: list[dict[str, str]],
    relative_file_path: str
) -> tuple[
    bool,
    str,
    str | None,
    str | None
]:

    if not edits:
        return (
            False,
            "Nessuna modifica ricevuta.",
            None,
            None
        )

    # Protezione da modifiche gigantesche
    if len(edits) > 10:
        return (
            False,
            "L'IA ha proposto troppe modifiche contemporaneamente.",
            None,
            None
        )

    working_content = original_content

    for index, edit in enumerate(
        edits,
        start=1
    ):
        old_text = edit["old_text"]
        new_text = edit["new_text"]

        occurrences = working_content.count(
            old_text
        )

        if occurrences == 0:
            return (
                False,
                (
                    f"Modifica {index}: il codice originale "
                    "indicato dall'IA non esiste nel file."
                ),
                None,
                None
            )

        if occurrences > 1:
            return (
                False,
                (
                    f"Modifica {index}: il codice indicato "
                    f"compare {occurrences} volte. "
                    "La modifica è ambigua."
                ),
                None,
                None
            )

        # Sostituzione ESATTAMENTE una volta
        working_content = working_content.replace(
            old_text,
            new_text,
            1
        )

    if working_content == original_content:
        return (
            False,
            "La modifica non cambia realmente il file.",
            None,
            None
        )

    diff = "".join(
        difflib.unified_diff(
            original_content.splitlines(
                keepends=True
            ),
            working_content.splitlines(
                keepends=True
            ),
            fromfile=f"a/{relative_file_path}",
            tofile=f"b/{relative_file_path}"
        )
    )

    return (
        True,
        "",
        working_content,
        diff
    )


def create_backup(
    project_name: str,
    file_name: str
) -> Path | None:

    project_path = find_project_path(
        project_name
    )

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if (
        project_path is None
        or file_path is None
    ):
        return None

    try:
        relative_path = file_path.relative_to(
            project_path
        )

        timestamp = datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )

        backup_path = (
            BASE_DIR
            / "memory"
            / "backups"
            / project_name
            / timestamp
            / relative_path
        )

        backup_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            file_path,
            backup_path
        )

        print(
            f"[BACKUP]: {backup_path}"
        )

        return backup_path

    except OSError as error:
        print(
            f"[BACKUP ERROR]: {error}"
        )

        return None


def apply_content_if_unchanged(
    project_name: str,
    file_name: str,
    expected_original: str,
    new_content: str
) -> tuple[bool, str]:

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    if file_path is None:
        return (
            False,
            "File non trovato."
        )

    try:
        current_content = file_path.read_text(
            encoding="utf-8"
        )

        # Importantissimo:
        # se hai modificato manualmente il file
        # dopo la preview, Jarvis NON sovrascrive.
        if current_content != expected_original:
            return (
                False,
                (
                    "Il file è cambiato dopo la generazione "
                    "della correzione."
                )
            )

        temporary_path = file_path.with_name(
            file_path.name + ".jarvis_tmp"
        )

        temporary_path.write_text(
            new_content,
            encoding="utf-8"
        )

        # Sostituzione atomica
        os.replace(
            temporary_path,
            file_path
        )

        return True, ""

    except OSError as error:
        return False, str(error)


def restore_content(
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
        temporary_path = file_path.with_name(
            file_path.name + ".jarvis_restore"
        )

        temporary_path.write_text(
            original_content,
            encoding="utf-8"
        )

        os.replace(
            temporary_path,
            file_path
        )

        return True

    except OSError as error:
        print(
            f"[ROLLBACK ERROR]: {error}"
        )

        return False