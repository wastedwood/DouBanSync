import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins.v3" / "doubansync"


def test_moviepilot_v3_manifest_matches_plugin_version():
    manifest = json.loads((ROOT / "package.v3.json").read_text(encoding="utf-8"))
    source = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")

    assert manifest["DouBanSync"]["version"] == "1.0.0"
    assert 'plugin_version = "1.0.0"' in source
    assert manifest["DouBanSync"]["system_version"] == ">=3.0.0"


def test_moviepilot_plugin_python_sources_compile():
    for path in PLUGIN_DIR.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_moviepilot_plugin_exposes_required_lifecycle_methods():
    tree = ast.parse((PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8"))
    plugin_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DouBanSync"
    )
    methods = {node.name for node in plugin_class.body if isinstance(node, ast.FunctionDef)}

    assert {"init_plugin", "get_state", "get_form", "get_api", "get_service", "stop_service"} <= methods
