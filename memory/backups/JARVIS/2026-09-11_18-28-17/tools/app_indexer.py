import json
import os
import sqlite3
import winreg
import re
import win32api

from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

import win32com.client


BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = BASE_DIR / "memory" / "jarvis.db"
SETTINGS_PATH = BASE_DIR / "config" / "settings.json"


IGNORED_EXECUTABLE_WORDS = {
    "uninstall",
    "unins",
    "setup",
    "installer",
    "update",
    "updater",
    "crash",
    "crashpad",
    "helper",
    "service",
    "repair",
}


def get_connection():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(DATABASE_PATH)

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            version TEXT,
            last_seen TEXT NOT NULL
        )
        """
    )

    # Migrazione automatica del vecchio database
    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(applications)"
        )
    }

    if "version" not in columns:
        connection.execute(
            "ALTER TABLE applications "
            "ADD COLUMN version TEXT"
        )

    connection.commit()

    return connection


def normalize_name(name: str) -> str:
    name = name.lower().strip()

    name = name.replace(".exe", "")
    name = name.replace("_", " ")
    name = name.replace("-", " ")

    return " ".join(name.split())

VERSION_PATTERN = re.compile(
    r"(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)"
)


def extract_version(text: str) -> str | None:
    match = VERSION_PATTERN.search(text)

    if match:
        return match.group(1)

    return None


def get_executable_version(
    executable: Path
) -> str | None:

    # Prima proviamo i metadata dell'EXE
    try:
        info = win32api.GetFileVersionInfo(
            str(executable),
            "\\"
        )

        ms = info["FileVersionMS"]
        ls = info["FileVersionLS"]

        parts = [
            win32api.HIWORD(ms),
            win32api.LOWORD(ms),
            win32api.HIWORD(ls),
            win32api.LOWORD(ls),
        ]

        # Toglie eventuali zeri finali inutili
        while len(parts) > 2 and parts[-1] == 0:
            parts.pop()

        return ".".join(
            str(part)
            for part in parts
        )

    except Exception:
        pass

    # Fallback: cerca la versione nel percorso
    #
    # C:\...\Blender 4.5\blender.exe
    #                  ^^^
    return extract_version(
        str(executable)
    )


def normalize_app_base(name: str) -> str:
    # "Blender 4.5" -> "blender"
    without_version = VERSION_PATTERN.sub(
        " ",
        name
    )

    return normalize_name(
        without_version
    )


def is_valid_executable(path: Path) -> bool:
    if not path.exists():
        return False

    if path.suffix.lower() != ".exe":
        return False

    name = path.stem.lower()

    for ignored in IGNORED_EXECUTABLE_WORDS:
        if ignored in name:
            return False

    return True


def save_application(
    name: str,
    path: str,
    source: str
):
    executable = Path(path)

    if not is_valid_executable(executable):
        return

    normalized = normalize_name(name)

    if not normalized:
        return

    version = get_executable_version(
        executable
    )

    timestamp = datetime.now().isoformat()

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO applications (
                name,
                normalized_name,
                path,
                source,
                version,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(path) DO UPDATE SET
                name = excluded.name,
                normalized_name = excluded.normalized_name,
                source = excluded.source,
                version = excluded.version,
                last_seen = excluded.last_seen
            """,
            (
                name,
                normalized,
                str(executable),
                source,
                version,
                timestamp
            )
        )

        connection.commit()

    finally:
        connection.close()

def scan_start_menu() -> int:
    start_menu_locations = [
        Path(
            os.environ.get(
                "PROGRAMDATA",
                "C:\\ProgramData"
            )
        )
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs",

        Path(
            os.environ.get(
                "APPDATA",
                ""
            )
        )
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs",
    ]

    shell = win32com.client.Dispatch(
        "WScript.Shell"
    )

    found = 0

    for start_menu in start_menu_locations:

        if not start_menu.exists():
            continue

        for shortcut_path in start_menu.rglob("*.lnk"):

            try:
                shortcut = shell.CreateShortcut(
                    str(shortcut_path)
                )

                target = shortcut.Targetpath

                if not target:
                    continue

                executable = Path(target)

                if not is_valid_executable(executable):
                    continue

                app_name = shortcut_path.stem

                save_application(
                    name=app_name,
                    path=str(executable),
                    source="start_menu"
                )

                found += 1

            except Exception as error:
                print(
                    f"[INDEXER WARNING] "
                    f"{shortcut_path.name}: {error}"
                )

    return found

def scan_registry_app_paths() -> int:
    registry_locations = [
        (
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        ),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        ),
    ]

    found = 0

    for root, registry_path in registry_locations:

        try:
            with winreg.OpenKey(
                root,
                registry_path
            ) as key:

                index = 0

                while True:
                    try:
                        subkey_name = winreg.EnumKey(
                            key,
                            index
                        )

                        index += 1

                    except OSError:
                        break

                    try:
                        with winreg.OpenKey(
                            key,
                            subkey_name
                        ) as subkey:

                            path, _ = winreg.QueryValueEx(
                                subkey,
                                ""
                            )

                            executable = Path(path)

                            if not is_valid_executable(
                                executable
                            ):
                                continue

                            name = executable.stem

                            save_application(
                                name=name,
                                path=str(executable),
                                source="registry"
                            )

                            found += 1

                    except OSError:
                        continue

        except OSError:
            continue

    return found

def load_scan_directories() -> list[Path]:
    if not SETTINGS_PATH.exists():
        return []

    try:
        with open(
            SETTINGS_PATH,
            "r",
            encoding="utf-8"
        ) as file:
            settings = json.load(file)

    except (
        OSError,
        json.JSONDecodeError
    ):
        return []

    directories = settings.get(
        "application_scan_directories",
        []
    )

    return [
        Path(directory)
        for directory in directories
    ]


def scan_directories() -> int:
    directories = load_scan_directories()

    found = 0

    for directory in directories:

        if not directory.exists():
            print(
                f"[INDEXER] Directory ignorata: "
                f"{directory}"
            )
            continue

        print(
            f"[INDEXER] Scansione: {directory}"
        )

        try:
            for executable in directory.rglob("*.exe"):

                if not is_valid_executable(executable):
                    continue

                save_application(
                    name=executable.stem,
                    path=str(executable),
                    source="directory_scan"
                )

                found += 1

        except (
            PermissionError,
            OSError
        ) as error:
            print(
                f"[INDEXER WARNING] "
                f"{directory}: {error}"
            )

    return found

def build_application_index() -> int:
    print("\n[INDEXER] Avvio indicizzazione...")

    start_menu_count = scan_start_menu()

    print(
        f"[INDEXER] Start Menu: "
        f"{start_menu_count}"
    )

    registry_count = scan_registry_app_paths()

    print(
        f"[INDEXER] Registry: "
        f"{registry_count}"
    )

    directory_count = scan_directories()

    print(
        f"[INDEXER] Directory: "
        f"{directory_count}"
    )

    total = (
        start_menu_count
        + registry_count
        + directory_count
    )

    print(
        f"[INDEXER] Indicizzazione completata. "
        f"{total} elementi analizzati."
    )

    return total

def _version_key(
    version: str | None
) -> tuple[int, int, int, int]:

    if not version:
        return (0, 0, 0, 0)

    numbers = [
        int(number)
        for number in re.findall(
            r"\d+",
            version
        )
    ]

    numbers = numbers[:4] + [0] * (4 - len(numbers))

    return tuple(numbers)


def find_application(
    requested_name: str
) -> dict | None:

    requested_version = extract_version(
        requested_name
    )

    requested_base = normalize_app_base(
        requested_name
    )

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            SELECT
                name,
                normalized_name,
                path,
                source,
                version
            FROM applications
            """
        )

        applications = cursor.fetchall()

    finally:
        connection.close()

    if not applications:
        return None

    candidates = []

    for (
        name,
        normalized_name,
        path,
        source,
        version
    ) in applications:

        candidate_base = normalize_app_base(
            name
        )

        # ---------------------------------
        # VERSIONE RICHIESTA ESPLICITAMENTE
        # ---------------------------------

        if requested_version:
            version_data = " ".join(
                [
                    name,
                    path,
                    version or ""
                ]
            ).lower()

            # Se chiedo Blender 4.0,
            # non accettiamo Blender 5.2
            if requested_version not in version_data:
                continue

        # ---------------------------------
        # MATCH DEL NOME
        # ---------------------------------

        if requested_base == candidate_base:
            score = 1.0

        elif (
            requested_base in candidate_base
            or candidate_base in requested_base
        ):
            score = 0.90

        else:
            score = SequenceMatcher(
                None,
                requested_base,
                candidate_base
            ).ratio()

        if score < 0.60:
            continue

        # Se i metadata non contengono la versione,
        # proviamo nome/percorso.
        detected_version = (
            version
            or extract_version(name)
            or extract_version(path)
        )

        source_priority = {
            "start_menu": 3,
            "registry": 2,
            "directory_scan": 1,
        }.get(
            source,
            0
        )

        candidates.append(
            {
                "name": name,
                "path": path,
                "source": source,
                "version": detected_version,
                "score": score,
                "source_priority": source_priority,
            }
        )

    if not candidates:
        return None

    # Prima miglior corrispondenza,
    # poi versione più recente,
    # poi fonte più affidabile.
    candidates.sort(
        key=lambda app: (
            app["score"],
            _version_key(
                app["version"]
            ),
            app["source_priority"],
        ),
        reverse=True
    )

    return candidates[0]