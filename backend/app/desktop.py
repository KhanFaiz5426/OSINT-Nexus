"""OSINT Nexus Desktop Application Entry Point."""

import logging
import os
import socket
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
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("osint.desktop")


class DesktopApi:
    """API exposed to the frontend javascript via window.pywebview.api"""
    
    def open_external(self, url: str) -> None:
        """Securely open external URLs in the system default browser."""
        # Simple safeguard: only open http/https links
        if url.startswith("http://") or url.startswith("https://"):
            logger.info("Opening external link in system browser: %s", url)
            webbrowser.open(url)
        else:
            logger.warning("Blocked attempt to open unsafe external URL: %s", url)


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
            fastapi_app,
            host="127.0.0.1",
            port=0,
            log_level="info",
            reload=False
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

            api = DesktopApi()
            window = webview.create_window(
                "OSINT Nexus",
                start_url,
                width=1280,
                height=800,
                min_size=(800, 600),
                js_api=api
            )

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

            logger.info("Webview terminated. Waiting for background Uvicorn thread to terminate cleanly...")
            if self.server_thread:
                # Wait for the FastAPI lifespan to complete its teardown
                self.server_thread.join(timeout=10.0)
            
            logger.info("Application shutdown complete.")
            sys.exit(0)

        except Exception as e:
            logger.error("Failed to start desktop app: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    app = DesktopApp()
    app.run()
