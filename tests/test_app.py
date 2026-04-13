"""Tests for muxer.tui.app - MuxerApp (headless Textual tests)."""

from __future__ import annotations

import pytest
from textual.widgets.option_list import Option

from muxer.tui.app import _TMUXP_EXAMPLES_URL, ConfirmDialog, MuxerApp, SplashHeader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> MuxerApp:
    """Return a default MuxerApp instance for headless tests."""
    return MuxerApp()


# ---------------------------------------------------------------------------
# Layout & composition
# ---------------------------------------------------------------------------


class TestComposition:
    @pytest.mark.asyncio()
    async def test_three_columns_rendered(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)):
            assert app.query_one("#active_sessions") is not None
            assert app.query_one("#git_worktrees") is not None
            assert app.query_one("#templates") is not None

    @pytest.mark.asyncio()
    async def test_banner_and_path_display(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)):
            banner = app.query_one("#app-banner")
            path_display = app.query_one("#path-display")
            assert banner is not None
            assert path_display is not None

    @pytest.mark.asyncio()
    async def test_footer_present(self, app: MuxerApp) -> None:
        from textual.widgets import Footer

        async with app.run_test(size=(120, 30)):
            assert app.query_one(Footer) is not None


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class TestBindings:
    expected_keys = ("q", "r", "l", "c", "a", "x", "f", "n", "e", "question_mark")

    def test_all_bindings_registered(self) -> None:
        keys = {b.key for b in MuxerApp.BINDINGS}
        for k in self.expected_keys:
            assert k in keys, f"Missing binding for key: {k}"

    def test_question_mark_key_display(self) -> None:
        binding = next(b for b in MuxerApp.BINDINGS if b.key == "question_mark")
        assert binding.key_display == "?"

    def test_command_palette_disabled(self) -> None:
        assert MuxerApp.ENABLE_COMMAND_PALETTE is False


# ---------------------------------------------------------------------------
# Contextual check_action
# ---------------------------------------------------------------------------


class TestCheckAction:
    @pytest.mark.asyncio()
    async def test_session_actions_hidden_when_unfocused(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            # Focus the worktree tree (not sessions, not templates)
            app.query_one("#git_worktrees").focus()
            await _pilot.pause()
            assert app.check_action("attach_session", ()) is None
            assert app.check_action("kill_session", ()) is None
            assert app.check_action("freeze_session", ()) is None

    @pytest.mark.asyncio()
    async def test_session_actions_visible_when_focused(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.query_one("#active_sessions").focus()
            await _pilot.pause()
            assert app.check_action("attach_session", ()) is True
            assert app.check_action("kill_session", ()) is True
            assert app.check_action("freeze_session", ()) is True

    @pytest.mark.asyncio()
    async def test_template_actions_hidden_when_unfocused(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.query_one("#active_sessions").focus()
            await _pilot.pause()
            assert app.check_action("new_template", ()) is None
            assert app.check_action("edit_template", ()) is None
            assert app.check_action("open_examples", ()) is None

    @pytest.mark.asyncio()
    async def test_template_actions_visible_when_focused(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.query_one("#templates").focus()
            await _pilot.pause()
            assert app.check_action("new_template", ()) is True
            assert app.check_action("edit_template", ()) is True
            assert app.check_action("open_examples", ()) is True

    @pytest.mark.asyncio()
    async def test_global_actions_always_visible(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)):
            for action in ("quit", "refresh_data", "launch_workspace", "open_config"):
                assert app.check_action(action, ()) is True


# ---------------------------------------------------------------------------
# Action guard behaviour (no live tmux)
# ---------------------------------------------------------------------------


class TestActionGuards:
    @pytest.mark.asyncio()
    async def test_launch_warns_without_selection(self, app: MuxerApp) -> None:
        """Launching without selecting a worktree/template should notify, not crash."""
        async with app.run_test(size=(120, 30)) as _pilot:
            app.action_launch_workspace()
            await _pilot.pause()

    @pytest.mark.asyncio()
    async def test_kill_warns_without_selection(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.query_one("#active_sessions").focus()
            await _pilot.pause()
            app.action_kill_session()
            await _pilot.pause()

    @pytest.mark.asyncio()
    async def test_edit_template_warns_without_selection(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.query_one("#templates").focus()
            await _pilot.pause()
            app.action_edit_template()
            await _pilot.pause()

    @pytest.mark.asyncio()
    async def test_refresh_does_not_crash(self, app: MuxerApp) -> None:
        async with app.run_test(size=(120, 30)) as _pilot:
            app.action_refresh_data()
            await _pilot.pause()


class TestKillConfirmation:
    @pytest.mark.asyncio()
    async def test_kill_cancelled_does_not_kill(
        self, app: MuxerApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake_kill_session(session_name: str) -> None:
            calls.append(session_name)

        def fake_push_screen(*args: object, **kwargs: object) -> None:
            screen = args[0]
            callback = kwargs.get("callback")
            assert isinstance(screen, ConfirmDialog)
            assert callable(callback)
            callback(False)

        monkeypatch.setattr(app.tmux_manager, "kill_session", fake_kill_session)
        monkeypatch.setattr(app, "push_screen", fake_push_screen)

        async with app.run_test(size=(120, 30)):
            session_list = app.query_one("#active_sessions")
            session_list.clear_options()
            session_list.add_options([Option("demo", id="demo")])
            session_list.highlighted = 0
            app.action_kill_session()

        assert calls == []

    @pytest.mark.asyncio()
    async def test_kill_confirmed_calls_kill(
        self, app: MuxerApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake_kill_session(session_name: str) -> None:
            calls.append(session_name)

        def fake_push_screen(*args: object, **kwargs: object) -> None:
            screen = args[0]
            callback = kwargs.get("callback")
            assert isinstance(screen, ConfirmDialog)
            assert callable(callback)
            callback(True)

        monkeypatch.setattr(app.tmux_manager, "kill_session", fake_kill_session)
        monkeypatch.setattr(app, "push_screen", fake_push_screen)

        async with app.run_test(size=(120, 30)):
            session_list = app.query_one("#active_sessions")
            session_list.clear_options()
            session_list.add_options([Option("demo", id="demo")])
            session_list.highlighted = 0
            app.action_kill_session()

        assert calls == ["demo"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_examples_url(self) -> None:
        assert "tmuxp.git-pull.com" in _TMUXP_EXAMPLES_URL


class TestWorkDirExpansion:
    def test_expanded_mode_opens_everything(self) -> None:
        assert MuxerApp._repo_node_expanded("expanded", 0) is True
        assert MuxerApp._repo_node_expanded("expanded", 5) is True

    def test_folded_mode_closes_everything(self) -> None:
        assert MuxerApp._repo_node_expanded("folded", 0) is False
        assert MuxerApp._repo_node_expanded("folded", 5) is False

    def test_top_mode_opens_only_first(self) -> None:
        assert MuxerApp._repo_node_expanded("top", 0) is True
        assert MuxerApp._repo_node_expanded("top", 1) is False


class TestAppearanceHelpers:
    def test_resolve_theme_tokens_preset(self) -> None:
        tokens = MuxerApp._resolve_theme_tokens("dark", None)
        assert tokens["screen_bg"] == "#111827"

    def test_resolve_theme_tokens_custom_override(self) -> None:
        tokens = MuxerApp._resolve_theme_tokens("custom", {"screen_bg": "#000000"})
        assert tokens["screen_bg"] == "#000000"

    def test_resolve_theme_tokens_custom_ignores_unknown(
        self, recwarn: pytest.WarningsRecorder
    ) -> None:
        tokens = MuxerApp._resolve_theme_tokens("custom", {"unknown": "#123456"})
        assert "unknown" not in tokens
        assert any("unknown custom_theme token" in str(w.message).lower() for w in recwarn)

    def test_header_palette_custom(self) -> None:
        tokens = MuxerApp._resolve_theme_tokens(
            "custom", {"header_static_bg": "#010101", "column_border": "#fefefe"}
        )
        palette = MuxerApp._header_palette(tokens)
        assert "#010101" in palette
        assert "#fefefe" in palette

    def test_light_theme_has_high_contrast_selection_and_footer_keys(self) -> None:
        tokens = MuxerApp._resolve_theme_tokens("light", None)
        assert tokens["selection_bg"] != tokens["list_bg"]
        assert tokens["selection_fg"] != tokens["selection_bg"]
        assert tokens["footer_key_bg"] != tokens["footer_desc_bg"]
        assert tokens["column_focus_border"] != tokens["column_border"]
        assert tokens["column_focus_bg"] != tokens["column_bg"]


class TestHeaderRefreshRates:
    def test_static_has_no_auto_refresh(self) -> None:
        assert SplashHeader._refresh_interval("static") is None

    def test_gradient_refresh_rate(self) -> None:
        assert SplashHeader._refresh_interval("gradient") == pytest.approx(1 / 30)

    def test_game_of_life_refresh_rate(self) -> None:
        assert SplashHeader._refresh_interval("game_of_life") == pytest.approx(1 / 8)

    def test_game_of_life_grid_uses_header_rows(self) -> None:
        header = SplashHeader(
            mode="game_of_life",
            colors=["#111111", "#222222"],
            static_color="#111111",
            text_color="#ffffff",
        )
        assert len(header._life_grid) == 4
