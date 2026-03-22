import os
import re
import ast
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"


class TestJavaScriptSyntax:
    """Test JavaScript files for syntax errors"""

    JS_FILES = [
        FRONTEND_DIR / "src" / "app.js",
        FRONTEND_DIR / "src" / "services" / "api.js",
        FRONTEND_DIR / "src" / "utils" / "formatters.js",
        FRONTEND_DIR / "src" / "utils" / "styles.js",
    ]

    def test_javascript_files_exist(self):
        """All expected JavaScript files should exist"""
        for js_file in self.JS_FILES:
            assert js_file.exists(), f"Missing JavaScript file: {js_file}"

    def test_javascript_braces_balanced(self):
        """JavaScript files should have balanced braces (depth tracking)"""
        for js_file in self.JS_FILES:
            if not js_file.exists():
                continue
            content = js_file.read_text()
            depth = 0
            in_string = False
            string_char = None
            for i, line in enumerate(content.split('\n'), 1):
                for char in line:
                    if char in ('"', "'", '`') and not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char and in_string:
                        in_string = False
                        string_char = None
                    elif not in_string:
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth < 0:
                                pytest.fail(
                                    f"{js_file.name}:{i} - Extra closing brace at depth {depth}"
                                )
            assert depth == 0, (
                f"{js_file.name}: Unclosed braces at end - depth {depth}"
            )

    def test_javascript_parse_with_node(self):
        """Parse JavaScript using Node.js for syntax validation"""
        import shutil
        if not shutil.which("node"):
            pytest.skip("Node.js not installed")

        for js_file in self.JS_FILES:
            if not js_file.exists():
                continue
            content = js_file.read_text()
            import re
            js_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
            if js_match:
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp:
                    tmp.write(js_match.group(1))
                    tmp_path = tmp.name
                try:
                    result = subprocess.run(
                        ["node", "--check", tmp_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode != 0:
                        pytest.fail(
                            f"JavaScript syntax error in {js_file.name}:\n{result.stderr}"
                        )
                finally:
                    import os
                    os.unlink(tmp_path)

    def test_javascript_parentheses_balanced(self):
        """JavaScript files should have balanced parentheses"""
        for js_file in self.JS_FILES:
            if not js_file.exists():
                continue
            content = js_file.read_text()
            open_parens = content.count('(')
            close_parens = content.count(')')
            assert open_parens == close_parens, (
                f"{js_file.name}: Unbalanced parentheses - "
                f"( = {open_parens}, ) = {close_parens}"
            )


class TestPythonSyntax:
    """Test Python files for syntax errors"""

    PYTHON_FILES = [
        BACKEND_DIR / "server.py",
        BACKEND_DIR / "kaggle_solver" / "__init__.py",
    ]

    def test_python_files_syntax(self):
        """Python files should have valid syntax"""
        for py_file in Path(BACKEND_DIR).rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                content = py_file.read_text()
                ast.parse(content)
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file}: {e}")


class TestLibraryImports:
    """Test that required libraries are importable"""

    def test_required_python_packages_installed(self):
        """Required Python packages should be installed"""
        required = ["fastapi", "openai", "pydantic", "yaml", "pytest", "dotenv"]
        for package in required:
            try:
                __import__(package)
            except ImportError:
                pytest.fail(f"Missing required package: {package}")

    def test_frontend_cdn_resources_accessible(self):
        """Frontend CDN resources should be accessible"""
        import urllib.request
        import urllib.error

        cdn_urls = [
            "https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js",
            "https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css",
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css",
        ]

        for url in cdn_urls:
            try:
                req = urllib.request.Request(url, method="HEAD")
                urllib.request.urlopen(req, timeout=10)
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                pytest.fail(f"CDN resource not accessible: {url} - {e}")


class TestHTMLStructure:
    """Test HTML files for basic structure"""

    def test_index_html_exists(self):
        """index.html should exist"""
        index_path = FRONTEND_DIR / "index.html"
        assert index_path.exists(), "Missing index.html"

    def test_index_html_has_required_tags(self):
        """index.html should have required HTML tags"""
        index_path = FRONTEND_DIR / "index.html"
        content = index_path.read_text()

        required_tags = [
            "<!DOCTYPE html>",
            "<html",
            "<head>",
            "<body",
            "</html>",
        ]

        for tag in required_tags:
            assert tag in content, f"Missing required tag in index.html: {tag}"

    def test_alpine_loads_after_app_js(self):
        """Alpine.js should load after app.js is defined"""
        index_path = FRONTEND_DIR / "index.html"
        content = index_path.read_text()

        app_js_pos = content.find('src/app.js')
        alpine_pos = content.find('alpinejs')

        assert app_js_pos > 0, "app.js script tag not found"
        assert alpine_pos > app_js_pos, (
            "Alpine.js must load AFTER app.js (use defer or place after)"
        )


class TestCodeQuality:
    """Basic code quality checks"""

    JS_FILES = [
        FRONTEND_DIR / "src" / "app.js",
        FRONTEND_DIR / "src" / "api.js",
        FRONTEND_DIR / "src" / "utils" / "helpers.js",
    ]

    def test_no_debug_code_in_production(self):
        """No debug console.log statements in production JS"""
        app_js = FRONTEND_DIR / "src" / "app.js"
        if not app_js.exists():
            return

        content = app_js.read_text()
        lines = content.split("\n")

        debug_patterns = [
            r"console\.log\(['\"]DEBUG",
            r"console\.debug\(",
            r"// TODO:.*BUG",
            r"// FIXME:",
        ]

        for i, line in enumerate(lines, 1):
            for pattern in debug_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    pytest.fail(
                        f"{app_js.name}:{i} - Debug code found: {line.strip()}"
                    )

    def test_no_hardcoded_secrets(self):
        """No hardcoded secrets in source files"""
        secret_patterns = [
            r'api_key\s*=\s*["\'][^"\']{20,}',  # Long API keys
            r'password\s*=\s*["\'][^"\']+',  # Passwords
            r'secret\s*=\s*["\'][^"\']+',  # Secrets
        ]

        for py_file in Path(BACKEND_DIR).rglob("*.py"):
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue

            content = py_file.read_text()
            for pattern in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    pytest.fail(
                        f"Potential secret found in {py_file.name}: {matches[0][:30]}..."
                    )

    def test_consistent_indentation(self):
        """Files should use consistent indentation (spaces, not tabs)"""
        for js_file in self.JS_FILES:
            if not js_file.exists():
                continue
            content = js_file.read_text()
            lines = content.split("\n")

            tab_lines = [
                (i + 1, line)
                for i, line in enumerate(lines)
                if "\t" in line and not line.strip().startswith("*")
            ]

            assert len(tab_lines) == 0, (
                f"{js_file.name} uses tabs instead of spaces on lines: "
                f"{[l[0] for l in tab_lines[:5]]}"
            )


class TestCSSFiles:
    """Test CSS files for basic validity"""

    def test_css_files_exist(self):
        """Required CSS files should exist"""
        css_files = [
            FRONTEND_DIR / "src" / "css" / "styles.css",
            FRONTEND_DIR / "src" / "css" / "tokens.css",
            FRONTEND_DIR / "src" / "css" / "base.css",
            FRONTEND_DIR / "src" / "css" / "domains" / "spheres.css",
            FRONTEND_DIR / "src" / "css" / "components" / "components.css",
        ]
        for css_file in css_files:
            assert css_file.exists(), f"Missing CSS file: {css_file}"

    def test_css_braces_balanced(self):
        """CSS files should have balanced braces"""
        css_files = list((FRONTEND_DIR / "src" / "css").rglob("*.css"))
        for css_file in css_files:
            if not css_file.exists():
                continue
            content = css_file.read_text()
            open_braces = content.count("{")
            close_braces = content.count("}")
            assert open_braces == close_braces, (
                f"{css_file.name}: Unbalanced braces"
            )
