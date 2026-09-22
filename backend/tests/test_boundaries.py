"""The two import rules the architecture rests on, checked on every run."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [p for d in ("clinic_agent", "seeds", "api") for p in (ROOT / d).rglob("*.py")] + [ROOT / "main.py"]
VENDORS = ("livekit.plugins",)
DATABASE = ("sqlalchemy", "alembic")


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _offenders(prefixes: tuple[str, ...], allowed: str) -> list[str]:
    return sorted(
        str(p.relative_to(ROOT))
        for p in SOURCES
        if allowed not in p.relative_to(ROOT).parts
        and any(n == pre or n.startswith(pre + ".") for n in _imports(p) for pre in prefixes)
    )


def test_only_store_imports_the_database_library():
    assert _offenders(DATABASE, "store") == []


def test_only_providers_import_a_vendor_package():
    assert _offenders(VENDORS, "providers") == []
