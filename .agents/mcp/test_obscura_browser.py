#!/usr/bin/env python3
"""Tests for obscura-browser-server.py (pure unit tests, no browser launch)."""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


def _load_obscura_server():
    """Load obscura-browser-server.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "obscura_browser_server",
        Path(__file__).parent / "obscura-browser-server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSanitizeFilename:
    """Tests for _sanitize_filename helper."""

    def test_basic_filename(self):
        module = _load_obscura_server()
        assert module._sanitize_filename("document.pdf") == "document.pdf"
        assert module._sanitize_filename("image.png") == "image.png"
        assert module._sanitize_filename("file.txt") == "file.txt"

    def test_removes_forward_slash(self):
        """Cross-platform: strips / on all OSes."""
        module = _load_obscura_server()
        assert module._sanitize_filename("path/to/file.pdf") == "file.pdf"
        assert module._sanitize_filename("deep/nested/path/file.pdf") == "file.pdf"

    def test_removes_backslash(self):
        """Cross-platform: strips \\ on all OSes."""
        module = _load_obscura_server()
        assert module._sanitize_filename("path\\to\\file.pdf") == "file.pdf"
        assert module._sanitize_filename("C\\Users\\file.pdf") == "file.pdf"

    def test_removes_both_separators(self):
        """Cross-platform: strips both / and \\ on all OSes."""
        module = _load_obscura_server()
        assert module._sanitize_filename("path/to\\file.pdf") == "file.pdf"
        assert module._sanitize_filename("a/b\\c/d\\e.pdf") == "e.pdf"

    def test_removes_parent_references(self):
        module = _load_obscura_server()
        assert module._sanitize_filename("....secret") == "secret"
        assert module._sanitize_filename("..file.pdf") == "file.pdf"

    def test_removes_special_characters(self):
        module = _load_obscura_server()
        assert module._sanitize_filename("file<script>.pdf") == "file_script_.pdf"
        assert module._sanitize_filename("file|pipe.pdf") == "file_pipe.pdf"
        assert module._sanitize_filename("file:colon.pdf") == "file_colon.pdf"

    def test_empty_filename(self):
        module = _load_obscura_server()
        assert module._sanitize_filename("") == "download"
        assert module._sanitize_filename("   ") == "download"

    def test_dot_only_filename(self):
        module = _load_obscura_server()
        assert module._sanitize_filename(".") == "download"
        assert module._sanitize_filename("..") == "download"
        assert module._sanitize_filename("...") == "download"

    def test_max_length_preserves_extension(self):
        module = _load_obscura_server()
        long_name = "a" * 500 + ".pdf"
        result = module._sanitize_filename(long_name)
        assert len(result) == 255
        assert result.endswith(".pdf")

    def test_max_length_no_extension(self):
        module = _load_obscura_server()
        long_name = "a" * 500
        result = module._sanitize_filename(long_name)
        assert len(result) == 255

    def test_unicode_filename(self):
        module = _load_obscura_server()
        result = module._sanitize_filename("文档.pdf")
        assert ".pdf" in result


class TestIsSafeDownloadPath:
    """Tests for _is_safe_download_path helper."""

    def test_valid_path(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert module._is_safe_download_path(tmpdir, os.path.join(tmpdir, "file.pdf"))
            assert module._is_safe_download_path(tmpdir, os.path.join(tmpdir, "subdir", "file.pdf"))

    def test_blocks_parent_traversal(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            parent_dir = os.path.dirname(tmpdir)
            outside_path = os.path.join(parent_dir, "outside.pdf")
            assert not module._is_safe_download_path(tmpdir, outside_path)

    def test_blocks_absolute_outside(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            other_tmp = tempfile.mkdtemp()
            try:
                assert not module._is_safe_download_path(tmpdir, os.path.join(other_tmp, "file.pdf"))
            finally:
                os.rmdir(other_tmp)

    def test_same_directory(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            assert module._is_safe_download_path(tmpdir, tmpdir)


class TestSafeDownloadPath:
    """Tests for _safe_download_path helper."""

    def test_constructs_safe_path(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = module._safe_download_path(tmpdir, "document.pdf")
            assert result == os.path.join(tmpdir, "document.pdf")

    def test_sanitizes_filename(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = module._safe_download_path(tmpdir, "file<script>.pdf")
            assert result == os.path.join(tmpdir, "file_script_.pdf")

    def test_path_traversal_sanitized_not_raised(self):
        """Path traversal is prevented by sanitization."""
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = module._safe_download_path(tmpdir, "../../secret.pdf")
            assert result == os.path.join(tmpdir, "secret.pdf")
            assert module._is_safe_download_path(tmpdir, result)


class TestResolveDownloadDir:
    """Tests for _resolve_download_dir helper."""

    def test_uses_ostwin_browser_download_dir(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_val = os.environ.get("OSTWIN_BROWSER_DOWNLOAD_DIR")
            try:
                os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = tmpdir
                result = module._resolve_download_dir()
                assert os.path.abspath(result) == os.path.abspath(tmpdir)
            finally:
                if old_val is not None:
                    os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = old_val
                else:
                    os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)

    def test_uses_agent_os_room_dir_fallback(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_browser = os.environ.get("OSTWIN_BROWSER_DOWNLOAD_DIR")
            old_room = os.environ.get("AGENT_OS_ROOM_DIR")
            try:
                os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
                os.environ["AGENT_OS_ROOM_DIR"] = tmpdir
                result = module._resolve_download_dir()
                expected = os.path.join(tmpdir, "artifacts", "downloads")
                assert os.path.abspath(result) == os.path.abspath(expected)
            finally:
                if old_browser is not None:
                    os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = old_browser
                else:
                    os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
                if old_room is not None:
                    os.environ["AGENT_OS_ROOM_DIR"] = old_room
                else:
                    os.environ.pop("AGENT_OS_ROOM_DIR", None)

    def test_creates_directory(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "new_downloads")
            old_val = os.environ.get("OSTWIN_BROWSER_DOWNLOAD_DIR")
            try:
                os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = download_path
                assert not os.path.exists(download_path)
                result = module._resolve_download_dir()
                assert os.path.exists(download_path)
                assert os.path.isdir(download_path)
            finally:
                if old_val is not None:
                    os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = old_val
                else:
                    os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)

    def test_default_fallback(self):
        module = _load_obscura_server()
        old_browser = os.environ.get("OSTWIN_BROWSER_DOWNLOAD_DIR")
        old_room = os.environ.get("AGENT_OS_ROOM_DIR")
        old_project = os.environ.get("AGENT_OS_ROOT")
        old_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    os.chdir(tmpdir)
                    os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
                    os.environ.pop("AGENT_OS_ROOM_DIR", None)
                    os.environ.pop("AGENT_OS_ROOT", None)
                    result = module._resolve_download_dir()
                    expected = os.path.join(tmpdir, "artifacts", "browser-downloads")
                    assert os.path.abspath(result) == os.path.abspath(expected)
                finally:
                    os.chdir(old_cwd)
        finally:
            if old_browser is not None:
                os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = old_browser
            else:
                os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
            if old_room is not None:
                os.environ["AGENT_OS_ROOM_DIR"] = old_room
            else:
                os.environ.pop("AGENT_OS_ROOM_DIR", None)
            if old_project is not None:
                os.environ["AGENT_OS_ROOT"] = old_project
            else:
                os.environ.pop("AGENT_OS_ROOT", None)

    def test_uses_agent_os_root_fallback(self):
        module = _load_obscura_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            old_browser = os.environ.get("OSTWIN_BROWSER_DOWNLOAD_DIR")
            old_room = os.environ.get("AGENT_OS_ROOM_DIR")
            old_project = os.environ.get("AGENT_OS_ROOT")
            try:
                os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
                os.environ.pop("AGENT_OS_ROOM_DIR", None)
                os.environ["AGENT_OS_ROOT"] = tmpdir
                result = module._resolve_download_dir()
                expected = os.path.join(tmpdir, "artifacts", "browser-downloads")
                assert os.path.abspath(result) == os.path.abspath(expected)
            finally:
                if old_browser is not None:
                    os.environ["OSTWIN_BROWSER_DOWNLOAD_DIR"] = old_browser
                else:
                    os.environ.pop("OSTWIN_BROWSER_DOWNLOAD_DIR", None)
                if old_room is not None:
                    os.environ["AGENT_OS_ROOM_DIR"] = old_room
                else:
                    os.environ.pop("AGENT_OS_ROOM_DIR", None)
                if old_project is not None:
                    os.environ["AGENT_OS_ROOT"] = old_project
                else:
                    os.environ.pop("AGENT_OS_ROOT", None)


class TestLaunchArgs:
    """Tests for launch arg helpers."""

    def test_default_args_no_stealth(self):
        """Default launch args must NOT include --stealth."""
        module = _load_obscura_server()
        args = module._get_default_launch_args(9222)
        assert args == ["serve", "--port", "9222"]
        assert "--stealth" not in args

    def test_build_launch_args_default(self):
        module = _load_obscura_server()
        args = module._build_launch_args(9222, "")
        assert args == ["serve", "--port", "9222"]
        assert "--stealth" not in args

    def test_build_launch_args_with_custom(self):
        module = _load_obscura_server()
        args = module._build_launch_args(9222, "--proxy http://localhost:8080")
        assert "serve" in args
        assert "--port" in args
        assert "9222" in args
        assert "--proxy" in args
        assert "http://localhost:8080" in args

    def test_build_launch_args_preserves_quoted_values(self):
        module = _load_obscura_server()
        args = module._build_launch_args(9222, '--user-agent "Ostwin Browser"')
        assert "--user-agent" in args
        assert "Ostwin Browser" in args

    def test_build_launch_args_rejects_malformed_quotes(self):
        module = _load_obscura_server()
        import pytest
        with pytest.raises(ValueError):
            module._build_launch_args(9222, '--user-agent "unterminated')

    def test_build_launch_args_with_stealth_explicit(self):
        """User can explicitly add --stealth via OBSCURA_ARGS."""
        module = _load_obscura_server()
        args = module._build_launch_args(9222, "--stealth")
        assert "--stealth" in args


class TestRefMap:
    """Tests for element ref map helpers."""

    def test_reset_ref_map(self):
        module = _load_obscura_server()
        module._reset_ref_map()
        module._store_element("@e1", {"role": "button", "name": "Submit"})
        assert len(module._element_ref_map) == 1

        module._reset_ref_map()
        assert len(module._element_ref_map) == 0

    def test_build_ref_sequence(self):
        module = _load_obscura_server()
        module._reset_ref_map()

        ref1 = module._build_ref()
        ref2 = module._build_ref()
        ref3 = module._build_ref()

        assert ref1 == "@e1"
        assert ref2 == "@e2"
        assert ref3 == "@e3"

    def test_resolve_ref_returns_selector(self):
        module = _load_obscura_server()
        module._reset_ref_map()

        module._store_element("@e1", {"ref": "@e1", "role": "button", "name": "Submit", "selector": "button:has-text(\"Submit\")"})

        result = module._resolve_ref("@e1")
        assert result == 'button:has-text("Submit")'

    def test_resolve_ref_returns_raw_if_not_found(self):
        module = _load_obscura_server()
        module._reset_ref_map()

        result = module._resolve_ref("@e999")
        assert result == "@e999"

    def test_resolve_ref_returns_raw_if_not_ref_format(self):
        module = _load_obscura_server()
        result = module._resolve_ref("button.submit")
        assert result == "button.submit"

    def test_build_elements_from_dom_snapshot(self):
        module = _load_obscura_server()
        module._reset_ref_map()

        raw_elements = [
            {"role": "button", "name": "Submit", "selector": "button:nth-of-type(1)"},
            {"role": "link", "name": "Learn More", "selector": "a:nth-of-type(1)"},
        ]

        elements = module._build_elements_from_dom_snapshot(raw_elements)

        assert len(elements) == 2

        refs = [e["ref"] for e in elements]
        assert any(r.startswith("@e") for r in refs)
        assert module._resolve_ref("@e1") == "button:nth-of-type(1)"

    def test_build_elements_skips_unusable_items(self):
        module = _load_obscura_server()
        module._reset_ref_map()

        raw_elements = [
            {"role": "button", "name": "Submit", "selector": ""},
            {"role": "", "name": "", "selector": "button:nth-of-type(1)"},
            {"role": "link", "name": "Docs", "selector": "a:nth-of-type(1)"},
        ]

        elements = module._build_elements_from_dom_snapshot(raw_elements)

        assert len(elements) == 1
        assert elements[0]["name"] == "Docs"


class TestMCPTools:
    """Tests for MCP tool functions (no browser required)."""

    def test_start_browser_returns_dependency_error_without_launch(self, monkeypatch):
        module = _load_obscura_server()
        import asyncio

        async def fake_ensure_browser():
            return {"running": False, "port": 9222, "error": "playwright not installed"}

        def fail_popen(*_args, **_kwargs):
            raise AssertionError("Popen should not be called when client dependency is missing")

        monkeypatch.setattr(module, "_ensure_browser", fake_ensure_browser)
        monkeypatch.setattr(module.subprocess, "Popen", fail_popen)

        result = asyncio.run(module._start_browser())
        assert result["running"] is False
        assert result["error"] == "playwright not installed"

    def test_browser_close_returns_success(self):
        module = _load_obscura_server()
        import asyncio
        result = asyncio.run(module.browser_close())
        data = json.loads(result)
        assert data["success"] is True

    def test_browser_health_without_browser(self):
        module = _load_obscura_server()
        import asyncio
        result = asyncio.run(module.browser_health())
        data = json.loads(result)
        assert "running" in data
        assert "port" in data


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
