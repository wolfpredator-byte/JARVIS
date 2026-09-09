import subprocess
import shutil
from pathlib import Path


APP_PATHS = {
    "blender": r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    "vscode": r"C:\Users\TUO_NOME\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\TUO_NOME\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "discord": r"C:\Users\TUO_NOME\AppData\Local\Discord\Update.exe",
}


def open_application(app_name: str) -> bool:
    app_name = app_name.strip().lower()

    # 1. Controlla il nostro registro personale
    if app_name in APP_PATHS:
        app_path = Path(APP_PATHS[app_name])

        if app_path.exists():
            subprocess.Popen([str(app_path)])
            return True

        print(f"Percorso non trovato: {app_path}")
        return False

    # 2. Cerca l'eseguibile nel PATH di Windows
    app_path = shutil.which(app_name)

    if app_path:
        subprocess.Popen([app_path])
        return True

    # 3. Ultimo tentativo tramite Windows
    try:
        subprocess.Popen(app_name, shell=True)
        return True

    except Exception as error:
        print(f"Errore durante l'apertura di {app_name}: {error}")
        return False