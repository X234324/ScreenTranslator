"""Automatic, offline screen translator for Windows, based on Skylark."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import cv2
import mss
import numpy as np
import pytesseract
from PIL import Image
from PyQt5.QtCore import QPoint, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


POLL_INTERVAL_SECONDS = 0.7
CHANGE_THRESHOLD = 0.008
PIXEL_THRESHOLD = 18
MAX_TRANSLATION_CACHE = 256


@dataclass(frozen=True)
class ScreenBounds:
    left: int
    top: int
    width: int
    height: int


def find_tesseract() -> str | None:
    configured = os.environ.get("TESSERACT_CMD")
    if configured:
        if os.path.isfile(configured):
            return configured
        raise FileNotFoundError(f"TESSERACT_CMD does not point to a file: {configured}")
    executable = shutil.which("tesseract")
    if executable:
        return executable
    return next(
        (
            str(candidate)
            for candidate in (
                Path(os.environ.get("ProgramFiles", "")) / "Tesseract-OCR" / "tesseract.exe",
                Path(os.environ.get("ProgramFiles(x86)", "")) / "Tesseract-OCR" / "tesseract.exe",
            )
            if candidate.is_file()
        ),
        None,
    )


def screen_changed(previous: np.ndarray | None, current: np.ndarray) -> bool:
    if previous is None or previous.shape != current.shape:
        return True
    difference = cv2.absdiff(previous, current)
    changed_pixels = cv2.countNonZero(cv2.threshold(
        difference, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY
    )[1])
    return changed_pixels / difference.size >= CHANGE_THRESHOLD


def text_key(text: str, source: str, target: str = "zh") -> str:
    normalized = " ".join(text.split()).casefold()
    return hashlib.sha256(f"{source}\0{target}\0{normalized}".encode("utf-8")).hexdigest()


def find_translation_path(languages: Iterable[object], source: str, target: str) -> list[object]:
    by_code = {language.code: language for language in languages}
    if source not in by_code or target not in by_code:
        return []

    pending: list[tuple[str, list[object]]] = [(source, [])]
    visited = {source}
    while pending:
        code, path = pending.pop(0)
        language = by_code[code]
        for translation in language.translations_from:
            next_code = translation.to_lang.code
            next_path = [*path, translation]
            if next_code == target:
                return next_path
            if next_code not in visited:
                visited.add(next_code)
                pending.append((next_code, next_path))
    return []


class TranslationClient:
    def __init__(self) -> None:
        worker_script = Path(__file__).with_name("translation_worker.py")
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [sys.executable, str(worker_script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=creation_flags,
        )
        ready_line = self.process.stdout.readline() if self.process.stdout else ""
        response = self._decode_response(ready_line)
        if response.get("ready") is not True:
            message = response.get("error") or "Translation worker failed to start."
            self.close()
            raise RuntimeError(str(message))

    def translate(self, text: str) -> str:
        if self.process.poll() is not None or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Offline translation worker is no longer running.")
        self.process.stdin.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        response = self._decode_response(self.process.stdout.readline())
        if "error" in response:
            raise RuntimeError(str(response["error"]))
        result = response.get("translation")
        if not isinstance(result, str):
            raise RuntimeError("Offline translation worker returned an invalid response.")
        return result

    @staticmethod
    def _decode_response(line: str) -> dict[str, object]:
        if not line:
            raise RuntimeError("Offline translation worker exited unexpectedly.")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError("Offline translation worker returned invalid JSON.") from error
        if not isinstance(response, dict):
            raise RuntimeError("Offline translation worker returned an invalid response.")
        return response

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        if self.process.stdin:
            try:
                self.process.stdin.write('{"stop": true}\n')
                self.process.stdin.flush()
                self.process.stdin.close()
            except OSError:
                pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=3)


class MonitorThread(QThread):
    translated = pyqtSignal(str)
    status = pyqtSignal(str)
    failed = pyqtSignal(str)
    active_changed = pyqtSignal(bool)

    def __init__(
        self,
        bounds: ScreenBounds,
        overlay_geometry: Callable[[], tuple[int, int, int, int]],
    ) -> None:
        super().__init__()
        self.bounds = bounds
        self.overlay_geometry = overlay_geometry
        self._active = threading.Event()
        self._active.set()
        self._poll_wake = threading.Event()
        self._translator: TranslationClient | None = None
        self._text_cache: OrderedDict[str, None] = OrderedDict()

    def set_active(self, active: bool) -> None:
        if active:
            self._active.set()
        else:
            self._active.clear()
        self._poll_wake.set()
        self.active_changed.emit(active)
        self.status.emit("Monitoring screen…" if active else "Paused")

    def run(self) -> None:
        try:
            tesseract = find_tesseract()
            if not tesseract:
                raise RuntimeError(
                    "Tesseract was not found. Install Tesseract OCR with English "
                    "language data, or set TESSERACT_CMD to tesseract.exe."
                )
            pytesseract.pytesseract.tesseract_cmd = tesseract
            self._translator = TranslationClient()
        except Exception as error:
            self.failed.emit(str(error))
            return

        previous: np.ndarray | None = None
        self.status.emit("Monitoring screen…")
        try:
            with mss.MSS() as capture:
                monitor = capture.monitors[0]
                while not self.isInterruptionRequested():
                    if not self._active.wait(timeout=0.2):
                        continue
                    if self.isInterruptionRequested():
                        break
                    frame = np.asarray(capture.grab(monitor))
                    frame = self._exclude_overlay(frame, monitor)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    preview = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
                    if screen_changed(previous, preview):
                        previous = preview
                        text = pytesseract.image_to_string(
                            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)),
                            lang="eng",
                            config="--oem 3 --psm 11",
                        ).strip()
                        self._translate_if_new(text)
                    self._poll_wake.clear()
                    if self._active.is_set() and not self.isInterruptionRequested():
                        self._poll_wake.wait(timeout=POLL_INTERVAL_SECONDS)
        except Exception as error:
            self.failed.emit(f"Screen monitoring stopped: {error}")
        finally:
            if self._translator is not None:
                self._translator.close()

    def _exclude_overlay(self, frame: np.ndarray, monitor: dict[str, int]) -> np.ndarray:
        left, top, width, height = self.overlay_geometry()
        scale_x = frame.shape[1] / self.bounds.width
        scale_y = frame.shape[0] / self.bounds.height
        x1 = max(0, round((left - self.bounds.left - monitor["left"]) * scale_x))
        y1 = max(0, round((top - self.bounds.top - monitor["top"]) * scale_y))
        x2 = min(frame.shape[1], round(x1 + width * scale_x))
        y2 = min(frame.shape[0], round(y1 + height * scale_y))
        if x2 > x1 and y2 > y1:
            frame[y1:y2, x1:x2] = 255
        return frame

    def _translate_if_new(self, text: str) -> None:
        normalized = " ".join(text.encode("ascii", errors="replace").decode("ascii").split())
        if len(normalized) < 3:
            return
        key = text_key(normalized, "auto")
        if key in self._text_cache:
            self._text_cache.move_to_end(key)
            return
        try:
            assert self._translator is not None
            translated = self._translator.translate(normalized)
            self._text_cache[key] = None
            if len(self._text_cache) > MAX_TRANSLATION_CACHE:
                self._text_cache.popitem(last=False)
            self.translated.emit(translated)
        except Exception as error:
            self.failed.emit(f"Translation failed: {error}")


class Overlay(QWidget):
    def __init__(self, bounds: ScreenBounds) -> None:
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.bounds = bounds
        self._drag_offset: QPoint | None = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.92)
        self.setMinimumSize(360, 150)
        self.resize(500, 220)
        self.move(bounds.left + 40, bounds.top + 80)

        self.toggle_button = QPushButton("Pause")
        self.toggle_button.setFixedWidth(86)
        self.close_button = QPushButton("×")
        self.close_button.setFixedWidth(28)
        self.output = QLabel("Starting automatic screen monitoring…")
        self.output.setWordWrap(True)
        self.output.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.output.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.output.setStyleSheet("color: white; font-size: 16px;")
        self.state = QLabel("Starting…")
        self.state.setStyleSheet("color: #cbd5e1;")

        header = QHBoxLayout()
        header.addWidget(QLabel("Screen Translator"))
        header.addStretch(1)
        header.addWidget(self.state)
        header.addWidget(self.toggle_button)
        header.addWidget(self.close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.output, 1)
        self.setStyleSheet(
            "Overlay { background-color: rgba(20, 24, 34, 220);"
            "border: 1px solid rgba(255,255,255,90); border-radius: 10px; }"
            "QPushButton { color: white; background: #315fba; padding: 6px;"
            "border-radius: 5px; }"
        )

    def geometry_tuple(self) -> tuple[int, int, int, int]:
        rect = self.geometry()
        return rect.x(), rect.y(), rect.width(), rect.height()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and event.pos().y() < 48:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        delta = 0.05 if event.angleDelta().y() > 0 else -0.05
        self.setWindowOpacity(min(1.0, max(0.3, self.windowOpacity() + delta)))
        event.accept()

    def closeEvent(self, event) -> None:
        self.close_requested.emit()
        super().closeEvent(event)

    close_requested = pyqtSignal()


def virtual_screen_bounds() -> ScreenBounds:
    screens = QGuiApplication.screens()
    left = min(screen.geometry().left() for screen in screens)
    top = min(screen.geometry().top() for screen in screens)
    right = max(screen.geometry().right() for screen in screens)
    bottom = max(screen.geometry().bottom() for screen in screens)
    return ScreenBounds(left, top, right - left + 1, bottom - top + 1)


def main() -> int:
    app = QApplication(sys.argv)
    bounds = virtual_screen_bounds()
    overlay = Overlay(bounds)
    monitor = MonitorThread(bounds, overlay.geometry_tuple)
    overlay.toggle_button.clicked.connect(
        lambda: monitor.set_active(not monitor._active.is_set())
    )
    monitor.active_changed.connect(
        lambda active: overlay.toggle_button.setText("Pause" if active else "Resume")
    )
    monitor.translated.connect(overlay.output.setText)
    monitor.status.connect(overlay.state.setText)
    monitor.failed.connect(overlay.output.setText)
    overlay.close_button.clicked.connect(overlay.close)
    overlay.close_requested.connect(monitor.requestInterruption)
    overlay.close_requested.connect(monitor.quit)
    overlay.show()
    monitor.start()
    app.aboutToQuit.connect(monitor.requestInterruption)
    app.aboutToQuit.connect(monitor.quit)
    app.aboutToQuit.connect(lambda: monitor.wait(3000))
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
