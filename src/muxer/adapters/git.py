"""Adapter for interacting with Git worktrees."""

import subprocess
from pathlib import Path

from muxer.config import Worktree


class GitManager:
    """Manages Git worktree operations via the git CLI."""

    def _run_git_text(self, repo_path: Path, args: list[str]) -> str | None:
        """Run a git command and return stripped stdout, or None on failure."""
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), *args],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None
        return result.stdout.strip()

    @staticmethod
    def _clean_branch_name(branch: str) -> str:
        """Normalize common git ref formats to a short branch name."""
        normalized = branch.strip()
        normalized = normalized.removeprefix("refs/heads/")
        normalized = normalized.removeprefix("refs/remotes/")
        if "/" in normalized:
            remote, remainder = normalized.split("/", 1)
            if remote and remainder:
                return remainder
        return normalized

    def get_default_branch(self, repo_path: Path) -> str | None:
        """Detects the default branch for a repository.

        Args:
            repo_path: The root path of the Git repository.

        Returns:
            The branch name (e.g. "main") or None if it cannot be determined.
        """
        candidates = [
            # Most accurate when remote HEAD is configured.
            ["symbolic-ref", "refs/remotes/origin/HEAD"],
            # Fallback for repositories where the remote head ref is absent.
            ["symbolic-ref", "--short", "HEAD"],
            ["rev-parse", "--abbrev-ref", "HEAD"],
        ]

        for args in candidates:
            raw = self._run_git_text(repo_path, args)
            if not raw or raw == "HEAD":
                continue
            branch = self._clean_branch_name(raw)
            if branch and branch != "HEAD":
                return branch

        return None

    def is_git_repository(self, path: Path) -> bool:
        """Determines if a given path is a Git repository.

        Args:
            path: The directory path to check.

        Returns:
            True if the directory contains a .git folder or file, False otherwise.
        """
        git_dir = path / ".git"
        return git_dir.exists()

    def get_worktrees(self, repo_path: Path) -> list[Worktree]:
        """Retrieves all worktrees for a given repository.

        Args:
            repo_path: The root path of the Git repository.

        Returns:
            A list of Worktree objects associated with the repository.
        """
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return []

        return self._parse_worktree_porcelain(result.stdout)

    def add_worktree(self, repo_path: Path, new_path: Path, branch: str) -> None:
        """Creates a new Git worktree.

        Args:
            repo_path: The root path of the base Git repository.
            new_path: The target directory for the new worktree.
            branch: The branch to checkout or create.
        """
        subprocess.run(
            ["git", "-C", str(repo_path), "worktree", "add", "-b", branch, str(new_path)],
            check=True,
        )

    def _parse_worktree_porcelain(self, output: str) -> list[Worktree]:
        """Parses the output of 'git worktree list --porcelain'.

        Args:
            output: The raw stdout from the git command.

        Returns:
            A list of parsed Worktree objects.
        """
        worktrees = []
        current_data: dict[str, str] = {}

        for line in output.splitlines():
            line = line.strip()

            if not line:
                if current_data:
                    worktrees.append(
                        Worktree(
                            path=Path(current_data["worktree"]),
                            head=current_data.get("HEAD", ""),
                            branch=current_data.get("branch"),
                        )
                    )
                    current_data = {}
                continue

            parts = line.split(" ", 1)
            if len(parts) == 2:
                key, value = parts
                current_data[key] = value

        if current_data:
            worktrees.append(
                Worktree(
                    path=Path(current_data["worktree"]),
                    head=current_data.get("HEAD", ""),
                    branch=current_data.get("branch"),
                )
            )

        return worktrees
