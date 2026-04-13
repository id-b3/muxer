


# muxer

> A modern, fast, TUI-based workspace manager bridging **tmuxp** and **Git Worktrees**.

`muxer` provides a beautiful, keyboard-driven terminal dashboard to manage your development environments. Instead of manually creating tmux sessions and navigating into specific worktrees, `muxer` auto-discovers your Git worktrees and lets you instantly launch them using your favorite `tmuxp` templates.

![muxer layout concept](https://img.shields.io/badge/TUI-Textual-blue?style=flat-square)
![python version](https://img.shields.io/badge/Python->=3.12-blue?style=flat-square)

## ✨ Features

* **Visual Dashboard**: A clean 3-column UI showing Active Tmux Sessions, Git Worktrees, and available Templates.
* **Native Git Worktree Support**: Automatically scans configured root directories for Git repositories and extracts their active worktrees.
* **Tmuxp Integration**: Leverages the rock-solid `tmuxp` engine to build windows, panes, and execute startup commands.
* **Asynchronous & Fast**: Uses Textual's background workers so the UI remains buttery-smooth at 60fps, even while scanning hundreds of directories.
* **Dynamic Overrides**: Automatically injects the correct `start_directory` and `session_name` into your templates based on your UI selection.

## 📦 Prerequisites

* **Python**: 3.12 or newer.
* **tmux**: Installed and available in your `$PATH`.
* **git**: Installed and available in your `$PATH`.
* **uv**: (Recommended) For lightning-fast installation and development.

## 🚀 Installation

The recommended way to install `muxer` globally is using `uv tool` (or `pipx`):

```bash
uv tool install git+https://github.com/yourusername/muxer.git
# or
pipx install git+https://github.com/yourusername/muxer.git
```

If you are developing locally:

```bash
git clone https://github.com/yourusername/muxer.git
cd muxer
uv sync
uv run muxer
```

## ⚙️ Configuration

`muxer` requires two things to be useful: an app configuration to know where your code lives, and `tmuxp` templates to define your window layouts.

### 1. App Configuration
By default, `muxer` looks for projects in `~/dev` and templates in `~/.config/tmuxp`. You can customize this by creating `~/.config/muxer/config.json`:

```json
{
    "workspace_roots": {
        "Work": "~/work",
        "Personal": "~/personal"
    },
    "tmuxp_config_dir": "~/.config/tmuxp",
    "auto_attach": false,
    "ignore_worktree_dirs": [".bare"],
    "main_branch_names": ["main", "master"],
    "work_dir_expansion": "top",
    "theme": "gruvbox",
    "header_visualization": "gradient"
}
```

`workspace_roots` accepts three formats:
* **Dict** (recommended) – `{"Label": "/path"}` groups repos under named headings in the tree.
* **List of strings** – `["/path/a", "/path/b"]` labels are derived from the directory name.
* **List of objects** – `[{"label": "Work", "path": "/path"}]` for explicit control.

Paths support `~` expansion.

| Option | Default | Description |
| :--- | :--- | :--- |
| `auto_attach` | `false` | Suspend the dashboard and attach immediately after launching a workspace. |
| `ignore_worktree_dirs` | `[".bare"]` | Directory names to exclude from the worktree listing (e.g. bare-repo dirs). |
| `main_branch_names` | `["main", "master"]` | Branch names highlighted green as "primary". `muxer` also auto-detects the remote default branch via `git symbolic-ref` and merges it into this list per repo. |
| `work_dir_expansion` | `"top"` | Initial expand state for repo/work-dir nodes: `"top"` (expand only the first), `"expanded"` (expand all), or `"folded"` (expand none). |
| `theme` | `"gruvbox"` | Colour theme for app chrome. Supported values: `"light"`, `"dark"`, `"gruvbox"`, `"custom"`. |
| `header_visualization` | `"gradient"` | Header visual mode. Supported values: `"static"`, `"gradient"`, `"game_of_life"`. |
| `custom_theme` | `null` | Optional flat token map used when `theme` is `"custom"` (unknown tokens are ignored). |

### 2. Tmuxp Templates
Create your window/pane layouts using standard `tmuxp` YAML or JSON files. Place them in your `tmuxp_config_dir` (e.g., `~/.config/tmuxp/python-backend.yaml`).

To make templates dynamic so `muxer` can inject the correct worktree paths, use the `{{session_name}}` and `{{start_directory}}` placeholders:

```yaml
session_name: "{{session_name}}"
start_directory: "{{start_directory}}"
windows:
  - window_name: editor
    focus: true
    panes:
      - nvim .
  - window_name: terminal
    panes:
      - git status
  - window_name: server
    panes:
      - make run
```

When launching, `muxer` always injects top-level `session_name` and `start_directory`. It also fills missing
`start_directory` fields on windows/panes with the selected worktree path. Any explicit `start_directory`
already defined in your template is preserved.

## 💻 Usage

Start the UI by running:

```bash
muxer
```

### Keybindings

| Key | Action | Description |
| :--- | :--- | :--- |
| `Tab` / `Shift+Tab` | Navigate | Move focus between the Sessions, Worktrees, and Templates columns. |
| `Up` / `Down` | Select | Highlight an item in the currently focused list. |
| `l` | Launch | Launch a new tmux session combining the highlighted Worktree + Template. |
| `c` | Config | Open `~/.config/muxer/config.json` in `$EDITOR` (creates it with defaults if missing). |
| `a` | Attach | Attach to the highlighted tmux session when the Active Sessions column has focus. |
| `x` | Kill | Kill the highlighted tmux session when the Active Sessions column has focus. |
| `f` | Freeze | Snapshot an active session into a tmuxp template via `tmuxp freeze` (Sessions pane). |
| `n` | New Template | Create a new tmuxp template scaffold and open it in `$EDITOR` (Templates pane). |
| `e` | Edit Template | Open the highlighted template in `$EDITOR` (Templates pane). |
| `?` | Examples | Open the [tmuxp configuration examples](https://tmuxp.git-pull.com/configuration/examples/#examples) in your browser. |
| `r` | Refresh | Manually trigger a background rescan of sessions, worktrees, and templates. |
| `q` | Quit | Exit the `muxer` dashboard. |

*Note: Once a workspace is launched, you will need to attach to it using standard tmux commands (e.g., `tmux attach -t session-name`), or you can configure `muxer` to auto-attach in future updates!*

## 🛠️ Development

This project uses `uv` for dependency management and `hatchling` as the build backend. Code quality is strictly enforced by `ruff`.

```bash
# Clone the repository
git clone https://github.com/yourusername/muxer.git
cd muxer

# Sync dependencies and install in editable mode
uv sync

# Run the app
uv run muxer

# Run linting and formatting
uvx ruff check .
uvx ruff format .
```

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
