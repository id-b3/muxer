"""Shared fixtures for the muxer test suite."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from muxer.config import AppConfig


@pytest.fixture()
def tmp_git_repo(tmp_path: Path) -> Path:
    """Create a minimal Git repository with an initial commit.

    Returns the repository root path.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
        check=True,
    )
    return repo


@pytest.fixture()
def tmp_git_repo_with_worktrees(tmp_git_repo: Path) -> Path:
    """Git repository with two extra worktrees: ``feature-a`` and ``feature-b``.

    Returns the main repository root path.
    """
    for branch in ("feature-a", "feature-b"):
        wt_path = tmp_git_repo.parent / branch
        subprocess.run(
            ["git", "-C", str(tmp_git_repo), "worktree", "add", "-b", branch, str(wt_path)],
            capture_output=True,
            check=True,
        )
    return tmp_git_repo


@pytest.fixture()
def tmp_workspace_root(tmp_path: Path, tmp_git_repo_with_worktrees: Path) -> Path:
    """A workspace root directory containing one git repo (with worktrees).

    The layout is ``<tmp_path>/workspace/repo`` where ``repo`` is a symlink
    (or copy) of the prepared git repo.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / tmp_git_repo_with_worktrees.name
    target.symlink_to(tmp_git_repo_with_worktrees)
    return workspace


@pytest.fixture()
def tmp_tmuxp_config_dir(tmp_path: Path) -> Path:
    """A temporary directory containing sample tmuxp templates."""
    config_dir = tmp_path / "tmuxp"
    config_dir.mkdir()

    yaml_template: dict[str, Any] = {
        "session_name": "{{session_name}}",
        "start_directory": "{{start_directory}}",
        "windows": [
            {
                "window_name": "editor",
                "panes": [{"shell_command": ["echo hello"]}],
            },
        ],
    }
    (config_dir / "dev.yaml").write_text(yaml.dump(yaml_template), encoding="utf-8")
    (config_dir / "ops.yml").write_text(yaml.dump(yaml_template), encoding="utf-8")
    (config_dir / "ci.json").write_text(json.dumps(yaml_template), encoding="utf-8")
    # Non-template file — should be ignored
    (config_dir / "notes.txt").write_text("not a template", encoding="utf-8")
    return config_dir


@pytest.fixture()
def tmp_app_config(
    tmp_workspace_root: Path,
    tmp_tmuxp_config_dir: Path,
    tmp_path: Path,
) -> Path:
    """Write a muxer config.json file and return its path."""
    cfg_path = tmp_path / "muxer_config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "workspace_roots": [str(tmp_workspace_root)],
                "tmuxp_config_dir": str(tmp_tmuxp_config_dir),
                "auto_attach": False,
                "ignore_worktree_dirs": [".bare"],
                "main_branch_names": ["main", "master"],
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


@pytest.fixture()
def app_config(tmp_app_config: Path) -> AppConfig:
    """An ``AppConfig`` loaded from the temporary config file."""
    return AppConfig.load(tmp_app_config)
