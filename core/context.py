import ctypes
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class ActiveWindowContext:
    title: str
    process_name: str
    pid: int
    application_name: str

    current_file: str | None = None
    project_name: str | None = None
    context_type: str | None = None


APP_NAMES = {
    "blender.exe": "Blender",
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "notepad.exe": "Blocco note",
    "calculatorapp.exe": "Calcolatrice",
    "explorer.exe": "Esplora file",
}


def _get_friendly_app_name(process_name: str) -> str:
    process_lower = process_name.lower()

    if process_lower in APP_NAMES:
        return APP_NAMES[process_lower]

    if process_lower.endswith(".exe"):
        return process_name[:-4]

    return process_name


def _analyze_window(
    application_name: str,
    title: str
) -> tuple[str | None, str | None, str | None]:

    current_file = None
    project_name = None
    context_type = None

    # -------------------------
    # VISUAL STUDIO CODE
    # -------------------------

    if application_name == "Visual Studio Code":
        parts = [
            part.strip()
            for part in title.split(" - ")
        ]

        if parts:
            possible_file = parts[0]

            # Es. router.py, main.py, index.html...
            if "." in possible_file:
                current_file = possible_file

        if len(parts) >= 3:
            project_name = parts[-2]

        context_type = "Coding"

    # -------------------------
    # BLENDER
    # -------------------------

    elif application_name == "Blender":
        parts = [
            part.strip()
            for part in title.split(" - ")
        ]

        for part in parts:
            if part.lower().endswith(".blend"):
                current_file = part
                project_name = Path(part).stem
                break

        context_type = "3D"

    return (
        current_file,
        project_name,
        context_type
    )


def get_active_window_context() -> ActiveWindowContext | None:
    user32 = ctypes.windll.user32

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(hwnd)

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1
    )

    window_title = buffer.value.strip()

    pid = ctypes.c_ulong()

    user32.GetWindowThreadProcessId(
        hwnd,
        ctypes.byref(pid)
    )

    process_id = pid.value

    try:
        process = psutil.Process(process_id)
        process_name = process.name()

    except (
        psutil.NoSuchProcess,
        psutil.AccessDenied
    ):
        process_name = "Sconosciuto"

    application_name = _get_friendly_app_name(
        process_name
    )

    current_file, project_name, context_type = (
        _analyze_window(
            application_name,
            window_title
        )
    )

    return ActiveWindowContext(
        title=window_title,
        process_name=process_name,
        pid=process_id,
        application_name=application_name,
        current_file=current_file,
        project_name=project_name,
        context_type=context_type
    )