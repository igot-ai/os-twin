"""Tests for dashboard/bot_manager.py"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestBotDirResolution:
    """Test BOT_DIR resolution logic."""

    def test_bot_dir_prefers_ostwin_home(self, tmp_path, monkeypatch):
        """BOT_DIR should prefer ~/.ostwin/bot/ when it exists."""
        # Create bot/package.json in temp ostwin home
        bot_dir = tmp_path / ".ostwin" / "bot"
        bot_dir.mkdir(parents=True)
        (bot_dir / "package.json").write_text("{}")
        
        # Patch Path.home() to return tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        # Remove module from cache and re-import
        if "dashboard.bot_manager" in sys.modules:
            del sys.modules["dashboard.bot_manager"]
        
        import dashboard.bot_manager as bm
        
        assert bm.BOT_DIR == tmp_path / ".ostwin" / "bot"
    
    def test_bot_dir_fallback_to_relative(self, tmp_path, monkeypatch):
        """BOT_DIR should fallback to relative path when ~/.ostwin/bot/ doesn't exist."""
        # Patch Path.home() to return tmp_path (no bot/package.json)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        # Remove module from cache and re-import
        if "dashboard.bot_manager" in sys.modules:
            del sys.modules["dashboard.bot_manager"]
        
        import dashboard.bot_manager as bm
        
        # Should be sibling of dashboard directory
        assert bm.BOT_DIR == bm._DASHBOARD_DIR.parent / "bot"


class TestBotProcessManager:
    """Test BotProcessManager class."""

    def test_init_with_default_dir(self):
        """BotProcessManager should use BOT_DIR by default."""
        from dashboard.bot_manager import BotProcessManager, BOT_DIR
        
        manager = BotProcessManager()
        assert manager.bot_dir == BOT_DIR
    
    def test_init_with_custom_dir(self, tmp_path):
        """BotProcessManager should accept custom bot_dir."""
        from dashboard.bot_manager import BotProcessManager
        
        custom_dir = tmp_path / "custom-bot"
        manager = BotProcessManager(bot_dir=custom_dir)
        
        assert manager.bot_dir == custom_dir
    
    def test_status_when_not_running(self):
        """Status should return correct info when bot is not running."""
        from dashboard.bot_manager import BotProcessManager
        
        manager = BotProcessManager()
        status = manager.status()
        
        assert status["running"] is False
        assert status["pid"] is None
        assert status["started_at"] is None
    
    def test_is_running_false_when_no_process(self):
        """is_running should be False when no process exists."""
        from dashboard.bot_manager import BotProcessManager
        
        manager = BotProcessManager()
        assert manager.is_running is False

    def test_find_tsx_local(self, tmp_path):
        """_find_tsx should return local tsx path when available."""
        from dashboard.bot_manager import BotProcessManager
        
        # Create mock tsx binary
        node_modules = tmp_path / "node_modules" / ".bin"
        node_modules.mkdir(parents=True)
        tsx_path = node_modules / "tsx"
        tsx_path.touch()
        
        manager = BotProcessManager(bot_dir=tmp_path)
        result = manager._find_tsx()
        
        assert result is not None
        exe, args = result
        assert exe == str(tsx_path)
        assert args == []
    
    def test_find_tsx_npx_fallback(self, tmp_path, monkeypatch):
        """_find_tsx should return npx tsx as fallback when local tsx not found."""
        from dashboard.bot_manager import BotProcessManager
        import shutil
        
        # Mock shutil.which to find npx
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/npx" if x == "npx" else None)
        
        manager = BotProcessManager(bot_dir=tmp_path)
        result = manager._find_tsx()
        
        assert result is not None
        exe, args = result
        assert exe == "/usr/bin/npx"
        assert args == ["tsx"]
    
    def test_find_tsx_returns_none_when_not_found(self, tmp_path, monkeypatch):
        """_find_tsx should return None when neither local tsx nor npx available."""
        from dashboard.bot_manager import BotProcessManager
        import shutil
        
        # Mock shutil.which to return None (npx not found)
        monkeypatch.setattr(shutil, "which", lambda x: None)
        
        manager = BotProcessManager(bot_dir=tmp_path)
        result = manager._find_tsx()
        
        assert result is None


class TestEnsureBotDependencies:
    """Test ensure_bot_dependencies function."""

    def test_returns_true_when_node_modules_exists(self, tmp_path, monkeypatch):
        """Should return True if node_modules already exists."""
        # Create node_modules
        (tmp_path / "node_modules").mkdir()
        
        # Patch BOT_DIR
        import dashboard.bot_manager as bm
        monkeypatch.setattr(bm, "BOT_DIR", tmp_path)
        
        result = bm.ensure_bot_dependencies()
        assert result is True
    
    def test_returns_false_when_no_package_json(self, tmp_path, monkeypatch):
        """Should return False if package.json doesn't exist."""
        import dashboard.bot_manager as bm
        monkeypatch.setattr(bm, "BOT_DIR", tmp_path)
        
        result = bm.ensure_bot_dependencies()
        assert result is False
    
    def test_installs_dependencies_when_missing(self, tmp_path, monkeypatch):
        """Should install dependencies when node_modules missing."""
        import dashboard.bot_manager as bm
        import subprocess
        
        # Create package.json
        (tmp_path / "package.json").write_text('{"name": "test"}')
        
        # Patch BOT_DIR
        monkeypatch.setattr(bm, "BOT_DIR", tmp_path)
        
        # Mock subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run = MagicMock(return_value=mock_result)
        monkeypatch.setattr(subprocess, "run", mock_run)
        
        # Mock shutil.which to find npm
        import shutil
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/npm" if x == "npm" else None)
        
        result = bm.ensure_bot_dependencies()
        
        assert result is True
        mock_run.assert_called_once()
