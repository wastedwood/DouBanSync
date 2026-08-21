from pathlib import Path
import unittest

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "app" / "templates"
STATIC_DIR = ROOT / "app" / "static"


class FrontendStructureTests(unittest.TestCase):
    def test_all_templates_parse(self):
        environment = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        for path in TEMPLATE_DIR.glob("*.html"):
            with self.subTest(template=path.name):
                source = path.read_text(encoding="utf-8")
                environment.parse(source)

    def test_frontend_uses_local_assets(self):
        base = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", base)
        self.assertIn("vendor/bootstrap/bootstrap.min.css", base)
        self.assertTrue((STATIC_DIR / "vendor" / "bootstrap" / "bootstrap.min.css").is_file())
        self.assertTrue((STATIC_DIR / "vendor" / "bootstrap" / "bootstrap.bundle.min.js").is_file())

    def test_sidebar_shows_current_project_version(self):
        base = (TEMPLATE_DIR / "base.html").read_text(encoding="utf-8")
        self.assertIn('class="sidebar-version">v0.2.2</span>', base)

    def test_templates_have_no_inline_event_handlers(self):
        html = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATE_DIR.glob("*.html"))
        for attribute in ("onclick=", "onchange=", "oninput="):
            self.assertNotIn(attribute, html)

    def test_approved_brand_assets_exist(self):
        for filename in ("brand-mark.svg", "favicon.svg"):
            path = STATIC_DIR / "img" / filename
            self.assertTrue(path.is_file())
            self.assertIn("#3478e5", path.read_text(encoding="utf-8"))
            self.assertIn("#00b56a", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
