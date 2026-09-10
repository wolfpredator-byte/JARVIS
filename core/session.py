from dataclasses import dataclass


@dataclass
class JarvisSession:
    last_project: str | None = None
    last_file: str | None = None
    last_request: str | None = None

    last_diagnostics: str | None = None
    last_ai_response: str | None = None

    pending_fix: str | None = None


session = JarvisSession()