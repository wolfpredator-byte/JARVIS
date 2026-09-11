import json
import time

from dataclasses import dataclass

from core.ai import (
    CODING_MODEL_PLAN,
    generate_code_edits
)

from core.code_focus import (
    build_focused_code
)

from tools.code_edit import (
    prepare_edits
)

from tools.diagnostics import (
    get_preflight_diagnostics,
    diagnostics_score,
    format_diagnostics
)

from tools.projects import (
    find_file_in_project,
    find_project_path
)


MAX_STAGNANT_ATTEMPTS = 2


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

    last_failed_edits: (
        list[dict[str, str]] | None
    ) = None

    last_failed_diagnostics: (
        str | None
    ) = None

    report: str = ""


def _normalize_text(
    text: str
) -> str:

    return " ".join(
        text.split()
    )


def _edit_signature(
    edits: list[dict[str, str]]
) -> str:

    normalized = []

    for edit in edits:

        old_text = _normalize_text(
            edit.get(
                "old_text",
                ""
            )
        )

        new_text = _normalize_text(
            edit.get(
                "new_text",
                ""
            )
        )

        normalized.append(
            {
                "old_text": old_text,
                "new_text": new_text,
            }
        )

    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True
    )


def _build_failure_feedback(
    model_name: str,
    attempt_number: int,
    edits: (
        list[dict[str, str]]
        | None
    ),
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

    diagnostics_text = (
        diagnostics_text[:2500]
    )

    return (
        f"MODELLO: {model_name}\n"
        f"TENTATIVO: {attempt_number}\n"
        f"SCORE PYRIGHT: {score}\n"
        f"EDIT:\n{edits_text}\n"
        f"DIAGNOSTICA:\n"
        f"{diagnostics_text}"
    )


def find_verified_fix(
    project_name: str,
    file_name: str,
    code: str,
    before_diagnostics: list[dict],
    diagnostics_text: str,
    analysis_context: str | None = None,
    previous_failed_edits: (
        list[dict[str, str]]
        | None
    ) = None,
    previous_failed_diagnostics: (
        str | None
    ) = None
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

    # ==================================
    # CONTEXT FOCUS
    # ==================================

    focused_code = build_focused_code(
        code=code,
        diagnostics=before_diagnostics
    )

    full_line_count = len(
        code.splitlines()
    )

    focused_line_count = len(
        focused_code.splitlines()
    )

    print(
        "\n"
        + "=" * 60
        + "\nCONTEXT FOCUS\n"
        + "=" * 60
    )

    print(
        f"File completo: "
        f"{full_line_count} righe"
    )

    print(
        f"Contesto inviato al modello: "
        f"{focused_line_count} righe"
    )

    if full_line_count > 0:

        reduction = (
            1
            - (
                focused_line_count
                / full_line_count
            )
        ) * 100

        print(
            f"Riduzione contesto: "
            f"{reduction:.1f}%"
        )

    print(
        "=" * 60
    )

    # ==================================
    # STORIA FALLIMENTI
    # ==================================

    failure_history: list[str] = []

    last_failed_edits = (
        previous_failed_edits
    )

    last_failed_diagnostics = (
        previous_failed_diagnostics
    )

    if (
        previous_failed_edits
        or previous_failed_diagnostics
    ):
        failure_history.append(
            (
                "TENTATIVO PRECEDENTE:\n"
                f"EDIT:\n"
                f"{previous_failed_edits}\n"
                f"DIAGNOSTICA:\n"
                f"{previous_failed_diagnostics}"
            )
        )

    # ==================================
    # MODEL ESCALATION
    # ==================================

    for model_info in CODING_MODEL_PLAN:

        model_name = (
            model_info["model"]
        )

        max_attempts = (
            model_info["attempts"]
        )

        print(
            "\n"
            + "=" * 60
            + f"\nCODING MODEL: "
            + f"{model_name}\n"
            + "=" * 60
        )

        seen_signatures: set[str] = set()

        stagnant_attempts = 0
        last_candidate_score = None

        for attempt_number in range(
            1,
            max_attempts + 1
        ):

            print(
                f"\n[AUTO RETRY] "
                f"{model_name} "
                f"- candidato "
                f"{attempt_number}/"
                f"{max_attempts}"
            )

            attempt_feedback = (
                "\n\n---\n\n".join(
                    failure_history[-3:]
                )
            )

            start_time = (
                time.perf_counter()
            )

            edits = generate_code_edits(
                # IMPORTANTISSIMO:
                # passiamo il contesto ridotto,
                # non l'intero file.
                code=focused_code,
                file_name=file_name,
                project_name=project_name,
                diagnostics=(
                    diagnostics_text
                ),
                previous_failed_edits=(
                    last_failed_edits
                ),
                failed_diagnostics=(
                    last_failed_diagnostics
                ),
                model_name=model_name,
                attempt_number=(
                    attempt_number
                ),
                attempt_feedback=(
                    attempt_feedback
                    if attempt_feedback
                    else None
                )
            )

            elapsed = (
                time.perf_counter()
                - start_time
            )

            print(
                f"[MODEL TIME] "
                f"{model_name}: "
                f"{elapsed:.1f} secondi"
            )

            # ==================================
            # NESSUN EDIT
            # ==================================

            if not edits:

                stagnant_attempts += 1

                message = (
                    f"{model_name}, "
                    f"tentativo "
                    f"{attempt_number}: "
                    "nessun edit valido."
                )

                print(
                    f"[AUTO RETRY] "
                    f"{message}"
                )

                failure_history.append(
                    message
                )

                if (
                    stagnant_attempts
                    >= MAX_STAGNANT_ATTEMPTS
                ):

                    print(
                        "\n[EARLY ESCALATION] "
                        "Troppi tentativi "
                        "senza una nuova soluzione."
                    )

                    break

                continue

            # ==================================
            # DUPLICATE DETECTION
            # ==================================

            signature = _edit_signature(
                edits
            )

            if signature in seen_signatures:

                print(
                    "\n[EARLY ESCALATION] "
                    "Il modello sta ripetendo "
                    "la stessa modifica."
                )

                failure_history.append(
                    (
                        f"{model_name}: "
                        "strategia duplicata."
                    )
                )

                break

            seen_signatures.add(
                signature
            )

            # ==================================
            # STRUCTURED EDIT
            # ==================================

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

                stagnant_attempts += 1

                message = (
                    f"{model_name}, "
                    f"tentativo "
                    f"{attempt_number}: "
                    "structured edit "
                    f"rifiutata. {error}"
                )

                print(
                    f"[AUTO RETRY] "
                    f"{message}"
                )

                failure_history.append(
                    message
                )

                last_failed_edits = edits

                if (
                    stagnant_attempts
                    >= MAX_STAGNANT_ATTEMPTS
                ):
                    print(
                        "\n[EARLY ESCALATION] "
                        "Le modifiche proposte "
                        "non sono applicabili."
                    )

                    break

                continue

            # ==================================
            # PREFLIGHT
            # ==================================

            (
                preflight_diagnostics,
                preflight_error
            ) = get_preflight_diagnostics(
                project_name=project_name,
                file_name=file_name,
                new_content=new_content
            )

            if (
                preflight_diagnostics
                is None
            ):

                stagnant_attempts += 1

                message = (
                    f"{model_name}, "
                    f"tentativo "
                    f"{attempt_number}: "
                    "preflight non riuscito. "
                    f"{preflight_error}"
                )

                print(
                    f"[AUTO RETRY] "
                    f"{message}"
                )

                failure_history.append(
                    message
                )

                last_failed_edits = edits

                if (
                    stagnant_attempts
                    >= MAX_STAGNANT_ATTEMPTS
                ):
                    print(
                        "\n[EARLY ESCALATION] "
                        "Troppi preflight "
                        "non riusciti."
                    )

                    break

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
                f"Modello: "
                f"{model_name}"
            )

            print(
                f"Candidato: "
                f"{attempt_number}"
            )

            print(
                f"Score originale: "
                f"{before_score}"
            )

            print(
                f"Score candidato: "
                f"{candidate_score}"
            )

            print(
                candidate_diagnostics_text
            )

            # ==================================
            # SUCCESSO
            # ==================================

            if candidate_score < before_score:

                print(
                    "\n"
                    "[AUTO RETRY] ✅ "
                    "Candidato verificato."
                )

                return FixSearchResult(
                    success=True,
                    edits=edits,
                    new_content=(
                        new_content
                    ),
                    diff=diff,
                    model_name=(
                        model_name
                    ),
                    attempt_number=(
                        attempt_number
                    ),
                    before_score=(
                        before_score
                    ),
                    after_score=(
                        candidate_score
                    ),
                    diagnostics_text=(
                        candidate_diagnostics_text
                    ),
                    report=(
                        "Correzione verificata "
                        f"con {model_name}. "
                        "Score Pyright: "
                        f"{before_score} "
                        "→ "
                        f"{candidate_score}."
                    )
                )

            # ==================================
            # FALLIMENTO
            # ==================================

            last_failed_edits = edits

            last_failed_diagnostics = (
                candidate_diagnostics_text
            )

            failure_history.append(
                _build_failure_feedback(
                    model_name=(
                        model_name
                    ),
                    attempt_number=(
                        attempt_number
                    ),
                    edits=edits,
                    diagnostics_text=(
                        candidate_diagnostics_text
                    ),
                    score=(
                        candidate_score
                    )
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

            # ==================================
            # STAGNATION DETECTION
            # ==================================

            if (
                last_candidate_score
                == candidate_score
            ):
                stagnant_attempts += 1

            else:
                stagnant_attempts = 1

            last_candidate_score = (
                candidate_score
            )

            if (
                stagnant_attempts
                >= MAX_STAGNANT_ATTEMPTS
            ):

                print(
                    "\n[EARLY ESCALATION] "
                    "Due candidati consecutivi "
                    "non hanno prodotto "
                    "alcun miglioramento."
                )

                break

        print(
            f"\n[MODEL ESCALATION] "
            f"{model_name} "
            "non ha trovato una "
            "correzione verificata."
        )

    # ==================================
    # NESSUN MODELLO HA RISOLTO
    # ==================================

    report = (
        "Ho provato tutti i modelli "
        "disponibili e nessun candidato "
        "ha migliorato la diagnostica "
        "in modo verificabile."
    )

    print(
        "\n"
        + "=" * 60
        + "\nCODING AGENT - "
        + "NESSUN FIX VERIFICATO\n"
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