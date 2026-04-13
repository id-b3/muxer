"""Tests for muxer.config - AppConfig, WorkspaceRoot, domain models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from muxer.config import AppConfig, TmuxTemplate, WorkspaceRoot, Worktree

# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


class TestWorktree:
    def test_frozen(self) -> None:
        wt = Worktree(path=Path("/a"), head="abc1234", branch="refs/heads/main")
        with pytest.raises(AttributeError):
            wt.path = Path("/b")  # type: ignore[misc]

    def test_detached(self) -> None:
        wt = Worktree(path=Path("/a"), head="abc1234", branch=None)
        assert wt.branch is None


class TestTmuxTemplate:
    def test_fields(self) -> None:
        t = TmuxTemplate(path=Path("/etc/tmuxp/dev.yaml"), name="dev")
        assert t.name == "dev"
        assert t.path.suffix == ".yaml"


class TestWorkspaceRoot:
    def test_fields(self) -> None:
        wr = WorkspaceRoot(path=Path("/home/user/dev"), label="dev")
        assert wr.label == "dev"


# ---------------------------------------------------------------------------
# AppConfig defaults
# ---------------------------------------------------------------------------


class TestAppConfigDefaults:
    def test_default_values(self) -> None:
        cfg = AppConfig()
        assert len(cfg.workspace_roots) == 1
        assert cfg.workspace_roots[0].label == "dev"
        assert cfg.auto_attach is False
        assert cfg.ignore_worktree_dirs == [".bare"]
        assert "main" in cfg.main_branch_names
        assert cfg.work_dir_expansion == "top"
        assert cfg.theme == "gruvbox"
        assert cfg.header_visualization == "gradient"
        assert cfg.custom_theme is None

    def test_load_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        cfg = AppConfig.load(tmp_path / "nonexistent.json")
        assert cfg == AppConfig()


# ---------------------------------------------------------------------------
# workspace_roots normalisation
# ---------------------------------------------------------------------------


class TestWorkspaceRootsNormalization:
    def test_list_of_strings(self) -> None:
        cfg = AppConfig.model_validate({"workspace_roots": ["/tmp/a", "/tmp/b"]})
        assert len(cfg.workspace_roots) == 2
        assert cfg.workspace_roots[0].label == "a"
        assert cfg.workspace_roots[1].path == Path("/tmp/b")

    def test_dict_format(self) -> None:
        cfg = AppConfig.model_validate(
            {"workspace_roots": {"Work": "/tmp/work", "Personal": "/tmp/personal"}}
        )
        labels = {r.label for r in cfg.workspace_roots}
        assert labels == {"Work", "Personal"}

    def test_list_of_objects(self) -> None:
        cfg = AppConfig.model_validate({"workspace_roots": [{"label": "OSS", "path": "/tmp/oss"}]})
        assert cfg.workspace_roots[0].label == "OSS"

    def test_label_auto_derived_from_path(self) -> None:
        cfg = AppConfig.model_validate({"workspace_roots": [{"path": "/tmp/myrepos"}]})
        assert cfg.workspace_roots[0].label == "myrepos"

    def test_tilde_expansion(self) -> None:
        cfg = AppConfig.model_validate({"workspace_roots": ["~/projects"]})
        assert "~" not in str(cfg.workspace_roots[0].path)

    def test_dict_tilde_expansion(self) -> None:
        cfg = AppConfig.model_validate({"workspace_roots": {"Home": "~/stuff"}})
        assert "~" not in str(cfg.workspace_roots[0].path)


# ---------------------------------------------------------------------------
# AppConfig.load from file
# ---------------------------------------------------------------------------


class TestAppConfigLoad:
    def test_load_from_file(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "workspace_roots": [str(tmp_path)],
                    "auto_attach": True,
                    "ignore_worktree_dirs": [".bare", "archive"],
                    "main_branch_names": ["develop"],
                    "work_dir_expansion": "folded",
                    "theme": "dark",
                    "header_visualization": "static",
                }
            ),
            encoding="utf-8",
        )
        cfg = AppConfig.load(cfg_path)
        assert cfg.auto_attach is True
        assert "archive" in cfg.ignore_worktree_dirs
        assert "develop" in cfg.main_branch_names
        assert cfg.work_dir_expansion == "folded"
        assert cfg.theme == "dark"
        assert cfg.header_visualization == "static"
        assert len(cfg.workspace_roots) == 1

    def test_invalid_work_dir_expansion_rejected(self) -> None:
        with pytest.raises(ValueError):
            AppConfig.model_validate({"work_dir_expansion": "invalid"})

    def test_invalid_theme_falls_back(self, recwarn: pytest.WarningsRecorder) -> None:
        cfg = AppConfig.model_validate({"theme": "neon"})
        assert cfg.theme == "gruvbox"
        assert any("Invalid 'theme'" in str(w.message) for w in recwarn)

    def test_invalid_header_visualization_falls_back(
        self, recwarn: pytest.WarningsRecorder
    ) -> None:
        cfg = AppConfig.model_validate({"header_visualization": "fractal"})
        assert cfg.header_visualization == "gradient"
        assert any("Invalid 'header_visualization'" in str(w.message) for w in recwarn)

    def test_custom_theme_requires_valid_tokens(self, recwarn: pytest.WarningsRecorder) -> None:
        cfg = AppConfig.model_validate({"theme": "custom"})
        assert cfg.theme == "gruvbox"
        assert cfg.custom_theme is None
        assert any("Theme is set to 'custom'" in str(w.message) for w in recwarn)

    def test_load_preserves_tmuxp_config_dir(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(
            json.dumps({"tmuxp_config_dir": "/custom/tmuxp"}),
            encoding="utf-8",
        )
        cfg = AppConfig.load(cfg_path)
        assert cfg.tmuxp_config_dir == Path("/custom/tmuxp")
