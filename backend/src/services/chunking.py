import ast
import re
from dataclasses import dataclass

# research.md §3: function/class-boundary chunking where a lightweight parser
# is feasible (Python: stdlib ast), heuristic boundaries for TS/JS, flat-text
# fallback otherwise. Naive flat splitting for everything would undersell the
# one workflow this phase exists to prove.

FLAT_CHUNK_LINES = 60
FLAT_CHUNK_OVERLAP = 5

_JS_BOUNDARY_RE = re.compile(
    r"^\s*(export\s+)?(default\s+)?"
    r"(async\s+)?function\s+\w+|"
    r"^\s*(export\s+)?class\s+\w+|"
    r"^\s*(export\s+)?(const|let|var)\s+\w+\s*=\s*(async\s*)?\([^)]*\)\s*=>",
)


@dataclass
class CodeChunk:
    text: str
    start_line: int
    end_line: int
    symbol_name: str | None = None


def chunk_source_file(path: str, content: str) -> list[CodeChunk]:
    if path.endswith(".py"):
        chunks = _chunk_python(content)
        if chunks:
            return chunks
    elif path.endswith((".ts", ".tsx", ".js", ".jsx")):
        chunks = _chunk_js_like(content)
        if chunks:
            return chunks
    return _chunk_flat(content)


def _chunk_python(content: str) -> list[CodeChunk] | None:
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines()
    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]
    if not top_level_defs:
        return None

    chunks: list[CodeChunk] = []
    prev_end = 0
    for node in sorted(top_level_defs, key=lambda n: n.lineno):
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        # Leftover module-level code between the previous def and this one
        # (imports, constants, etc.) becomes its own chunk so nothing is lost.
        if start > prev_end:
            leftover = "\n".join(lines[prev_end:start]).strip()
            if leftover:
                chunks.append(CodeChunk(text=leftover, start_line=prev_end + 1, end_line=start))
        chunks.append(
            CodeChunk(
                text="\n".join(lines[start:end]),
                start_line=start + 1,
                end_line=end,
                symbol_name=node.name,
            )
        )
        prev_end = end

    if prev_end < len(lines):
        leftover = "\n".join(lines[prev_end:]).strip()
        if leftover:
            chunks.append(CodeChunk(text=leftover, start_line=prev_end + 1, end_line=len(lines)))
    return chunks


def _chunk_js_like(content: str) -> list[CodeChunk] | None:
    lines = content.splitlines()
    boundaries = [i for i, line in enumerate(lines) if _JS_BOUNDARY_RE.match(line)]
    if not boundaries:
        return None

    chunks: list[CodeChunk] = []
    if boundaries[0] > 0:
        leftover = "\n".join(lines[: boundaries[0]]).strip()
        if leftover:
            chunks.append(CodeChunk(text=leftover, start_line=1, end_line=boundaries[0]))

    for idx, start in enumerate(boundaries):
        end = boundaries[idx + 1] if idx + 1 < len(boundaries) else len(lines)
        symbol_match = re.search(r"(function|class|const|let|var)\s+(\w+)", lines[start])
        chunks.append(
            CodeChunk(
                text="\n".join(lines[start:end]),
                start_line=start + 1,
                end_line=end,
                symbol_name=symbol_match.group(2) if symbol_match else None,
            )
        )
    return chunks


def _chunk_flat(content: str) -> list[CodeChunk]:
    lines = content.splitlines()
    if not lines:
        return []
    chunks = []
    step = FLAT_CHUNK_LINES - FLAT_CHUNK_OVERLAP
    for start in range(0, len(lines), step):
        end = min(start + FLAT_CHUNK_LINES, len(lines))
        chunks.append(
            CodeChunk(text="\n".join(lines[start:end]), start_line=start + 1, end_line=end)
        )
        if end == len(lines):
            break
    return chunks
