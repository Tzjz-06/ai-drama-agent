"""桌面端入口。"""

from __future__ import annotations

import argparse
import ctypes
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from ai_drama_agent.web import DramaWebHandler


def _configure_stable_web_rendering() -> None:
    """Avoid GPU-compositor artifacts in the embedded Chromium view."""
    required_flags = ("--disable-gpu", "--disable-gpu-compositing")
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(
        [*existing_flags, *(flag for flag in required_flags if flag not in existing_flags)]
    )
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)


@dataclass
class LocalWebRuntime:
    server: ThreadingHTTPServer
    thread: threading.Thread
    url: str
    mode: str

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def build_runtime(offline_demo: bool) -> LocalWebRuntime:
    port = _free_port()

    class DesktopHandler(DramaWebHandler):
        pass

    DesktopHandler.offline_demo = offline_demo
    server = ThreadingHTTPServer(("127.0.0.1", port), DesktopHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}/"
    _wait_for_http(url)
    mode = "offline-rule-based" if offline_demo else "runtime-configurable"
    return LocalWebRuntime(server=server, thread=thread, url=url, mode=mode)


class FrameForgeWindow(QMainWindow):
    def __init__(self, runtime: LocalWebRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        self.setWindowTitle("饺子创作台")
        self.setWindowIcon(QIcon(str(_resource_path("jiaozi-creation-studio.ico"))))
        self.setStyleSheet(
            """
            QMainWindow { background: #111316; }
            """
        )
        self.resize(1540, 980)
        self.setMinimumSize(1200, 760)
        self.browser = QWebEngineView(self)
        self.browser.page().setBackgroundColor(QColor("#111316"))
        self.browser.page().featurePermissionRequested.connect(self._handle_feature_permission)
        self.browser.page().profile().downloadRequested.connect(self._handle_download)
        self.browser.setUrl(QUrl(runtime.url))
        self.setCentralWidget(self.browser)

    def _handle_feature_permission(self, origin: QUrl, feature: QWebEnginePage.Feature) -> None:
        if feature == QWebEnginePage.Feature.ClipboardReadWrite:
            self.browser.page().setFeaturePermission(
                origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )

    def _handle_download(self, download: QWebEngineDownloadRequest) -> None:
        suffix = Path(download.downloadFileName()).suffix.lower()
        if suffix in {".docx", ".zip"}:
            suggested_path = Path(
                QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
            ) / download.downloadFileName()
            file_filter = "ZIP 压缩包 (*.zip)" if suffix == ".zip" else "Word 文档 (*.docx)"
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出剧本和分镜" if suffix == ".zip" else "导出 Word 文档",
                str(suggested_path),
                file_filter,
            )
            if not selected_path:
                download.cancel()
                return
            destination = Path(selected_path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            download.setDownloadDirectory(str(destination.parent))
            download.setDownloadFileName(destination.name)
            download.accept()
            return
        download.setDownloadDirectory(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        )
        download.accept()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.runtime.shutdown()
        super().closeEvent(event)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动饺子创作台桌面端。")
    parser.add_argument("--offline-demo", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--browser-preview", action="store_true")
    args = parser.parse_args()

    offline_demo = args.offline_demo
    runtime = build_runtime(offline_demo=offline_demo)

    if args.smoke_test:
        print(runtime.url)
        print(runtime.mode)
        runtime.shutdown()
        return

    if args.browser_preview:
        print(runtime.url)
        print(runtime.mode)
        webbrowser.open(runtime.url)
        print("已在默认浏览器打开网页预览，按 Ctrl+C 停止本地服务。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runtime.shutdown()
        return

    _configure_stable_web_rendering()
    app = QApplication(sys.argv)
    app.setApplicationName("饺子创作台")
    app.setWindowIcon(QIcon(str(_resource_path("jiaozi-creation-studio.ico"))))
    window = FrameForgeWindow(runtime)
    _apply_windows_chrome(window)
    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


def _apply_windows_chrome(window: QMainWindow) -> None:
    """Match the native Windows title bar to the studio surface color."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.c_void_p(int(window.winId()))
        dwmapi = ctypes.windll.dwmapi
        for attribute, color in (
            (34, 0x161311),  # DWMWA_BORDER_COLOR, #111316 in COLORREF order
            (35, 0x161311),  # DWMWA_CAPTION_COLOR
            (36, 0xF4F3F2),  # DWMWA_TEXT_COLOR
        ):
            value = ctypes.c_uint32(color)
            dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
    except (AttributeError, OSError):
        # Older Windows versions may not expose the DWM color attributes.
        return


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, timeout_seconds: float = 12.0) -> None:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"桌面端内置服务启动失败：{url}")


def _resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    path = base / name
    if path.exists():
        return path
    return base / "installer" / name


if __name__ == "__main__":
    main()
