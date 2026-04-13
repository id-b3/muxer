"""Command Line Interface entry point for muxer."""

from muxer.tui.app import MuxerApp


def main() -> None:
    """Main entry point for the application. Launches the Textual TUI."""
    app = MuxerApp()
    app.run()


if __name__ == "__main__":
    main()
