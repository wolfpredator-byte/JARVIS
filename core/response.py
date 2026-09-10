import re
from dataclasses import dataclass


@dataclass
class JarvisResponse:
    display: str
    speech: str


def build_spoken_summary(
    full_text: str,
    file_name: str | None = None,
    issue_count: int | None = None,
    max_chars: int = 320
) -> str:

    # Elimina completamente i blocchi di codice
    cleaned = re.sub(
        r"```.*?```",
        " ",
        full_text,
        flags=re.DOTALL
    )

    # Elimina markdown inline
    cleaned = re.sub(
        r"`([^`]*)`",
        r"\1",
        cleaned
    )

    # Elimina titoli, bullet e liste numerate
    cleaned = re.sub(
        r"(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|\d+[.)]\s+)",
        "",
        cleaned
    )

    cleaned = cleaned.replace("*", "")
    cleaned = cleaned.replace("_", "")

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned
    ).strip()

    # Prende al massimo le prime due frasi utili
    sentences = re.split(
        r"(?<=[.!?])\s+",
        cleaned
    )

    short_content = " ".join(
        sentences[:2]
    ).strip()

    if len(short_content) > 180:
        short_content = short_content[:180]

        if " " in short_content:
            short_content = short_content.rsplit(
                " ",
                1
            )[0]

        short_content += "..."

    parts = []

    if file_name:
        parts.append(
            f"Ho analizzato {file_name}."
        )

    if issue_count is not None:
        if issue_count == 0:
            parts.append(
                "Pyright non segnala problemi."
            )

        elif issue_count == 1:
            parts.append(
                "Pyright segnala un problema."
            )

        else:
            parts.append(
                f"Pyright segnala {issue_count} problemi."
            )

    if short_content:
        parts.append(short_content)

    parts.append(
        "Ti ho lasciato i dettagli completi nel terminale."
    )

    speech = " ".join(parts)

    if len(speech) > max_chars:
        speech = speech[:max_chars].rsplit(
            " ",
            1
        )[0] + "..."

    return speech