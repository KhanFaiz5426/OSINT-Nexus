"""OSINT Nexus Desktop Application Entry Point."""

import logging
import os
import sys
import threading
import time
import webbrowser
from urllib.request import urlopen

try:
    import uvicorn
    import webview
except ImportError as e:
    print(f"Error: Missing dependency. {e}")
    print("Please install required dependencies: pip install pywebview uvicorn")
    sys.exit(1)

from pathlib import Path

# Setup persistent logging to user-writable AppData directory
log_dir = Path(os.environ.get("APPDATA", os.path.expanduser("~"))) / "osint-nexus" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "app.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("osint.desktop")


class DesktopApi:
    """API exposed to the frontend javascript via window.pywebview.api"""

    def __init__(self, window: "webview.Window | None" = None) -> None:
        self._window = window

    def set_window(self, window: "webview.Window") -> None:
        """Set the webview window reference (called after window creation)."""
        self._window = window

    def open_external(self, url: str) -> None:
        """Securely open external URLs in the system default browser."""
        # Simple safeguard: only open http/https links
        if url.startswith("http://") or url.startswith("https://"):
            logger.info("Opening external link in system browser: %s", url)
            webbrowser.open(url)
        else:
            logger.warning("Blocked attempt to open unsafe external URL: %s", url)

    def open_file_dialog(self) -> str | None:
        """Open a native file-selection dialog filtered for .osint files.

        Returns the selected file path, or None if cancelled.
        """
        if not self._window:
            logger.warning("open_file_dialog called but no window reference set.")
            return None
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                file_types=("OSINT Workspace (*.osint)",),
            )
            if result and len(result) > 0:
                selected = result[0]
                logger.info("File dialog selected: %s", selected)
                return selected
            logger.info("File dialog cancelled by user.")
            return None
        except Exception as exc:
            logger.error("File dialog error: %s", exc)
            return None

    def save_file_dialog(self) -> str | None:
        """Open a native save dialog for .osint files.

        Returns the selected destination path, or None if cancelled.
        Ensures the path ends with .osint extension.
        """
        if not self._window:
            logger.warning("save_file_dialog called but no window reference set.")
            return None
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="investigation.osint",
                file_types=("OSINT Workspace (*.osint)",),
            )
            if result:
                selected = result if isinstance(result, str) else result[0]
                # Ensure .osint extension
                if not selected.endswith(".osint"):
                    selected += ".osint"
                logger.info("Save dialog selected: %s", selected)
                return selected
            logger.info("Save dialog cancelled by user.")
            return None
        except Exception as exc:
            logger.error("Save dialog error: %s", exc)
            return None

    def select_folder_dialog(self) -> str | None:
        """Open a native folder-selection dialog.

        Returns the selected folder path, or None if cancelled.
        """
        if not self._window:
            logger.warning("select_folder_dialog called but no window reference set.")
            return None
        try:
            result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
            if result and len(result) > 0:
                selected = result[0]
                logger.info("Folder dialog selected: %s", selected)
                return selected
            logger.info("Folder dialog cancelled by user.")
            return None
        except Exception as exc:
            logger.error("Folder dialog error: %s", exc)
            return None

    def save_report_dialog(self, default_filename: str, format_type: str) -> str | None:
        """Open a native save dialog for reports."""
        if not self._window:
            return None
        file_types = ("HTML Files (*.html)", "All Files (*.*)")
        try:
            result = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default_filename, file_types=file_types
            )
            if result:
                selected = result if isinstance(result, str) else result[0]
                if format_type == "html" and not selected.endswith(".html"):
                    selected += ".html"
                return selected
            return None
        except Exception as exc:
            logger.error("Save report dialog error: %s", exc)
            return None

    def download_file_to_path(self, url: str, dest_path: str) -> bool:
        """Download a file from a local URL to a specific path."""
        try:
            import urllib.request

            logger.info("Downloading %s to %s", url, dest_path)
            req = urllib.request.Request(url, headers={"User-Agent": "OSINT-Nexus-Desktop"})
            with urllib.request.urlopen(req) as response, open(dest_path, "wb") as out_file:
                out_file.write(response.read())
            return True
        except Exception as exc:
            logger.error("Failed to download file: %s", exc)
            return False


class DesktopApp:
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.port = None

    def _run_server(self, config: uvicorn.Config):
        self.server = uvicorn.Server(config)
        self.server.run()

    def start_backend(self) -> int:
        """Start the FastAPI backend on an ephemeral 127.0.0.1 port."""
        from app.main import app as fastapi_app

        config = uvicorn.Config(
            fastapi_app, host="127.0.0.1", port=0, log_level="info", reload=False
        )
        self.server_thread = threading.Thread(target=self._run_server, args=(config,), daemon=True)
        self.server_thread.start()

        # Wait for the server to start and retrieve the bound port
        timeout = 10.0
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            if self.server and getattr(self.server, "started", False):
                if hasattr(self.server, "servers") and self.server.servers:
                    sockets = self.server.servers[0].sockets
                    if sockets:
                        self.port = sockets[0].getsockname()[1]
                        logger.info("Uvicorn bound to ephemeral port: %d", self.port)
                        return self.port
            time.sleep(0.1)

        raise RuntimeError("Timed out waiting for Uvicorn server to start and bind to a port.")

    def _wait_for_health(self):
        """Poll the FastAPI health endpoint to ensure readiness."""
        url = f"http://127.0.0.1:{self.port}/health"
        timeout = 10.0
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            try:
                with urlopen(url, timeout=1.0) as response:
                    if response.status == 200:
                        logger.info("Backend health check passed.")
                        return
            except Exception:
                pass
            time.sleep(0.25)
        raise RuntimeError(f"Backend health check failed at {url}")

    def on_closing(self):
        """Hook for when the user closes the pywebview window."""
        logger.info("Window closing event received. Initiating graceful shutdown...")
        if self.server:
            # Setting should_exit triggers Uvicorn's shutdown process,
            # which in turn fires the FastAPI lifespan context manager.
            # The lifespan handles TaskManager, EventBus, and SQLite teardown.
            self.server.should_exit = True

    def run(self):
        try:
            port = self.start_backend()
            self._wait_for_health()

            # Check for development override URL
            dev_url = os.environ.get("OSINT_DEV_URL")
            start_url = dev_url if dev_url else f"http://127.0.0.1:{port}"
            logger.info("Launching desktop window pointing to: %s", start_url)

            # Auto-open workspace if .osint file passed via command line
            if len(sys.argv) > 1 and sys.argv[1].endswith(".osint"):
                target_path = os.path.abspath(sys.argv[1])
                try:
                    import json
                    import urllib.request

                    req = urllib.request.Request(
                        f"http://127.0.0.1:{port}/api/v1/workspace/open",
                        data=json.dumps({"path": target_path}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=5.0) as response:
                        if response.status == 200:
                            logger.info(
                                "Successfully opened workspace from command line: %s", target_path
                            )
                except Exception as e:
                    logger.error("Failed to open workspace from command line: %s", e)

            api = DesktopApi()
            window = webview.create_window(
                "OSINT Nexus", start_url, width=1280, height=800, min_size=(800, 600), js_api=api
            )
            # Give the API the window reference for native file dialogs
            api.set_window(window)

            window.events.closing += self.on_closing

            # JS injection to enforce the navigation policy:
            # 1. Allowed: same-origin links
            # 2. External links: intercepted and passed to the DesktopApi to open in system browser
            navigation_policy_js = """
            window.addEventListener('click', function(e) {
                let a = e.target.closest('a');
                if (a && a.href) {
                    // Check if it's an external link
                    if (!a.href.startsWith(window.location.origin)) {
                        e.preventDefault();
                        if (window.pywebview && window.pywebview.api) {
                            window.pywebview.api.open_external(a.href);
                        } else {
                            console.warn("pywebview API not ready, blocked external link:", a.href);
                        }
                    }
                }
            }, true);
            """

            # We use the loaded event to inject the policy whenever the frame loads
            def on_loaded():
                window.evaluate_js(navigation_policy_js)

            window.events.loaded += on_loaded

            # Start the webview (blocks the main thread)
            webview.start(private_mode=False)

            logger.info(
                "Webview terminated. Waiting for background Uvicorn thread to terminate cleanly..."
            )
            if self.server_thread:
                # Wait for the FastAPI lifespan to complete its teardown
                self.server_thread.join(timeout=10.0)

            logger.info("Application shutdown complete.")
            sys.exit(0)

        except Exception as e:
            logger.error("Failed to start desktop app: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    import os
    import sys

    # On Python 3.8+ Windows, DLLs must be explicitly added to the search path
    if os.name == "nt" and sys.version_info >= (3, 8):
        gtk_paths = [
            r"C:\Program Files\GTK3-Runtime Win64\bin",
            r"C:\Program Files (x86)\GTK3-Runtime Win32\bin",
        ]
        for path in gtk_paths:
            if os.path.isdir(path):
                try:
                    os.add_dll_directory(path)
                    os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
                except Exception:
                    pass

    app = DesktopApp()
    app.run()
