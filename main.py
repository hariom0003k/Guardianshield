"""
Guardian Shield — Application Entry Point.
Launches the shoulder-surfing protection module with customizable runtime flags.
"""

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PySide6.QtWidgets import QApplication

from guardian_shield import GuardianShield


def parse_args():
    parser = argparse.ArgumentParser(
        description="Guardian Shield v2.0.0 — Shoulder-Surfing Detection & Privacy Protection"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Guardian Shield v2.0.0"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode using synthetic camera frames"
    )
    parser.add_argument(
        "--auto-shield",
        action="store_true",
        help="Enable Auto-Shield mode (instantly blurs screen on high threat)"
    )
    parser.add_argument(
        "--style",
        choices=["blur", "dim", "mosaic", "decoy"],
        default=None,
        help="Default shield visual style"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Throttled frame rate limit for camera capture (default: 8)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to custom settings.yaml file"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in console-only mode without desktop GUI overlay"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Create Guardian Shield instance
    app_engine = GuardianShield(config_path=args.config)

    # Apply command-line overrides
    if args.simulate:
        app_engine.camera.enable_simulation = True
    if args.auto_shield:
        app_engine.config.features.auto_shield_enabled = True
        app_engine.threat_classifier.auto_shield_enabled = True
    if args.style:
        app_engine.config.shield.default_style = args.style
    if args.fps:
        app_engine.config.camera.fps_limit = args.fps
        app_engine.camera.fps_limit = args.fps

    if args.headless:
        print("Starting Guardian Shield in Headless / CLI mode...")
        app_engine.start()
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Guardian Shield...")
            app_engine.stop()
            sys.exit(0)

    # Desktop GUI Mode
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    app_engine.initialize_ui()
    app_engine.start()

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
