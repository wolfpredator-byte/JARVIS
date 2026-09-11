import json

from dataclasses import dataclass

from core.ai import (
    CODING_MODEL_PLAN,
    generate_code_edits
)

from tools.code_edit import prepare_edits

from tools.diagnostics import (
    get_preflight_diagnostics,
    diagnostics_score,
    format_diagnostics
)

from tools.projects import (
    find_file_in_project,
    find_project_path
)


@dataclass
class FixSearchResult:
    success: bool

    edits: list[dict[str, str]] | None = None
    new_content: str | None = None
    diff: str | None = None

    model_name: str | None = None
    attempt_number: int | None = None

    before_score: int = 0
    after_score: int | None = None

    diagnostics_text: str | None = None

    last_failed_edits: list[dict[str, str]] | None = None
    last_failed_diagnostics: str | None = None

    report: str = ""


def _build_failure_feedback(
    model_name: str,
    attempt_number: int,
    edits: list[dict[str, str]] | None,
    diagnostics_text: str,
    score: int
) -> str:

    edits_text = (
        json.dumps(
            edits,
            ensure_ascii=False,
            indent=2
        )
        if edits
        else "Nessun edit valido."
    )

    # Evitiamo di gonfiare troppo il prompt.
    diagnostics_text = diagnostics_text[:3000]

    return (
        f"MODELLO: {model_name}\n"
        f"TENTATIVO: {attempt_number}\n"
        f"SCORE PYRIGHT: {score}\n"
        f"EDIT:\n{edits_text}\n"
        f"DIAGNOSTICA:\n{diagnostics_text}"
    )


def find_verified_fix(
    project_name: str,
    file_name: str,
    code: str,
    before_diagnostics: list[dict],
    diagnostics_text: str,
    analysis_context: str | None = None,
    previous_failed_edits: list[dict[str, str]] | None = None,
    previous_failed_diagnostics: str | None = None
) -> FixSearchResult:

    before_score = diagnostics_score(
        before_diagnostics
    )

    file_path = find_file_in_project(
        project_name,
        file_name
    )

    project_path = find_project_path(
        project_name
    )

    if (
        file_path is None
        or project_path is None
    ):
        return FixSearchResult(
            success=False,
            before_score=before_score,
            report=(
                "Non riesco a determinare "
                "il percorso del file."
            )
        )

    relative_file_path = (
        file_path
        .relative_to(project_path)
        .as_posix()
    )

    failure_history: list[str] = []

    last_failed_edits = (
        previous_failed_edits
    )

    last_failed_diagnostics = (
        previous_failed_diagnostics
    )

    # Se arriviamo da un precedente "riprova",
    # inseriamo anche quel fallimento nel contesto.
    if (
        previous_failed_edits
        or previous_failed_diagnostics
    ):
        failure_history.append(
            "TENTATIVO PRECEDENTE ALLA SESSIONE ATTUALE:\n"
            f"EDIT:\n{previous_failed_edits}\n"
            f"DIAGNOSTICA:\n"
            f"{previous_failed_diagnostics}"
        )

    for model_info in CODING_MODEL_PLAN:

        model_name = model_info["model"]
        max_attempts = model_info["attempts"]

        print(
            "\n"
            + "=" * 60
            + f"\nCODING MODEL: {model_name}\n"
            + "=" * 60
        )

        for attempt_number in range(
            1,
            max_attempts + 1
        ):

            print(
                f"\n[AUTO RETRY] "
                f"{model_name} "
                f"- candidato "
                f"{attempt_number}/{max_attempts}"
            )

            # Passiamo soltanto gli ultimi fallimenti
            # per evitare prompt enormi.
            attempt_feedback = "\n\n---\n\n".join(
                failure_history[-3:]
            )

            edits = generate_code_edits(
                code=code,
                file_name=file_name,
                project_name=project_name,
                diagnostics=diagnostics_text,
                previous_failed_edits=(
                    last_failed_edits
                ),
                failed_diagnostics=(
                    last_failed_diagnostics
                ),
                model_name=model_name,
                attempt_number=attempt_number,
                attempt_feedback=(
                    attempt_feedback
                    if attempt_feedback
                    else None
                )
            )

            if not edits:
                message = (
                    f"{model_name}, tentativo "
                    f"{attempt_number}: "
                    "nessun edit valido."
                )

                print(
                    f"[AUTO RETRY] {message}"
                )

                failure_history.append(
                    message
                )

                continue

            (
                valid,
                error,
                new_content,
                diff
            ) = prepare_edits(
                original_content=code,
                edits=edits,
                relative_file_path=(
                    relative_file_path
                )
            )

            if (
                not valid
                or new_content is None
                or diff is None
            ):
                message = (
                    f"{model_name}, tentativo "
                    f"{attempt_number}: "
                    f"structured edit rifiutata. "
                    f"{error}"
                )

                print(
                    f"[AUTO RETRY] {message}"
                )

                failure_history.append(
                    message
                )

                last_failed_edits = edits

                continue

            (
                preflight_diagnostics,
                preflight_error
            ) = get_preflight_diagnostics(
                project_name=project_name,
                file_name=file_name,
                new_content=new_content
            )

            if preflight_diagnostics is None:
                message = (
                    f"{model_name}, tentativo "
                    f"{attempt_number}: "
                    "preflight non riuscito. "
                    f"{preflight_error}"
                )

                print(
                    f"[AUTO RETRY] {message}"
                )

                failure_history.append(
                    message
                )

                last_failed_edits = edits

                continue

            candidate_score = (
                diagnostics_score(
                    preflight_diagnostics
                )
            )

            candidate_diagnostics_text = (
                format_diagnostics(
                    preflight_diagnostics
                )
            )

            print(
                "\n[AUTO PREFLIGHT]"
            )

            print(
                f"Modello: {model_name}"
            )

            print(
                f"Candidato: {attempt_number}"
            )

            print(
                f"Score originale: {before_score}"
            )

            print(
                f"Score candidato: {candidate_score}"
            )

            print(
                candidate_diagnostics_text
            )

            # ----------------------------
            # SUCCESSO
            # ----------------------------

            if candidate_score < before_score:

                print(
                    "\n"
                    "[AUTO RETRY] ✅ "
                    "Candidato verificato."
                )

                return FixSearchResult(
                    success=True,
                    edits=edits,
                    new_content=new_content,
                    diff=diff,
                    model_name=model_name,
                    attempt_number=(
                        attempt_number
                    ),
                    before_score=before_score,
                    after_score=candidate_score,
                    diagnostics_text=(
                        candidate_diagnostics_text
                    ),
                    report=(
                        f"Correzione verificata con "
                        f"{model_name}. "
                        f"Score Pyright: "
                        f"{before_score} → "
                        f"{candidate_score}."
                    )
                )

            # ----------------------------
            # FALLIMENTO
            # ----------------------------

            last_failed_edits = edits
            last_failed_diagnostics = (
                candidate_diagnostics_text
            )

            failure_history.append(
                _build_failure_feedback(
                    model_name=model_name,
                    attempt_number=(
                        attempt_number
                    ),
                    edits=edits,
                    diagnostics_text=(
                        candidate_diagnostics_text
                    ),
                    score=candidate_score
                )
            )

            if candidate_score > before_score:
                print(
                    "[AUTO RETRY] ❌ "
                    "Il candidato peggiora "
                    "la diagnostica."
                )

            else:
                print(
                    "[AUTO RETRY] ❌ "
                    "Il candidato non migliora "
                    "la diagnostica."
                )

        # Solo se TUTTI i candidati di questo
        # modello falliscono arriviamo qui.

        print(
            f"\n[MODEL ESCALATION] "
            f"{model_name} non ha trovato "
            "una correzione verificata."
        )

    # ---------------------------------
    # NESSUN MODELLO HA RISOLTO
    # ---------------------------------

    report = (
        "Ho provato tutti i modelli disponibili "
        "e nessun candidato ha migliorato "
        "la diagnostica in modo verificabile."
    )

    print(
        "\n"
        + "=" * 60
        + "\nCODING AGENT - NESSUN FIX VERIFICATO\n"
        + "=" * 60
        + "\n"
        + report
        + "\n"
        + "=" * 60
    )

    return FixSearchResult(
        success=False,
        before_score=before_score,
        last_failed_edits=(
            last_failed_edits
        ),
        last_failed_diagnostics=(
            last_failed_diagnostics
        ),
        report=report
    )