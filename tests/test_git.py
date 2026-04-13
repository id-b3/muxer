"""Tests for muxer.adapters.git - GitManager."""

from __future__ import annotations

import subprocess
from pathlib import Path

from muxer.adapters.git import GitManager


class TestIsGitRepository:
    def test_true_for_repo(self, tmp_git_repo: Path) -> None:
        gm = GitManager()
        assert gm.is_git_repository(tmp_git_repo) is True

    def test_false_for_plain_dir(self, tmp_path: Path) -> None:
        gm = GitManager()
        assert gm.is_git_repository(tmp_path) is False


class TestGetWorktrees:
    def test_single_worktree(self, tmp_git_repo: Path) -> None:
        gm = GitManager()
        worktrees = gm.get_worktrees(tmp_git_repo)
        assert len(worktrees) == 1
        assert worktrees[0].path == tmp_git_repo
        assert worktrees[0].branch is not None

    def test_multiple_worktrees(self, tmp_git_repo_with_worktrees: Path) -> None:
        gm = GitManager()
        worktrees = gm.get_worktrees(tmp_git_repo_with_worktrees)
        assert len(worktrees) == 3  # main + feature-a + feature-b
        branches = {wt.branch.removeprefix("refs/heads/") for wt in worktrees if wt.branch}
        assert "feature-a" in branches
        assert "feature-b" in branches

    def test_returns_empty_for_nonexistent(self, tmp_path: Path) -> None:
        gm = GitManager()
        assert gm.get_worktrees(tmp_path / "nope") == []


class TestParseWorktreePorcelain:
    def test_basic_parse(self) -> None:
        output = "worktree /home/user/project\nHEAD abc1234567890\nbranch refs/heads/main\n\n"
        gm = GitManager()
        result = gm._parse_worktree_porcelain(output)
        assert len(result) == 1
        assert result[0].path == Path("/home/user/project")
        assert result[0].head == "abc1234567890"
        assert result[0].branch == "refs/heads/main"

    def test_multiple_entries(self) -> None:
        output = (
            "worktree /a\nHEAD aaa\nbranch refs/heads/main\n\n"
            "worktree /b\nHEAD bbb\nbranch refs/heads/dev\n\n"
        )
        gm = GitManager()
        result = gm._parse_worktree_porcelain(output)
        assert len(result) == 2
        assert result[0].path == Path("/a")
        assert result[1].branch == "refs/heads/dev"

    def test_detached_head(self) -> None:
        output = "worktree /detached\nHEAD abc123\ndetached\n\n"
        gm = GitManager()
        result = gm._parse_worktree_porcelain(output)
        assert len(result) == 1
        assert result[0].branch is None

    def test_no_trailing_newline(self) -> None:
        output = "worktree /a\nHEAD aaa\nbranch refs/heads/main"
        gm = GitManager()
        result = gm._parse_worktree_porcelain(output)
        assert len(result) == 1

    def test_empty_output(self) -> None:
        gm = GitManager()
        assert gm._parse_worktree_porcelain("") == []


class TestGetDefaultBranch:
    def test_returns_local_head_without_remote(self, tmp_git_repo: Path) -> None:
        gm = GitManager()
        assert gm.get_default_branch(tmp_git_repo) in {"main", "master"}

    def test_returns_branch_when_set(self, tmp_git_repo: Path) -> None:
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_git_repo),
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/develop",
            ],
            capture_output=True,
            check=True,
        )
        gm = GitManager()
        assert gm.get_default_branch(tmp_git_repo) == "develop"

    def test_returns_none_for_nonexistent_dir(self, tmp_path: Path) -> None:
        gm = GitManager()
        assert gm.get_default_branch(tmp_path / "nope") is None

    def test_normalizes_remote_prefixed_short_ref(self) -> None:
        gm = GitManager()
        assert gm._clean_branch_name("origin/develop") == "develop"
