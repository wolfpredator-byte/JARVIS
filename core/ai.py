from ollama import chat
import json


MODEL_NAME = "qwen2.5-coder:7b-instruct"

# Evitiamo di passare file enormi al modello
MAX_CODE_CHARS = 30000


def analyze_code(
    code: str,
    file_name: str,
    project_name: str,
    request: str,
    diagnostics: str | None = None
) -> str:

    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS]

    system_prompt = """
Sei il modulo Coding Assistant di JARVIS.

Stai aiutando l'utente mentre lavora direttamente sul proprio PC.

Regole:
- Rispondi in italiano.
- Sii preciso e concreto.
- Analizza realmente il codice fornito.
- Non inventare file, funzioni o errori che non vedi.
- Se non hai abbastanza informazioni, dillo.
- Per le risposte vocali resta relativamente conciso.
- Se trovi un problema, indica funzione, classe o parte del codice coinvolta.
- La sezione DIAGNOSTICA REALE proviene dal type checker.
- Se contiene errori o warning, analizzali esplicitamente.
- Non ignorare la diagnostica fornita.
- Spiega la causa e proponi una correzione concreta.
"""

    diagnostics_section = (
         diagnostics
         if diagnostics
         else "Nessuna diagnostica disponibile."
    )

    user_prompt = f"""
    PROGETTO:
    {project_name}

    FILE:
    {file_name}

    RICHIESTA:
    {request}

    DIAGNOSTICA REALE:
    {diagnostics_section}

    CODICE:
    {code}
    """

    try:
        response = chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        content = response.message.content

        if not content:
            return "Il modello non ha restituito una risposta."

        return content.strip()

    except Exception as error:
        print(f"[AI ERROR]: {error}")

        return (
            "Non riesco a comunicare con il "
            "modello di intelligenza artificiale locale."
        )

def generate_code_edits(
    code: str,
    file_name: str,
    project_name: str,
    diagnostics: str
) -> list[dict[str, str]] | None:

    system_prompt = """
Sei il Coding Agent di JARVIS.

Devi proporre modifiche MINIME e precise al codice.

REGOLE:
- Restituisci ESCLUSIVAMENTE JSON valido.
- Non usare Markdown.
- Non usare blocchi ```json.
- Non restituire l'intero file.
- Non generare unified diff.
- Modifica soltanto il codice necessario.
- old_text deve essere copiato ESATTAMENTE dal codice originale.
- old_text deve contenere abbastanza contesto da comparire una sola volta.
- new_text deve contenere il testo che sostituirà old_text.
- Non modificare codice non collegato al problema.
- Se servono più modifiche, crea più elementi in edits.

Formato obbligatorio:

{
    "edits": [
        {
            "old_text": "testo esatto esistente",
            "new_text": "nuovo testo"
        }
    ]
}
"""

    user_prompt = f"""
PROGETTO:
{project_name}

FILE:
{file_name}

DIAGNOSTICA REALE:
{diagnostics}

CODICE:
{code}
"""

    try:
        response = chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            options={
                "temperature": 0
            }
        )

        content = response.message.content

        if not content:
            return None

        content = content.strip()

        # Protezione nel caso il modello aggiunga comunque Markdown
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

        data = json.loads(content)

        edits = data.get("edits")

        if not isinstance(edits, list):
            return None

        cleaned_edits = []

        for edit in edits:
            if not isinstance(edit, dict):
                continue

            old_text = edit.get("old_text")
            new_text = edit.get("new_text")

            if not isinstance(old_text, str):
                continue

            if not isinstance(new_text, str):
                continue

            if not old_text:
                continue

            if old_text == new_text:
                continue

            cleaned_edits.append(
                {
                    "old_text": old_text,
                    "new_text": new_text
                }
            )

        if not cleaned_edits:
            return None

        return cleaned_edits

    except json.JSONDecodeError as error:
        print(
            f"[AI EDIT JSON ERROR]: {error}"
        )
        return None

    except Exception as error:
        print(
            f"[AI EDIT ERROR]: {error}"
        )
        return None    