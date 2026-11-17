"""Unit tests for the Coder agent's pure helper functions."""

from vectra.agents.coder import (
    _parse_patches,
    _validate_patch,
    _extract_python_imports,
    _detect_new_imports,
    _generate_fallback_dockerfile_uv,
)


class TestParsePatches:
    def test_plain_array(self):
        raw = '[{"file": "app.py", "new_content": "x = 1", "description": "fix"}]'
        patches = _parse_patches(raw)
        assert len(patches) == 1
        assert patches[0]["file"] == "app.py"

    def test_fenced_array(self):
        raw = '```json\n[{"file": "a.py", "new_content": "y"}]\n```'
        assert len(_parse_patches(raw)) == 1

    def test_empty(self):
        assert _parse_patches("") == []


class TestValidatePatch:
    def test_new_file_always_valid(self):
        ok, reason = _validate_patch(None, "SECRET=abc", ".env")
        assert ok
        assert reason == "new file"

    def test_massive_shrink_rejected(self):
        original = "\n".join(f"line{i}" for i in range(100))
        ok, reason = _validate_patch(original, "line0\nline1", "app.py")
        assert not ok
        assert "reduced file" in reason

    def test_deleted_function_rejected(self):
        original = "def a():\n    pass\n\ndef b():\n    pass\n\ndef c():\n    pass\n"
        patched = "def a():\n    pass\n# removed b and c\n# padding\n# padding\n# padding\n"
        ok, reason = _validate_patch(original, patched, "app.py")
        assert not ok
        assert "definitions" in reason

    def test_nearly_empty_rejected(self):
        ok, _ = _validate_patch("x = 1", "  ", "app.py")
        assert not ok

    def test_good_patch_accepted(self):
        original = 'def login(pw):\n    return pw == "admin"\n'
        patched = (
            "import hmac\n\ndef login(pw):\n"
            '    return hmac.compare_digest(pw, get_hash())\n'
        )
        ok, reason = _validate_patch(original, patched, "app.py")
        assert ok


class TestImportExtraction:
    def test_import_forms(self):
        content = (
            "import bcrypt\n"
            "from dotenv import load_dotenv\n"
            "import fastapi.responses\n"
            "import os\n"  # stdlib — must be excluded
        )
        pkgs = _extract_python_imports(content)
        assert pkgs == {"bcrypt", "dotenv", "fastapi"}

    def test_detect_new_imports(self):
        old = {"app.py": "import fastapi\n"}
        new = {"app.py": "import fastapi\nimport bcrypt\n"}
        assert _detect_new_imports(old, new) == {"bcrypt"}


class TestFallbackDockerfile:
    def test_fastapi_entrypoint_detected(self):
        manifest = {
            "main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
            "pyproject.toml": "[project]\nname='x'\n",
            "uv.lock": "",
        }
        dockerfile = _generate_fallback_dockerfile_uv(manifest, "")
        assert "uvicorn" in dockerfile
        assert '"main:app"' in dockerfile
        assert "--frozen" in dockerfile
        assert "EXPOSE 8000" in dockerfile

    def test_no_lock_no_frozen(self):
        manifest = {"main.py": "print('hi')\n", "pyproject.toml": ""}
        dockerfile = _generate_fallback_dockerfile_uv(manifest, "")
        assert "--frozen" not in dockerfile
