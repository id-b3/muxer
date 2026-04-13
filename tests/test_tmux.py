"""Tests for muxer.adapters.tmux - TmuxManager.

Tests that require a live tmux server use the ``server`` and ``session``
fixtures provided by libtmux's pytest plugin (registered via entry-point).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import libtmux
import pytest
import yaml

from muxer.adapters.tmux import TmuxManager
from muxer.config import TmuxTemplate

# ---------------------------------------------------------------------------
# Template discovery (no tmux server needed)
# ---------------------------------------------------------------------------


class TestGetTemplates:
    def test_discovers_yaml_yml_json(self, tmp_tmuxp_config_dir: Path) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        # Bypass __init__ since we don't need a real server for this
        templates = tm.get_templates(tmp_tmuxp_config_dir)
        names = {t.name for t in templates}
        assert names == {"ci", "dev", "ops"}

    def test_ignores_non_template_files(self, tmp_tmuxp_config_dir: Path) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        templates = tm.get_templates(tmp_tmuxp_config_dir)
        assert all(t.name != "notes" for t in templates)

    def test_sorted_by_name(self, tmp_tmuxp_config_dir: Path) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        templates = tm.get_templates(tmp_tmuxp_config_dir)
        assert [t.name for t in templates] == sorted(t.name for t in templates)

    def test_empty_for_missing_dir(self, tmp_path: Path) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        assert tm.get_templates(tmp_path / "nope") == []

    def test_empty_for_file(self, tmp_path: Path) -> None:
        f = tmp_path / "afile"
        f.touch()
        tm = TmuxManager.__new__(TmuxManager)
        assert tm.get_templates(f) == []


class TestReadConfig:
    def _make_manager(self) -> TmuxManager:
        tm = TmuxManager.__new__(TmuxManager)
        return tm

    def test_read_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "t.yaml"
        p.write_text(yaml.dump({"session_name": "test"}), encoding="utf-8")
        assert self._make_manager()._read_config(p) == {"session_name": "test"}

    def test_read_yml(self, tmp_path: Path) -> None:
        p = tmp_path / "t.yml"
        p.write_text(yaml.dump({"a": 1}), encoding="utf-8")
        assert self._make_manager()._read_config(p)["a"] == 1

    def test_read_json(self, tmp_path: Path) -> None:
        p = tmp_path / "t.json"
        p.write_text(json.dumps({"b": 2}), encoding="utf-8")
        assert self._make_manager()._read_config(p)["b"] == 2

    def test_unsupported_format_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "t.toml"
        p.write_text("key = 'val'", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported template format"):
            self._make_manager()._read_config(p)


class TestStartDirectoryDefaults:
    def _make_manager(self) -> TmuxManager:
        return TmuxManager.__new__(TmuxManager)

    def test_sets_missing_window_and_pane_start_directory(self) -> None:
        config: dict[str, Any] = {
            "windows": [
                {
                    "window_name": "editor",
                    "panes": [{"shell_command": "nvim ."}, "git status"],
                }
            ]
        }
        self._make_manager()._apply_start_directory_defaults(config, "/work/repo")

        window = config["windows"][0]
        assert window["start_directory"] == "/work/repo"
        assert window["panes"][0]["start_directory"] == "/work/repo"

    def test_preserves_explicit_window_start_directory(self) -> None:
        config: dict[str, Any] = {
            "windows": [
                {
                    "window_name": "editor",
                    "start_directory": "/custom/window/path",
                    "panes": [{"shell_command": "nvim ."}],
                }
            ]
        }
        self._make_manager()._apply_start_directory_defaults(config, "/work/repo")

        window = config["windows"][0]
        assert window["start_directory"] == "/custom/window/path"
        assert "start_directory" not in window["panes"][0]

    def test_preserves_explicit_pane_start_directory(self) -> None:
        config: dict[str, Any] = {
            "windows": [
                {
                    "window_name": "editor",
                    "panes": [
                        {
                            "start_directory": "/custom/pane/path",
                            "shell_command": "nvim .",
                        }
                    ],
                }
            ]
        }
        self._make_manager()._apply_start_directory_defaults(config, "/work/repo")

        pane = config["windows"][0]["panes"][0]
        assert pane["start_directory"] == "/custom/pane/path"


# ---------------------------------------------------------------------------
# Live tmux server tests (libtmux fixtures)
# ---------------------------------------------------------------------------


class TestKillSession:
    def test_kill_existing_session(self, server: libtmux.Server) -> None:
        server.new_session(session_name="kill-me")
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server
        tm.kill_session("kill-me")
        assert not server.has_session("kill-me")

    def test_kill_nonexistent_raises(self, server: libtmux.Server) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server
        with pytest.raises(ValueError, match="not found"):
            tm.kill_session("does-not-exist")


class TestFreezeSession:
    def test_freeze_returns_dict(self, server: libtmux.Server) -> None:
        sess = server.new_session(session_name="freeze-me")
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server
        config = tm.freeze_session("freeze-me")
        assert isinstance(config, dict)
        assert config["session_name"] == "freeze-me"
        assert "windows" in config
        sess.kill()

    def test_freeze_nonexistent_raises(self, server: libtmux.Server) -> None:
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server
        with pytest.raises(ValueError, match="not found"):
            tm.freeze_session("no-such-session")


class TestGetActiveSessions:
    def test_lists_sessions(self, server: libtmux.Server) -> None:
        server.new_session(session_name="s1")
        server.new_session(session_name="s2")
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server
        sessions = tm.get_active_sessions()
        names = {s.name for s in sessions}
        assert "s1" in names
        assert "s2" in names


class TestLaunchTemplate:
    def test_launch_creates_session(self, server: libtmux.Server, tmp_path: Path) -> None:
        template_config: dict[str, Any] = {
            "session_name": "placeholder",
            "windows": [{"window_name": "main", "panes": [""]}],
        }
        tmpl_file = tmp_path / "basic.yaml"
        tmpl_file.write_text(yaml.dump(template_config), encoding="utf-8")

        template = TmuxTemplate(path=tmpl_file, name="basic")
        tm = TmuxManager.__new__(TmuxManager)
        tm.server = server

        tm.launch_template(template, session_name="launched-test", start_directory=tmp_path)
        assert server.has_session("launched-test")
        # Cleanup
        server.kill_session("launched-test")
