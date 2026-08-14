"""桌面端入口。"""

from __future__ import annotations

import argparse
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

from PySide6.QtCore import QStandardPaths, QUrl
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QStatusBar, QToolBar

from ai_drama_agent.web import DramaWebHandler


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
        self.resize(1540, 980)
        self.setMinimumSize(1200, 760)
        self._build_toolbar()
        self._build_statusbar()
        self.browser = QWebEngineView(self)
        self.browser.page().featurePermissionRequested.connect(self._handle_feature_permission)
        self.browser.page().profile().downloadRequested.connect(self._handle_download)
        self.browser.setUrl(QUrl(runtime.url))
        self.setCentralWidget(self.browser)
        self.statusBar().showMessage(
            "离线推理模式" if runtime.mode == "offline-rule-based" else "真实模型模式"
        )

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)

        reload_action = QAction("刷新", self)
        reload_action.triggered.connect(self._reload)
        toolbar.addAction(reload_action)

        browser_action = QAction("浏览器打开", self)
        browser_action.triggered.connect(self._open_in_browser)
        toolbar.addAction(browser_action)

    def _build_statusbar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)

    def _reload(self) -> None:
        self.browser.reload()

    def _open_in_browser(self) -> None:
        webbrowser.open(self.runtime.url)

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
                self.statusBar().showMessage("已取消导出", 3000)
                return
            destination = Path(selected_path)
            if destination.suffix.lower() != suffix:
                destination = destination.with_suffix(suffix)
            download.setDownloadDirectory(str(destination.parent))
            download.setDownloadFileName(destination.name)
            download.accept()
            self.statusBar().showMessage(f"正在导出：{destination.name}", 5000)
            return
        download.setDownloadDirectory(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        )
        download.accept()
        self.statusBar().showMessage(f"已开始下载：{download.downloadFileName()}", 5000)

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

    app = QApplication(sys.argv)
    app.setApplicationName("饺子创作台")
    app.setWindowIcon(QIcon(str(_resource_path("jiaozi-creation-studio.ico"))))
    window = FrameForgeWindow(runtime)
    window.show()
    exit_code = app.exec()
    sys.exit(exit_code)


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
