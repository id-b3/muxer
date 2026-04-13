"""The main Textual application for muxer."""

import os
import random
import subprocess
import warnings
import webbrowser
from pathlib import Path
from time import time
from typing import ClassVar

import yaml
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.events import DescendantFocus
from textual.message import Message
from textual.renderables.gradient import LinearGradient
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, OptionList, Static, Tree
from textual.widgets.option_list import Option

from muxer.adapters.git import GitManager
from muxer.adapters.tmux import TmuxManager
from muxer.config import AppConfig, TmuxTemplate, Worktree

_TEMPLATE_SCAFFOLD = """\
session_name: "{{session_name}}"
start_directory: "{{start_directory}}"
windows:
  - window_name: editor
    focus: true
    panes:
      - shell_command:
          - echo "Hello from {{session_name}}"
  - window_name: terminal
    panes:
      - ""
"""

_TMUXP_EXAMPLES_URL = "https://tmuxp.git-pull.com/configuration/examples/#examples"

_BANNER = "[bold]⚡  MUXER  ⚡[/]\n[bold]tmux workspace manager[/]"
_THEME_TOKENS: dict[str, dict[str, str]] = {
    "gruvbox": {
        "screen_bg": "#282828",
        "screen_fg": "#ebdbb2",
        "path_bg": "#3c3836",
        "path_fg": "#a89984",
        "column_bg": "#32302f",
        "column_title_fg": "#d5c4a1",
        "column_border": "#689d6a",
        "column_focus_border": "#8ec07c",
        "column_focus_bg": "#3c3836",
        "list_bg": "#32302f",
        "list_fg": "#ebdbb2",
        "tree_bg": "#32302f",
        "tree_fg": "#ebdbb2",
        "footer_bg": "#3c3836",
        "footer_fg": "#a89984",
        "confirm_panel_bg": "#282828",
        "confirm_panel_border": "#d79921",
        "confirm_title_fg": "#fabd2f",
        "confirm_message_fg": "#ebdbb2",
        "header_text_fg": "#fbf1c7",
        "header_static_bg": "#3c3836",
        "selection_bg": "#458588",
        "selection_fg": "#fbf1c7",
        "selection_blur_bg": "#504945",
        "selection_blur_fg": "#ebdbb2",
        "footer_key_bg": "#689d6a",
        "footer_key_fg": "#1d2021",
        "footer_desc_bg": "#3c3836",
        "footer_desc_fg": "#ebdbb2",
        "footer_hover_bg": "#7c6f64",
        "footer_hover_fg": "#fbf1c7",
    },
    "dark": {
        "screen_bg": "#111827",
        "screen_fg": "#e5e7eb",
        "path_bg": "#1f2937",
        "path_fg": "#93c5fd",
        "column_bg": "#111827",
        "column_title_fg": "#f9fafb",
        "column_border": "#4b5563",
        "column_focus_border": "#60a5fa",
        "column_focus_bg": "#1f2937",
        "list_bg": "#111827",
        "list_fg": "#e5e7eb",
        "tree_bg": "#111827",
        "tree_fg": "#e5e7eb",
        "footer_bg": "#1f2937",
        "footer_fg": "#9ca3af",
        "confirm_panel_bg": "#111827",
        "confirm_panel_border": "#60a5fa",
        "confirm_title_fg": "#bfdbfe",
        "confirm_message_fg": "#e5e7eb",
        "header_text_fg": "#f9fafb",
        "header_static_bg": "#1f2937",
        "selection_bg": "#2563eb",
        "selection_fg": "#f9fafb",
        "selection_blur_bg": "#374151",
        "selection_blur_fg": "#f3f4f6",
        "footer_key_bg": "#3b82f6",
        "footer_key_fg": "#f9fafb",
        "footer_desc_bg": "#1f2937",
        "footer_desc_fg": "#d1d5db",
        "footer_hover_bg": "#1d4ed8",
        "footer_hover_fg": "#f9fafb",
    },
    "light": {
        "screen_bg": "#f9fafb",
        "screen_fg": "#111827",
        "path_bg": "#e5e7eb",
        "path_fg": "#1f2937",
        "column_bg": "#ffffff",
        "column_title_fg": "#111827",
        "column_border": "#9ca3af",
        "column_focus_border": "#2563eb",
        "column_focus_bg": "#eff6ff",
        "list_bg": "#ffffff",
        "list_fg": "#111827",
        "tree_bg": "#ffffff",
        "tree_fg": "#111827",
        "footer_bg": "#e5e7eb",
        "footer_fg": "#374151",
        "confirm_panel_bg": "#ffffff",
        "confirm_panel_border": "#6b7280",
        "confirm_title_fg": "#111827",
        "confirm_message_fg": "#1f2937",
        "header_text_fg": "#111827",
        "header_static_bg": "#d1d5db",
        "selection_bg": "#2563eb",
        "selection_fg": "#ffffff",
        "selection_blur_bg": "#93c5fd",
        "selection_blur_fg": "#0f172a",
        "footer_key_bg": "#1d4ed8",
        "footer_key_fg": "#ffffff",
        "footer_desc_bg": "#cbd5e1",
        "footer_desc_fg": "#0f172a",
        "footer_hover_bg": "#1e40af",
        "footer_hover_fg": "#ffffff",
    },
}
_CUSTOM_THEME_ALLOWED_KEYS = frozenset(_THEME_TOKENS["gruvbox"])


class SplashHeader(Container):
    """Configurable animated header with centered app title."""

    DEFAULT_CSS = """
    SplashHeader {
        dock: top;
        width: 100%;
        height: 4;
        align: center middle;
    }

    SplashHeader > Static {
        width: auto;
        height: auto;
        content-align: center middle;
        text-align: center;
        padding: 0 2;
        color: #fbf1c7;
        text-style: bold;
        background: transparent;
    }
    """

    def __init__(
        self,
        mode: str,
        colors: list[str],
        static_color: str,
        text_color: str,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._mode = mode
        self._colors = colors
        self._static_color = static_color
        self._text_color = text_color
        # Intentionally unseeded so each app start gets a different life pattern.
        self._rng = random.Random()
        self._life_grid = [[self._rng.random() > 0.6 for _ in range(32)] for _ in range(4)]

    @staticmethod
    def _refresh_interval(mode: str) -> float | None:
        if mode == "static":
            return None
        if mode == "game_of_life":
            return 1 / 8
        return 1 / 30

    def on_mount(self) -> None:
        self.query_one(Static).styles.color = self._text_color
        self.auto_refresh = self._refresh_interval(self._mode)

    def compose(self) -> ComposeResult:
        yield Static(_BANNER)

    @staticmethod
    def _hex_to_rgb(color: str) -> tuple[int, int, int]:
        value = color.lstrip("#")
        if len(value) != 6:
            return (60, 56, 54)
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))

    @staticmethod
    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        r, g, b = rgb
        return f"#{r:02x}{g:02x}{b:02x}"

    @classmethod
    def _mix_hex(cls, low: str, high: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        lr, lg, lb = cls._hex_to_rgb(low)
        hr, hg, hb = cls._hex_to_rgb(high)
        return cls._rgb_to_hex(
            (
                int(lr + (hr - lr) * ratio),
                int(lg + (hg - lg) * ratio),
                int(lb + (hb - lb) * ratio),
            )
        )

    def _step_life(self) -> None:
        height = len(self._life_grid)
        width = len(self._life_grid[0])
        next_grid: list[list[bool]] = []
        for y in range(height):
            row: list[bool] = []
            for x in range(width):
                neighbors = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        if self._life_grid[(y + dy) % height][(x + dx) % width]:
                            neighbors += 1
                alive = self._life_grid[y][x]
                row.append(neighbors in (2, 3) if alive else neighbors == 3)
            next_grid.append(row)
        self._life_grid = next_grid

    def _life_stops(self) -> list[tuple[float, str]]:
        if not self._colors:
            return [(0.0, self._static_color), (1.0, self._static_color)]

        if len(self._colors) == 1:
            return [(0.0, self._colors[0]), (1.0, self._colors[0])]

        width = len(self._life_grid[0])
        max_alive_per_column = len(self._life_grid)
        stops: list[tuple[float, str]] = []
        for x in range(width):
            alive_count = 0
            for y in range(len(self._life_grid)):
                if self._life_grid[y][x]:
                    alive_count += 1
            ratio = alive_count / max_alive_per_column
            color_index = round(ratio * (len(self._colors) - 1))
            stops.append((x / max(1, width - 1), self._colors[color_index]))
        return stops

    def render(self) -> LinearGradient:
        if self._mode == "static":
            return LinearGradient(0, [(0.0, self._static_color), (1.0, self._static_color)])

        if self._mode == "game_of_life":
            self._step_life()
            return LinearGradient(0, self._life_stops())

        if not self._colors:
            return LinearGradient(0, [(0.0, self._static_color), (1.0, self._static_color)])
        if len(self._colors) == 1:
            return LinearGradient(0, [(0.0, self._colors[0]), (1.0, self._colors[0])])

        color_stops = [
            (index / (len(self._colors) - 1), color) for index, color in enumerate(self._colors)
        ]
        return LinearGradient(time() * 90, color_stops)


class WorkspaceLaunched(Message):
    """Message fired when a background worker creates a tmux session."""

    def __init__(self, session_name: str) -> None:
        super().__init__()
        self.session_name = session_name


class ConfirmDialog(ModalScreen[bool]):
    """A small yes/no modal used for destructive actions."""

    CSS = ""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape,n", "cancel", "Cancel", show=False),
        Binding("enter,y", "confirm", "Confirm", show=False),
    ]

    @staticmethod
    def _build_css(tokens: dict[str, str]) -> str:
        return f"""
    ConfirmDialog {{
        align: center middle;
    }}

    .confirm-panel {{
        width: 64;
        max-width: 90%;
        padding: 1 2;
        border: round {tokens["confirm_panel_border"]};
        background: {tokens["confirm_panel_bg"]};
    }}

    .confirm-title {{
        text-align: center;
        text-style: bold;
        color: {tokens["confirm_title_fg"]};
        margin-bottom: 1;
    }}

    .confirm-message {{
        color: {tokens["confirm_message_fg"]};
        margin-bottom: 1;
    }}

    .confirm-actions {{
        align-horizontal: center;
        height: auto;
    }}

    .confirm-actions Button {{
        margin: 0 1;
    }}
    """

    def __init__(self, title: str, message: str, theme_tokens: dict[str, str]) -> None:
        super().__init__()
        self._title = title
        self._message = message
        self.CSS = self._build_css(theme_tokens)

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-panel"):
            yield Label(self._title, classes="confirm-title")
            yield Static(self._message, classes="confirm-message")
            with Horizontal(classes="confirm-actions"):
                yield Button("Cancel", id="cancel")
                yield Button("Confirm", id="confirm", variant="error")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
            return
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)


class MuxerApp(App):
    """The main Textual application for managing tmux workspaces."""

    CSS = ""
    ENABLE_COMMAND_PALETTE = False

    @staticmethod
    def _build_css(tokens: dict[str, str]) -> str:
        return f"""
    Screen {{
        layout: vertical;
        background: {tokens["screen_bg"]};
        color: {tokens["screen_fg"]};
    }}

    #path-display {{
        width: 100%;
        height: 1;
        content-align: center middle;
        background: {tokens["path_bg"]};
        color: {tokens["path_fg"]};
    }}

    Horizontal {{
        height: 1fr;
    }}

    .column {{
        width: 1fr;
        height: 100%;
        border: solid {tokens["column_border"]};
        margin: 1 1;
        padding: 1;
        background: {tokens["column_bg"]};
    }}

    .column:focus-within {{
        border: solid {tokens["column_focus_border"]};
        background: {tokens["column_focus_bg"]};
    }}

    .column-title {{
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 1;
        color: {tokens["column_title_fg"]};
    }}

    OptionList {{
        border: none;
        height: 1fr;
        background: {tokens["list_bg"]};
        color: {tokens["list_fg"]};
    }}

    OptionList > .option-list--option-highlighted {{
        color: {tokens["selection_blur_fg"]};
        background: {tokens["selection_blur_bg"]};
    }}

    OptionList:focus > .option-list--option-highlighted {{
        color: {tokens["selection_fg"]};
        background: {tokens["selection_bg"]};
        text-style: bold;
    }}

    Tree {{
        border: none;
        height: 1fr;
        background: {tokens["tree_bg"]};
        color: {tokens["tree_fg"]};
    }}

    Tree > .tree--cursor {{
        color: {tokens["selection_blur_fg"]};
        background: {tokens["selection_blur_bg"]};
    }}

    Tree:focus > .tree--cursor {{
        color: {tokens["selection_fg"]};
        background: {tokens["selection_bg"]};
        text-style: bold;
    }}

    Footer {{
        background: {tokens["footer_bg"]};
        color: {tokens["footer_fg"]};
    }}

    Footer .footer-key--key {{
        background: {tokens["footer_key_bg"]};
        color: {tokens["footer_key_fg"]};
        text-style: bold;
    }}

    Footer .footer-key--description {{
        background: {tokens["footer_desc_bg"]};
        color: {tokens["footer_desc_fg"]};
    }}

    Footer FooterKey:hover {{
        background: {tokens["footer_hover_bg"]};
        color: {tokens["footer_hover_fg"]};
    }}

    Footer FooterKey:hover .footer-key--key {{
        background: {tokens["footer_hover_bg"]};
        color: {tokens["footer_hover_fg"]};
    }}

    Footer FooterKey:hover .footer-key--description {{
        background: {tokens["footer_desc_bg"]};
        color: {tokens["footer_desc_fg"]};
    }}

    #worktree-column {{
        width: 2fr;
    }}
    """

    @staticmethod
    def _resolve_theme_tokens(theme: str, custom_theme: dict[str, str] | None) -> dict[str, str]:
        if theme == "custom":
            tokens = dict(_THEME_TOKENS["gruvbox"])
            if not custom_theme:
                return tokens
            for token, color in custom_theme.items():
                if token in _CUSTOM_THEME_ALLOWED_KEYS:
                    tokens[token] = color
                else:
                    warnings.warn(
                        f"Unknown custom_theme token '{token}' ignored.",
                        stacklevel=2,
                    )
            return tokens
        return dict(_THEME_TOKENS.get(theme, _THEME_TOKENS["gruvbox"]))

    @staticmethod
    def _header_palette(tokens: dict[str, str]) -> list[str]:
        candidate_keys = (
            "screen_bg",
            "path_bg",
            "column_bg",
            "column_border",
            "footer_bg",
            "confirm_panel_border",
            "header_static_bg",
        )
        palette: list[str] = []
        seen: set[str] = set()
        for key in candidate_keys:
            color = tokens.get(key)
            if color and color not in seen:
                palette.append(color)
                seen.add(color)
        if not palette:
            return ["#3c3836"]
        return palette

    # --- Bindings ---------------------------------------------------------
    # Global bindings are always visible.
    # Contextual bindings are shown/hidden via check_action() based on focus.
    _SESSION_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {
            "attach_session",
            "kill_session",
            "freeze_session",
        }
    )
    _TEMPLATE_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {
            "new_template",
            "edit_template",
            "open_examples",
        }
    )

    BINDINGS: ClassVar[list[Binding]] = [
        # Global
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh_data", "Refresh", priority=True),
        Binding("l", "launch_workspace", "Launch", priority=True),
        Binding("c", "open_config", "Config", priority=True),
        Binding("tab", "focus_next", "Next Pane", show=False),
        Binding("shift+tab", "focus_previous", "Prev Pane", show=False),
        # Sessions pane
        Binding("a", "attach_session", "Attach", priority=True),
        Binding("x", "kill_session", "Kill", priority=True),
        Binding("f", "freeze_session", "Freeze", priority=True),
        # Templates pane
        Binding("n", "new_template", "New Tmpl", priority=True),
        Binding("e", "edit_template", "Edit Tmpl", priority=True),
        Binding("question_mark", "open_examples", "Examples", priority=True, key_display="?"),
    ]

    def __init__(self) -> None:
        """Initializes the application and core managers."""
        super().__init__()
        self.config = AppConfig.load()
        self._theme_tokens = self._resolve_theme_tokens(self.config.theme, self.config.custom_theme)
        self._header_colors = self._header_palette(self._theme_tokens)
        self.CSS = self._build_css(self._theme_tokens)
        self.git_manager = GitManager()
        self.tmux_manager = TmuxManager()

    # --- Layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Builds the UI layout."""
        yield SplashHeader(
            mode=self.config.header_visualization,
            colors=self._header_colors,
            static_color=self._theme_tokens["header_static_bg"],
            text_color=self._theme_tokens["header_text_fg"],
            id="app-banner",
        )
        yield Static("", id="path-display")

        with Horizontal():
            with Vertical(classes="column"):
                yield Label("Active Sessions", classes="column-title")
                yield OptionList(id="active_sessions")

            with Vertical(classes="column", id="worktree-column"):
                yield Label("Git Worktrees", classes="column-title")
                wt_tree = Tree("Worktrees", id="git_worktrees")
                wt_tree.show_root = False
                yield wt_tree

            with Vertical(classes="column"):
                yield Label("Templates", classes="column-title")
                yield OptionList(id="templates")

        yield Footer()

    # --- Lifecycle --------------------------------------------------------

    def on_mount(self) -> None:
        """Triggered when the app is mounted to the terminal. Starts data fetching."""
        self.action_refresh_data()

    def on_descendant_focus(self, _event: DescendantFocus) -> None:
        """Refresh the footer bindings whenever focus moves between widgets."""
        self.refresh_bindings()

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
        """Show/hide contextual bindings based on which pane is focused.

        Returns None to hide a binding from the footer entirely.
        """
        if action in self._SESSION_ACTIONS:
            return True if self._sessions_focused() else None
        if action in self._TEMPLATE_ACTIONS:
            return True if self._templates_focused() else None
        return True

    # --- Helpers ----------------------------------------------------------

    def _sessions_focused(self) -> bool:
        return self.query_one("#active_sessions", OptionList).has_focus

    def _templates_focused(self) -> bool:
        return self.query_one("#templates", OptionList).has_focus

    @staticmethod
    def _repo_node_expanded(expansion_mode: str, repo_index: int) -> bool:
        """Return whether a repo/work-dir node should start expanded."""
        if expansion_mode == "expanded":
            return True
        if expansion_mode == "folded":
            return False
        return repo_index == 0

    def _get_editor(self) -> str:
        return os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"

    @staticmethod
    def _config_path() -> Path:
        return Path.home() / ".config" / "muxer" / "config.json"

    def _get_selected_session_name(self) -> str | None:
        """Returns the selected active session name, or None with a notification."""
        session_list = self.query_one("#active_sessions", OptionList)

        if session_list.highlighted is None:
            self.notify("Select an active session first.", severity="warning")
            return None

        option = session_list.get_option_at_index(session_list.highlighted)
        return str(option.id) if option.id else None

    # --- Global actions ---------------------------------------------------

    def action_refresh_data(self) -> None:
        """Fetches data from adapters in the background and populates the UI."""
        self._load_active_sessions()
        self._load_templates()
        self._load_worktrees()
        self.notify("Refreshing…", timeout=2)

    def action_launch_workspace(self) -> None:
        """Launches a tmux session based on the selected worktree and template."""
        tree = self.query_one("#git_worktrees", Tree)
        template_list = self.query_one("#templates", OptionList)

        node = tree.cursor_node
        if node is None or not isinstance(node.data, Worktree):
            self.notify("Select a worktree (not a repo folder).", severity="warning")
            return

        if template_list.highlighted is None:
            self.notify("Please select a template.", severity="warning")
            return

        template_name = template_list.get_option_at_index(template_list.highlighted).id
        if not template_name:
            return

        worktree = node.data
        worktree_path = worktree.path
        session_name = f"{worktree_path.parent.name}-{worktree_path.name}"

        templates = self.tmux_manager.get_templates(self.config.tmuxp_config_dir)
        selected_template = next((t for t in templates if t.name == template_name), None)

        if not selected_template:
            self.notify(f"Template {template_name} not found.", severity="error")
            return

        self._launch_in_background(selected_template, session_name, worktree_path)

    def action_open_config(self) -> None:
        """Open muxer config in the user's editor, creating it if absent."""
        config_path = self._config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if not config_path.exists():
            config_path.write_text(AppConfig().model_dump_json(indent=2), encoding="utf-8")

        editor = self._get_editor()
        with self.suspend():
            subprocess.run([editor, str(config_path)], check=False)

        self.notify(f"Opened config: {config_path}", timeout=2)

    # --- Sessions pane actions --------------------------------------------

    def attach_to_tmux(self, session_name: str) -> None:
        """Temporarily suspends the UI and attaches to a tmux session."""
        with self.suspend():
            subprocess.run(["tmux", "attach-session", "-t", session_name], check=False)
        self.action_refresh_data()

    def action_attach_session(self) -> None:
        """Attaches to the selected active tmux session."""
        session_name = self._get_selected_session_name()
        if session_name is None:
            return
        self.attach_to_tmux(session_name)

    def action_kill_session(self) -> None:
        """Kills the selected active tmux session."""
        session_name = self._get_selected_session_name()
        if session_name is None:
            return

        self.push_screen(
            ConfirmDialog(
                "Kill tmux session?",
                f"Are you sure you want to kill '{session_name}'? This cannot be undone.",
                self._theme_tokens,
            ),
            callback=lambda confirmed: self._on_kill_session_confirmed(session_name, confirmed),
        )

    def _on_kill_session_confirmed(self, session_name: str, confirmed: bool) -> None:
        """Runs once the kill confirmation modal is dismissed."""
        if not confirmed:
            self.notify("Kill cancelled.", timeout=2)
            return

        try:
            self.tmux_manager.kill_session(session_name)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return

        self.notify(f"Killed session: {session_name}")
        self.action_refresh_data()

    def action_freeze_session(self) -> None:
        """Freezes an active tmux session into a tmuxp template file."""
        session_name = self._get_selected_session_name()
        if session_name is None:
            return

        try:
            config_dict = self.tmux_manager.freeze_session(session_name)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return

        config_dir = self.config.tmuxp_config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        editor = self._get_editor()

        with self.suspend():
            name = input(f"Save template as (without extension) [{session_name}]: ").strip()
            if not name:
                name = session_name

            filepath = config_dir / f"{name}.yaml"
            if filepath.exists():
                overwrite = input(f"'{name}' already exists. Overwrite? [y/N]: ").strip().lower()
                if overwrite != "y":
                    print("Cancelled.")
                    return

            filepath.write_text(
                yaml.dump(config_dict, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            print(f"Frozen session saved to {filepath}")
            subprocess.run([editor, str(filepath)], check=False)

        self.action_refresh_data()

    # --- Templates pane actions -------------------------------------------

    def action_new_template(self) -> None:
        """Creates a new tmuxp template scaffold and opens it in $EDITOR."""
        config_dir = self.config.tmuxp_config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        editor = self._get_editor()

        with self.suspend():
            name = input("Template name (without extension): ").strip()
            if name:
                filepath = config_dir / f"{name}.yaml"
                if filepath.exists():
                    print(f"'{name}' already exists — opening for edit.")
                else:
                    filepath.write_text(_TEMPLATE_SCAFFOLD, encoding="utf-8")
                    print(f"Created {filepath}")
                subprocess.run([editor, str(filepath)], check=False)

        self.action_refresh_data()

    def action_edit_template(self) -> None:
        """Opens the selected template in the user's $EDITOR."""
        template_list = self.query_one("#templates", OptionList)

        if template_list.highlighted is None:
            self.notify("Select a template to edit.", severity="warning")
            return

        template_name = str(template_list.get_option_at_index(template_list.highlighted).id)
        if not template_name:
            return

        templates = self.tmux_manager.get_templates(self.config.tmuxp_config_dir)
        selected = next((t for t in templates if t.name == template_name), None)
        if not selected:
            self.notify(f"Template '{template_name}' not found.", severity="error")
            return

        editor = self._get_editor()
        with self.suspend():
            subprocess.run([editor, str(selected.path)], check=False)

        self.action_refresh_data()

    def action_open_examples(self) -> None:
        """Opens the tmuxp configuration examples in the default browser."""
        webbrowser.open(_TMUXP_EXAMPLES_URL)
        self.notify(f"Opened {_TMUXP_EXAMPLES_URL}")

    # --- Event handlers ---------------------------------------------------

    @on(WorkspaceLaunched)
    def on_workspace_launched(self, event: WorkspaceLaunched) -> None:
        """Refreshes data and optionally attaches after a workspace launch."""
        self.action_refresh_data()
        if self.config.auto_attach:
            self.attach_to_tmux(event.session_name)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Shows the full worktree path in the path-display bar."""
        path_display = self.query_one("#path-display", Static)
        if isinstance(event.node.data, Worktree):
            path_display.update(f"📍 {event.node.data.path}")
        else:
            path_display.update("")

    # --- Background workers -----------------------------------------------

    @work(thread=True, exclusive=True, group="launch")
    def _launch_in_background(self, template: TmuxTemplate, session_name: str, path: Path) -> None:
        """Launches the tmux workspace in a worker thread."""
        self.app.call_from_thread(self.notify, f"Launching {session_name}...")
        try:
            self.tmux_manager.launch_template(template, session_name, path)
            self.app.call_from_thread(self.notify, f"Successfully launched {session_name}!")
            self.app.call_from_thread(self.post_message, WorkspaceLaunched(session_name))
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to launch: {e}", severity="error")

    @work(thread=True, exclusive=True, group="load-sessions")
    def _load_active_sessions(self) -> None:
        """Fetches active tmux sessions in the background."""
        try:
            sessions = self.tmux_manager.get_active_sessions()
            options = [Option(s.name, id=s.name) for s in sessions if s.name]

            def update_ui() -> None:
                session_list = self.query_one("#active_sessions", OptionList)
                session_list.clear_options()
                session_list.add_options(options)

            self.app.call_from_thread(update_ui)
        except Exception:
            self.app.call_from_thread(self.notify, "Could not connect to tmux.", severity="warning")

    @work(thread=True, exclusive=True, group="load-templates")
    def _load_templates(self) -> None:
        """Fetches available tmuxp templates in the background."""
        templates = self.tmux_manager.get_templates(self.config.tmuxp_config_dir)
        options = [Option(t.name, id=t.name) for t in templates]

        def update_ui() -> None:
            template_list = self.query_one("#templates", OptionList)
            template_list.clear_options()
            template_list.add_options(options)

        self.app.call_from_thread(update_ui)

    @work(thread=True, exclusive=True, group="load-worktrees")
    def _load_worktrees(self) -> None:
        """Scans workspace roots for Git worktrees and builds a tree view."""
        ignore_dirs = set(self.config.ignore_worktree_dirs)
        groups: dict[str, list[tuple[Path, set[str], list[Worktree]]]] = {}

        for ws_root in self.config.workspace_roots:
            if not ws_root.path.exists() or not ws_root.path.is_dir():
                continue

            for repo_dir in sorted(ws_root.path.iterdir()):
                if repo_dir.is_dir() and self.git_manager.is_git_repository(repo_dir):
                    worktrees = [
                        wt
                        for wt in self.git_manager.get_worktrees(repo_dir)
                        if wt.path.name not in ignore_dirs
                    ]
                    if worktrees:
                        main_names: set[str] = set(self.config.main_branch_names)
                        detected = self.git_manager.get_default_branch(repo_dir)
                        if detected:
                            main_names.add(detected)
                        groups.setdefault(ws_root.label, []).append(
                            (repo_dir, main_names, worktrees)
                        )

        def update_ui() -> None:
            tree = self.query_one("#git_worktrees", Tree)
            tree.clear()

            configured_labels: list[str] = []
            seen_labels: set[str] = set()
            for ws_root in self.config.workspace_roots:
                if ws_root.label in groups and ws_root.label not in seen_labels:
                    configured_labels.append(ws_root.label)
                    seen_labels.add(ws_root.label)

            unordered_labels = [label for label in groups if label not in seen_labels]
            group_labels = configured_labels + unordered_labels
            show_group_labels = len(group_labels) > 1

            work_dir_index = 0
            for group_label in group_labels:
                if show_group_labels:
                    parent = tree.root.add(f"📁 [bold italic]{group_label}[/]", expand=True)
                else:
                    parent = tree.root

                for repo_path, main_names, worktrees in groups[group_label]:
                    expand_repo = self._repo_node_expanded(
                        self.config.work_dir_expansion, work_dir_index
                    )
                    repo_node = parent.add(f"📂 [bold]{repo_path.name}[/]", expand=expand_repo)
                    work_dir_index += 1

                    for wt in worktrees:
                        branch_short = wt.branch.removeprefix("refs/heads/") if wt.branch else None

                        if branch_short in main_names:
                            leaf_label = f"🟢 [bold green]{branch_short}[/]"
                        elif branch_short:
                            leaf_label = f"🔵 [cyan]{branch_short}[/]"
                        else:
                            short_hash = wt.head[:7] if wt.head else "???"
                            leaf_label = f"🟡 [yellow]detached @ {short_hash}[/]"

                        repo_node.add_leaf(leaf_label, data=wt)

        self.app.call_from_thread(update_ui)
