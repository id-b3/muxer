"""Application configuration and core domain models."""

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_VALID_THEMES = {"light", "dark", "gruvbox", "custom"}
_VALID_HEADER_VISUALIZATIONS = {"static", "gradient", "game_of_life"}


@dataclass(frozen=True, kw_only=True)
class WorkspaceRoot:
    """A labeled directory root to scan for Git repositories.

    Attributes:
        path: Absolute path to the workspace directory.
        label: Human-readable label for grouping in the UI.
    """

    path: Path
    label: str


@dataclass(frozen=True, kw_only=True)
class Worktree:
    """Represents a Git worktree.

    Attributes:
        path: Absolute path to the worktree directory.
        head: The commit hash of the worktree's HEAD.
        branch: The branch name checked out in the worktree, or None if detached.
    """

    path: Path
    head: str
    branch: str | None


@dataclass(frozen=True, kw_only=True)
class TmuxTemplate:
    """Represents a discovered tmuxp template.

    Attributes:
        path: Absolute path to the configuration file.
        name: The identifier of the template (typically the filename without extension).
    """

    path: Path
    name: str


class AppConfig(BaseModel):
    """Global application settings for muxer.

    Attributes:
        workspace_roots: Labeled directories to scan for Git repositories.  Accepts a plain
            list of path strings (labels auto-derived from the directory name), a
            ``{label: path}`` mapping, or a list of ``{label, path}`` objects.
        tmuxp_config_dir: Directory containing tmuxp templates.
        auto_attach: Whether to attach to a newly launched tmux session automatically.
        ignore_worktree_dirs: Directory names to exclude from worktree listings (e.g. [".bare"]).
        main_branch_names: Branch names treated as "main" for colour-coding. Auto-detected
            default branches are merged with this list at runtime.
        work_dir_expansion: Initial expansion behavior for repo/work-dir nodes in the tree.
            ``"top"`` expands only the first work-dir, ``"expanded"`` expands all, and
            ``"folded"`` expands none.
        theme: App colour theme. Supports ``"light"``, ``"dark"``, ``"gruvbox"``, and ``"custom"``.
        header_visualization: Header visualization mode. Supports ``"static"``, ``"gradient"``,
            and ``"game_of_life"``.
        custom_theme: Optional flat token map used when ``theme`` is ``"custom"``.
    """

    workspace_roots: list[WorkspaceRoot] = Field(
        default_factory=lambda: [WorkspaceRoot(path=Path.home() / "dev", label="dev")],
    )
    tmuxp_config_dir: Path = Field(default_factory=lambda: Path.home() / ".config" / "tmuxp")
    auto_attach: bool = Field(default=False)
    ignore_worktree_dirs: list[str] = Field(default_factory=lambda: [".bare"])
    main_branch_names: list[str] = Field(default_factory=lambda: ["main", "master"])
    work_dir_expansion: Literal["top", "expanded", "folded"] = Field(default="top")
    theme: Literal["light", "dark", "gruvbox", "custom"] = Field(default="gruvbox")
    header_visualization: Literal["static", "gradient", "game_of_life"] = Field(default="gradient")
    custom_theme: dict[str, str] | None = Field(default=None)

    @field_validator("workspace_roots", mode="before")
    @classmethod
    def _normalize_roots(cls, v: Any) -> list[dict[str, Any]]:
        """Accept list-of-strings, label→path dict, or list-of-objects."""
        if isinstance(v, dict):
            # {"Work": "~/work", "Personal": "~/personal"}
            return [{"path": str(Path(p).expanduser()), "label": lbl} for lbl, p in v.items()]
        if isinstance(v, list):
            out: list[dict[str, Any]] = []
            for item in v:
                if isinstance(item, str | Path):
                    p = Path(item).expanduser()
                    out.append({"path": str(p), "label": p.name})
                elif isinstance(item, dict):
                    d = dict(item)
                    if "path" in d:
                        d["path"] = str(Path(d["path"]).expanduser())
                    if "label" not in d:
                        d["label"] = Path(d["path"]).name
                    out.append(d)
                else:
                    out.append(item)
            return out
        return v

    @field_validator("theme", mode="before")
    @classmethod
    def _normalize_theme(cls, value: Any) -> str:
        if not isinstance(value, str):
            warnings.warn("Invalid 'theme' in config; falling back to 'gruvbox'.", stacklevel=2)
            return "gruvbox"
        normalized = value.strip().lower()
        if normalized not in _VALID_THEMES:
            warnings.warn("Invalid 'theme' in config; falling back to 'gruvbox'.", stacklevel=2)
            return "gruvbox"
        return normalized

    @field_validator("header_visualization", mode="before")
    @classmethod
    def _normalize_header_visualization(cls, value: Any) -> str:
        if not isinstance(value, str):
            warnings.warn(
                "Invalid 'header_visualization' in config; falling back to 'gradient'.",
                stacklevel=2,
            )
            return "gradient"
        normalized = value.strip().lower()
        if normalized not in _VALID_HEADER_VISUALIZATIONS:
            warnings.warn(
                "Invalid 'header_visualization' in config; falling back to 'gradient'.",
                stacklevel=2,
            )
            return "gradient"
        return normalized

    @field_validator("custom_theme", mode="before")
    @classmethod
    def _normalize_custom_theme(cls, value: Any) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            warnings.warn(
                "Invalid 'custom_theme' in config; ignoring custom theme tokens.",
                stacklevel=2,
            )
            return None

        normalized: dict[str, str] = {}
        for key, raw in value.items():
            if not isinstance(key, str) or not isinstance(raw, str):
                continue
            token = key.strip()
            color = raw.strip()
            if token and color:
                normalized[token] = color

        if not normalized:
            warnings.warn(
                "Invalid 'custom_theme' in config; ignoring custom theme tokens.",
                stacklevel=2,
            )
            return None
        return normalized

    @model_validator(mode="after")
    def _normalize_custom_theme_selection(self) -> "AppConfig":
        if self.theme == "custom" and not self.custom_theme:
            warnings.warn(
                "Theme is set to 'custom' but no valid 'custom_theme' provided; "
                "falling back to 'gruvbox'.",
                stacklevel=2,
            )
            self.theme = "gruvbox"
        return self

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        """Loads the application configuration from a file.

        Args:
            config_path: Path to the JSON config file. Defaults to ~/.config/muxer/config.json.

        Returns:
            An instantiated AppConfig model.
        """
        path = config_path or Path.home() / ".config" / "muxer" / "config.json"

        if not path.exists():
            return cls()

        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)
