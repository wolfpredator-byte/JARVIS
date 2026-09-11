from dataclasses import dataclass


@dataclass
class JarvisSession:
    last_project: str | None = None
    last_file: str | None = None
    last_request: str | None = None
    last_diagnostics: str | None = None
    last_ai_response: str | None = None

    pending_edits: list[dict[str, str]] | None = None
    pending_original_content: str | None = None
    pending_new_content: str | None = None
    pending_diff: str | None = None
    pending_before_score: int | None = None

    last_failed_edits: list[dict[str, str]] | None = None
    last_failed_diagnostics: str | None = None

    fix_retry_count: int = 0
    max_fix_retries: int = 3

    def clear_pending_edit(self):
        self.pending_edits = None
        self.pending_original_content = None
        self.pending_new_content = None
        self.pending_diff = None
        self.pending_before_score = None


session = JarvisSession()