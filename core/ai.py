from ollama import chat
import json


MODEL_NAME = "qwen2.5-coder:7b-instruct"


CODING_MODEL_PLAN = [
    {
        "model": "qwen2.5-coder:7b-instruct",
        "attempts": 3,
    },
    {
        "model": "qwen2.5-coder:14b",
        "attempts": 3,
    },
    {
        "model": "qwen3.8:27b-q4_k_m",
        "attempts": 1,
    },
    {
        "model": "qwen3.8:27b",
        "attempts": 1,
    },
    {
        "model": "qwen3.6:35b",
        "attempts": 1,
    },
]

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
    diagnostics: str,
    previous_failed_edits: list[dict[str, str]] | None = None,
    failed_diagnostics: str | None = None,
    model_name: str = MODEL_NAME,
    attempt_number: int = 1,
    attempt_feedback: str | None = None
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
- Se viene fornito un tentativo precedente fallito, analizzalo.
- Non riproporre la stessa modifica.
- La nuova soluzione deve essere materialmente differente.
- Usa la diagnostica del tentativo fallito per capire cosa è andato storto.
- La diagnostica fornita da Pyright è la fonte principale da seguire.
- Prima di creare la modifica, identifica quale espressione produce
  realmente il tipo o il valore sbagliato.
- Non modificare una firma, un tipo di ritorno o un contratto pubblico
  soltanto per far sparire l'errore del type checker.
- Una modifica deve affrontare la CAUSA della diagnostica.
- Verifica mentalmente che la modifica non contraddica il messaggio
  di errore.
- Se i tentativi precedenti sono falliti, NON ripetere quelle modifiche.
- Cerca una strategia materialmente differente.
- old_text deve esistere esattamente nel codice ricevuto.
- new_text deve essere realmente diverso da old_text.

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

    failed_attempt_section = ""

    if previous_failed_edits:
        failed_attempt_section = f"""
TENTATIVO PRECEDENTE FALLITO:

MODIFICHE TENTATE:
{json.dumps(
    previous_failed_edits,
    ensure_ascii=False,
    indent=2
)}

DIAGNOSTICA DOPO IL TENTATIVO:
{failed_diagnostics or "Non disponibile"}

IMPORTANTE:
La modifica precedente è stata annullata automaticamente.
NON ripetere la stessa soluzione.
Analizza perché ha peggiorato la diagnostica e proponi
una soluzione differente.
"""

    automatic_retry_section = ""

    if attempt_feedback:
        automatic_retry_section = f"""
RISULTATI DEI TENTATIVI AUTOMATICI PRECEDENTI:

{attempt_feedback}

Questi tentativi sono già stati verificati realmente con Pyright
e NON hanno risolto il problema.

Non ripetere quelle strategie.
Proponi una modifica diversa.
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

TENTATIVO AUTOMATICO:
{attempt_number}
{automatic_retry_section}
{failed_attempt_section}

"""

    try:
        response = chat(
            model=model_name,
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
                "temperature": 0.1
            }
        )

        content = response.message.content

        if not content:
            return None

        print(
            f"\n[AI RAW EDIT RESPONSE - {model_name}]\n"
            + content
        )

        content = content.strip()

        # Protezione nel caso il modello aggiunga comunque Markdown
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

        data = json.loads(content)

        edits = data.get("edits")

        if not isinstance(edits, list):
            print(
                "[AI EDIT ERROR] "
                "La risposta non contiene una lista 'edits' valida."
            )
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
            print(
                "[AI EDIT ERROR] "
                "Il modello non ha prodotto nessun edit utilizzabile."
            )
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

def analyze_failed_fix(
    code: str,
    file_name: str,
    project_name: str,
    diagnostics: str,
    failed_edits: list[dict[str, str]] | None,
    failed_diagnostics: str | None
) -> str:

    system_prompt = """
Sei il Coding Agent di JARVIS.

Diversi tentativi automatici di correzione sono falliti.

NON devi generare una nuova modifica.

Devi invece:
- analizzare il problema originale;
- analizzare il tentativo fallito;
- spiegare perché la soluzione precedente non ha funzionato;
- identificare quali informazioni mancano;
- indicare se il problema potrebbe dipendere da altro codice,
  typing, import, configurazione o librerie esterne;
- proporre il prossimo passo diagnostico.
- NON cambiare il tipo di ritorno dichiarato soltanto per eliminare
  un errore del type checker.
- Considera la signature della funzione come un contratto da
  preservare, salvo prova evidente che sia sbagliata.
- Se la funzione dichiara tuple[int, int, int, int],
  il valore restituito deve avere ESATTAMENTE quattro elementi.
- Prima di proporre una modifica, verifica mentalmente che essa
  non contraddica direttamente la diagnostica fornita.
- Non aggiungere o rimuovere elementi arbitrariamente da tuple,
  liste o argomenti solo per tentare di soddisfare il type checker.
- Preferisci correggere l'espressione che causa l'incompatibilità
  invece di allargare il tipo dichiarato.

Rispondi in italiano.
Sii concreto.
"""

    user_prompt = f"""
PROGETTO:
{project_name}

FILE:
{file_name}

DIAGNOSTICA ATTUALE:
{diagnostics}

TENTATIVI FALLITI:
{failed_edits}

DIAGNOSTICA DOPO IL TENTATIVO:
{failed_diagnostics}

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
            return (
                "Non sono riuscito a capire perché "
                "le correzioni stanno fallendo."
            )

        return content.strip()

    except Exception as error:
        print(f"[AI FAILURE ANALYSIS ERROR]: {error}")

        return (
            "Non sono riuscito ad analizzare "
            "il fallimento della correzione."
        )    