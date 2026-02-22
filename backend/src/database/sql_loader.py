from pathlib import Path

_SQL_DIR = Path(__file__).parent / "sql"


def load_sql(filename: str) -> dict[str, str]:
    """Parse a SQL file with '-- name: query_name' sections into a dict of named queries."""
    path = _SQL_DIR / filename
    content = path.read_text()

    queries: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- name:"):
            if current_name is not None:
                queries[current_name] = "\n".join(current_lines).strip()
            current_name = stripped[len("-- name:"):].strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        queries[current_name] = "\n".join(current_lines).strip()

    return queries
