import ast


FOCUS_FALLBACK_RADIUS = 35
MAX_FOCUSED_LINES = 160


def _diagnostic_lines(
    diagnostics: list[dict]
) -> list[int]:

    lines = []

    for diagnostic in diagnostics:
        line = diagnostic.get("line")

        if isinstance(line, int) and line > 0:
            lines.append(line)

    return sorted(set(lines))


def _node_contains_line(
    node: ast.AST,
    line: int
) -> bool:

    start = getattr(
        node,
        "lineno",
        None
    )

    end = getattr(
        node,
        "end_lineno",
        None
    )

    if (
        not isinstance(start, int)
        or not isinstance(end, int)
    ):
        return False

    return start <= line <= end


def _find_smallest_relevant_node(
    tree: ast.AST,
    line: int
) -> ast.AST | None:

    candidates = []

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            )
        ):
            continue

        if not _node_contains_line(
            node,
            line
        ):
            continue

        start = getattr(
            node,
            "lineno",
            0
        )

        end = getattr(
            node,
            "end_lineno",
            start
        )

        size = end - start

        candidates.append(
            (
                size,
                node
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def _extract_node_source(
    lines: list[str],
    node: ast.AST
) -> str | None:

    start = getattr(
        node,
        "lineno",
        None
    )

    end = getattr(
        node,
        "end_lineno",
        None
    )

    if (
        not isinstance(start, int)
        or not isinstance(end, int)
    ):
        return None

    start_index = max(
        0,
        start - 1
    )

    end_index = min(
        len(lines),
        end
    )

    return "".join(
        lines[start_index:end_index]
    )


def _fallback_context(
    code: str,
    diagnostic_lines: list[int]
) -> str:

    lines = code.splitlines(
        keepends=True
    )

    if not lines:
        return code

    if not diagnostic_lines:
        return "".join(
            lines[:MAX_FOCUSED_LINES]
        )

    first_line = min(
        diagnostic_lines
    )

    last_line = max(
        diagnostic_lines
    )

    start = max(
        0,
        first_line
        - FOCUS_FALLBACK_RADIUS
        - 1
    )

    end = min(
        len(lines),
        last_line
        + FOCUS_FALLBACK_RADIUS
    )

    selected = lines[start:end]

    if len(selected) > MAX_FOCUSED_LINES:
        selected = selected[
            :MAX_FOCUSED_LINES
        ]

    return "".join(selected)


def build_focused_code(
    code: str,
    diagnostics: list[dict]
) -> str:

    diagnostic_lines = (
        _diagnostic_lines(
            diagnostics
        )
    )

    if not diagnostic_lines:
        return _fallback_context(
            code,
            diagnostic_lines
        )

    try:
        tree = ast.parse(code)

    except SyntaxError:
        return _fallback_context(
            code,
            diagnostic_lines
        )

    lines = code.splitlines(
        keepends=True
    )

    selected_blocks = []
    selected_ranges = set()

    for line in diagnostic_lines:

        node = (
            _find_smallest_relevant_node(
                tree,
                line
            )
        )

        if node is None:
            continue

        start = getattr(
            node,
            "lineno",
            None
        )

        end = getattr(
            node,
            "end_lineno",
            None
        )

        if (
            not isinstance(start, int)
            or not isinstance(end, int)
        ):
            continue

        node_range = (
            start,
            end
        )

        if node_range in selected_ranges:
            continue

        selected_ranges.add(
            node_range
        )

        source = _extract_node_source(
            lines,
            node
        )

        if source:
            selected_blocks.append(
                source
            )

    if not selected_blocks:
        return _fallback_context(
            code,
            diagnostic_lines
        )

    focused_code = "\n\n".join(
        selected_blocks
    )

    focused_lines = (
        focused_code.splitlines(
            keepends=True
        )
    )

    if (
        len(focused_lines)
        > MAX_FOCUSED_LINES
    ):
        return _fallback_context(
            code,
            diagnostic_lines
        )

    return focused_code