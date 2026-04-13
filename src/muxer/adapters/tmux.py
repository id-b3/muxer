"""Adapter for interacting with tmux and tmuxp."""

import json
from pathlib import Path
from typing import Any

import libtmux
import yaml
from tmuxp.workspace.builder import WorkspaceBuilder
from tmuxp.workspace.freezer import freeze as tmuxp_freeze
from tmuxp.workspace.loader import expand, trickle

from muxer.config import TmuxTemplate


class TmuxManager:
    """Manages tmux sessions and launches tmuxp templates."""

    def __init__(self) -> None:
        """Initializes the connection to the local tmux server."""
        self.server = libtmux.Server()

    def get_active_sessions(self) -> list[libtmux.Session]:
        """Retrieves all currently running tmux sessions.

        Returns:
            A list of active libtmux Session objects.
        """
        return self.server.sessions

    def kill_session(self, session_name: str) -> None:
        """Kills a running tmux session by name.

        Args:
            session_name: The exact tmux session name to kill.

        Raises:
            ValueError: If the session does not exist.
        """
        session = self.server.sessions.get(
            lambda candidate: candidate.name == session_name, default=None
        )
        if session is None:
            raise ValueError(f"Session {session_name!r} not found.")

        session.kill()

    def freeze_session(self, session_name: str) -> dict[str, Any]:
        """Freezes a running tmux session into a tmuxp-compatible config dict.

        Args:
            session_name: The name of the tmux session to snapshot.

        Returns:
            A dictionary representing the tmuxp workspace configuration.

        Raises:
            ValueError: If the session does not exist.
        """
        session = self.server.sessions.get(
            lambda candidate: candidate.name == session_name, default=None
        )
        if session is None:
            raise ValueError(f"Session {session_name!r} not found.")

        return tmuxp_freeze(session)

    def get_templates(self, config_dir: Path) -> list[TmuxTemplate]:
        """Scans a directory for valid tmuxp templates.

        Args:
            config_dir: The directory containing YAML or JSON tmuxp files.

        Returns:
            A list of discovered TmuxTemplate objects.
        """
        if not config_dir.exists() or not config_dir.is_dir():
            return []

        templates = []
        for file in config_dir.iterdir():
            if file.suffix in (".yaml", ".yml", ".json"):
                templates.append(
                    TmuxTemplate(
                        path=file,
                        name=file.stem,
                    )
                )
        return sorted(templates, key=lambda t: t.name)

    def launch_template(
        self, template: TmuxTemplate, session_name: str, start_directory: Path
    ) -> None:
        """Launches a tmuxp template with dynamic overrides.

        Args:
            template: The TmuxTemplate object to load.
            session_name: The target name for the new tmux session.
            start_directory: The root directory for the workspace (e.g., a worktree path).

        Raises:
            ValueError: If the template format is unsupported.
        """
        raw_config = self._read_config(template.path)

        raw_config["session_name"] = session_name
        fallback_directory = str(start_directory)
        raw_config["start_directory"] = fallback_directory
        self._apply_start_directory_defaults(raw_config, fallback_directory)

        expanded_config = expand(raw_config, cwd=template.path.parent)
        builder = WorkspaceBuilder(session_config=trickle(expanded_config), server=self.server)
        builder.build()

    def _apply_start_directory_defaults(
        self, config: dict[str, Any], fallback_directory: str
    ) -> None:
        """Fill missing window/pane start_directory values with the selected worktree path.

        Explicit start_directory values in templates are preserved.
        """
        windows = config.get("windows")
        if not isinstance(windows, list):
            return

        for window in windows:
            if not isinstance(window, dict):
                continue

            window_has_explicit_directory = "start_directory" in window
            if not window_has_explicit_directory:
                window["start_directory"] = fallback_directory

            panes = window.get("panes")
            if not isinstance(panes, list) or window_has_explicit_directory:
                continue

            for pane in panes:
                if isinstance(pane, dict) and "start_directory" not in pane:
                    pane["start_directory"] = fallback_directory

    def _read_config(self, filepath: Path) -> dict[str, Any]:
        """Reads a YAML or JSON file into a dictionary.

        Args:
            filepath: Path to the configuration file.

        Returns:
            The parsed dictionary configuration.
        """
        content = filepath.read_text(encoding="utf-8")

        if filepath.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content)
        if filepath.suffix == ".json":
            return json.loads(content)

        raise ValueError(f"Unsupported template format: {filepath.suffix}")
