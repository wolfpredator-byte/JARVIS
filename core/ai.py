from ollama import chat


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

def generate_code_fix(
    code: str,
    file_name: str,
    project_name: str,
    diagnostics: str
) -> str:

    system_prompt = """
Sei il Coding Agent di JARVIS.

Devi correggere il file fornito.

Regole:
- Correggi gli errori indicati nella diagnostica.
- Mantieni invariato tutto il codice non necessario alla correzione.
- Non aggiungere spiegazioni.
- Non usare blocchi Markdown.
- Restituisci ESCLUSIVAMENTE il contenuto completo del file corretto.
"""

    user_prompt = f"""
PROGETTO:
{project_name}

FILE:
{file_name}

DIAGNOSTICA:
{diagnostics}

CODICE ATTUALE:
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
            return ""

        return content.strip()

    except Exception as error:
        print(f"[AI FIX ERROR]: {error}")
        return ""   