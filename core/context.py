import ctypes
from dataclasses import dataclass

import psutil


@dataclass
class ActiveWindowContext:
    title: str
    process_name: str
    pid: int
    application_name: str


APP_NAMES = {
    "blender.exe": "Blender",
    "code.exe": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "vivaldi.exe": "Vivaldi",
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

    # Se non conosciamo il programma,
    # togliamo semplicemente ".exe"
    if process_lower.endswith(".exe"):
        return process_name[:-4]

    return process_name


def get_active_window_context() -> ActiveWindowContext | None:
    user32 = ctypes.windll.user32

    # Finestra attualmente in primo piano
    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    # Titolo della finestra
    length = user32.GetWindowTextLengthW(hwnd)

    buffer = ctypes.create_unicode_buffer(length + 1)

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1
    )

    window_title = buffer.value.strip()

    # PID del programma proprietario della finestra
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

    return ActiveWindowContext(
        title=window_title,
        process_name=process_name,
        pid=process_id,
        application_name=application_name
    )