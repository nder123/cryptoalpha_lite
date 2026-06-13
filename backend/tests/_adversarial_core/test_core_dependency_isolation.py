import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent
CORE_SOURCE_FILES = tuple(
    path
    for path in CORE_DIR.glob("*.py")
    if path.name not in {"__init__.py"} and not path.name.startswith("test_")
)

FORBIDDEN_IMPORT_PREFIXES = (
    "app",
    "runtime",
    "scripts",
    "services",
    "stress",
)

FORBIDDEN_STANDARD_IMPORTS = (
    "datetime",
    "http",
    "importlib",
    "os",
    "pathlib",
    "requests",
    "socket",
    "subprocess",
    "sys",
    "time",
    "uuid",
)


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    return tuple(imported)


def test_core_has_no_runtime_or_upper_layer_dependencies():
    for path in CORE_SOURCE_FILES:
        for imported in _imports(path):
            assert not imported.startswith(FORBIDDEN_IMPORT_PREFIXES)


def test_core_has_no_dynamic_or_environment_dependencies():
    for path in CORE_SOURCE_FILES:
        imports = _imports(path)

        assert all(imported not in FORBIDDEN_STANDARD_IMPORTS for imported in imports)
