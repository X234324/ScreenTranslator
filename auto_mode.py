"""Automatic, offline screen translator for Windows, based on Skylark."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
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
from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
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


@dataclass(frozen=True)
class TextRegion:
    text: str
    left: int
    top: int
    width: int
    height: int
    translation: str = ""


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


def extract_text_regions(
    data: dict[str, list], left: int = 0, top: int = 0
) -> list[TextRegion]:
    paragraphs: dict[
        tuple[str, str, str], list[tuple[str, int, int, int, int, str]]
    ] = {}
    text_count = len(data.get("text", []))
    for index, raw_text in enumerate(data.get("text", [])):
        text = " ".join(str(raw_text).encode("ascii", errors="replace").decode("ascii").split())
        if len(text) < 2 or not re.search(r"[A-Za-z]", text):
            continue
        try:
            if float(data["conf"][index]) < 35:
                continue
            x = int(data["left"][index])
            y = int(data["top"][index])
            width = int(data["width"][index])
            height = int(data["height"][index])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        paragraph_key = tuple(
            str(data.get(field, [""] * text_count)[index])
            for field in ("block_num", "par_num", "page_num")
        )
        line_key = str(data.get("line_num", [""] * text_count)[index])
        paragraphs.setdefault(paragraph_key, []).append(
            (text, x, y, width, height, line_key)
        )

    regions: list[TextRegion] = []
    for words in paragraphs.values():
        lines: dict[str, list[tuple[str, int, int, int, int]]] = {}
        for word, x, y, width, height, line_key in words:
            lines.setdefault(line_key, []).append((word, x, y, width, height))
        ordered_lines = sorted(
            lines.values(),
            key=lambda line: min(word[2] for word in line),
        )
        line_texts = []
        for line in ordered_lines:
            line.sort(key=lambda word: word[1])
            line_texts.append(" ".join(word[0] for word in line))
        text = " ".join(line_texts)
        if len(text) < 3:
            continue
        x1 = min(word[1] for word in words)
        y1 = min(word[2] for word in words)
        x2 = max(word[1] + word[3] for word in words)
        y2 = max(word[2] + word[4] for word in words)
        regions.append(TextRegion(text, left + x1, top + y1, x2 - x1, y2 - y1))
    return sorted(regions, key=lambda region: (region.top, region.left))


def screen_changed(previous: np.ndarray | None, current: np.ndarray) -> bool:
    if previous is None or previous.shape != current.shape:
        return True
    difference = cv2.absdiff(previous, current)
    changed_pixels = cv2.countNonZero(cv2.threshold(
        difference, PIXEL_THRESHOLD, 255, cv2.THRESH_BINARY
    )[1])
    return changed_pixels / difference.size >= CHANGE_THRESHOLD


def screen_preview(frame: np.ndarray) -> np.ndarray:
    return cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)


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
    translated = pyqtSignal(object)
    status = pyqtSignal(str)
    failed = pyqtSignal(str)
    active_changed = pyqtSignal(bool)

    def __init__(
        self,
        bounds: ScreenBounds,
        overlay_regions: Callable[[], tuple[TextRegion, ...]],
    ) -> None:
        super().__init__()
        self.bounds = bounds
        self.overlay_regions = overlay_regions
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
        self.status.emit("正在监控屏幕…" if active else "已暂停")

    def run(self) -> None:
        try:
            tesseract = find_tesseract()
            if not tesseract:
                raise RuntimeError(
                    "未找到 Tesseract。请安装带英文数据的 Tesseract OCR，"
                    "或设置 TESSERACT_CMD 为 tesseract.exe 的完整路径。"
                )
            pytesseract.pytesseract.tesseract_cmd = tesseract
            self._translator = TranslationClient()
        except Exception as error:
            self.failed.emit(str(error))
            return

        previous: np.ndarray | None = None
        self.status.emit("正在监控屏幕…")
        try:
            with mss.MSS() as capture:
                monitor = capture.monitors[0]
                while not self.isInterruptionRequested():
                    if not self._active.wait(timeout=0.2):
                        continue
                    if self.isInterruptionRequested():
                        break
                    frame = np.asarray(capture.grab(monitor))
                    frame = self._exclude_translations(frame, monitor)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                    preview = screen_preview(gray)
                    comparison_previous = None
                    if previous is not None:
                        comparison_previous = screen_preview(
                            self._exclude_translations(previous.copy(), monitor)
                        )
                    previous = gray
                    if screen_changed(comparison_previous, preview):
                        data = pytesseract.image_to_data(
                            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)),
                            lang="eng",
                            config="--oem 3 --psm 11",
                            output_type=pytesseract.Output.DICT,
                        )
                        regions = extract_text_regions(
                            data,
                            monitor["left"],
                            monitor["top"],
                        )
                        if regions:
                            self._translate_regions(regions)
                    else:
                        previous = gray
                    self._poll_wake.clear()
                    if self._active.is_set() and not self.isInterruptionRequested():
                        self._poll_wake.wait(timeout=POLL_INTERVAL_SECONDS)
        except Exception as error:
            self.failed.emit(f"Screen monitoring stopped: {error}")
        finally:
            if self._translator is not None:
                self._translator.close()

    def _exclude_translations(self, frame: np.ndarray, monitor: dict[str, int]) -> np.ndarray:
        scale_x = frame.shape[1] / monitor["width"]
        scale_y = frame.shape[0] / monitor["height"]
        for region in self.overlay_regions():
            x1 = max(0, round((region.left - monitor["left"]) * scale_x))
            y1 = max(0, round((region.top - monitor["top"]) * scale_y))
            x2 = min(
                frame.shape[1],
                round((region.left + region.width - monitor["left"]) * scale_x),
            )
            y2 = min(
                frame.shape[0],
                round((region.top + region.height - monitor["top"]) * scale_y),
            )
            if x2 > x1 and y2 > y1:
                frame[y1:y2, x1:x2] = 255
        return frame

    def _translate_regions(self, regions: list[TextRegion]) -> None:
        if not regions:
            return

        translated_regions: list[TextRegion] = []
        try:
            for region in regions:
                key = text_key(region.text, "en")
                if key in self._text_cache:
                    translation = self._text_cache[key]
                    self._text_cache.move_to_end(key)
                else:
                    assert self._translator is not None
                    translation = self._translator.translate(region.text)
                    self._text_cache[key] = translation
                    if len(self._text_cache) > MAX_TRANSLATION_CACHE:
                        self._text_cache.popitem(last=False)
                translated_regions.append(
                    TextRegion(
                        region.text,
                        region.left,
                        region.top,
                        region.width,
                        region.height,
                        translation,
                    )
                )
            self.translated.emit(translated_regions)
        except Exception as error:
            self.failed.emit(f"Translation failed: {error}")


class TranslationOverlay(QWidget):
    def __init__(self, bounds: ScreenBounds) -> None:
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.bounds = bounds
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(bounds.left, bounds.top, bounds.width, bounds.height)
        self._labels: dict[str, QLabel] = {}
        self._regions: tuple[TextRegion, ...] = ()
        self.setStyleSheet(
            "QLabel { color: #202124; background-color: rgba(255, 255, 255, 250);"
            "border: 0; border-radius: 2px;"
            "padding: 1px 2px; font-size: 15px; font-weight: 400; }"
        )

    def mask_regions(self) -> tuple[TextRegion, ...]:
        return self._regions

    def set_translations(self, regions: list[TextRegion]) -> None:
        if not regions:
            return

        active_labels: set[str] = set()
        label_regions: list[TextRegion] = []
        occurrences: dict[str, int] = {}
        screen_right = self.bounds.left + self.bounds.width
        screen_bottom = self.bounds.top + self.bounds.height

        for region in regions:
            if not region.translation.strip() or region.width < 1:
                continue

            base_key = text_key(region.text, "en")
            occurrence = occurrences.get(base_key, 0)
            occurrences[base_key] = occurrence + 1
            key = f"{base_key}:{occurrence}"
            active_labels.add(key)
            label = self._labels.get(key)
            if label is None:
                label = QLabel(self)
                self._labels[key] = label
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            label.setTextInteractionFlags(Qt.NoTextInteraction)
            label_text = (
                f"<div>{html.escape(region.translation)}</div>"
                f'<div style="color:#5f6368;font-size:11px;">'
                f"{html.escape(region.text)}</div>"
            )
            if label.text() != label_text:
                label.setText(label_text)

            x = min(max(self.bounds.left, region.left), screen_right - 1)
            y = min(max(self.bounds.top, region.top), screen_bottom - 1)
            width = min(region.width, screen_right - x)
            label.setFixedWidth(width)
            height = max(region.height, label.heightForWidth(width) + 4)
            height = min(height, screen_bottom - y)
            label.setFixedHeight(height)
            label.move(x - self.bounds.left, y - self.bounds.top)
            label.show()
            label_regions.append(
                TextRegion(
                    region.text,
                    x,
                    y,
                    width,
                    height,
                    region.translation,
                )
            )

        for key, label in self._labels.items():
            if key not in active_labels:
                label.hide()
        self._regions = tuple(label_regions)


class TrayControls:
    def __init__(self, app: QApplication, monitor: MonitorThread) -> None:
        self.monitor = monitor
        self.tray = QSystemTrayIcon(QIcon(str(Path(__file__).with_name("skylark.ico"))))
        self.tray.setToolTip("实时屏幕翻译：正在监控屏幕")
        menu = QMenu()
        self.toggle_action = QAction("暂停翻译", menu)
        self.toggle_action.triggered.connect(self.toggle)
        menu.addAction(self.toggle_action)
        menu.addSeparator()
        exit_action = QAction("退出", menu)
        exit_action.triggered.connect(app.quit)
        menu.addAction(exit_action)
        self.tray.setContextMenu(menu)
        monitor.active_changed.connect(self.update_active)
        monitor.status.connect(self.tray.setToolTip)
        monitor.failed.connect(self.show_error)
        self.tray.show()

    def toggle(self) -> None:
        self.monitor.set_active(not self.monitor._active.is_set())

    def update_active(self, active: bool) -> None:
        self.toggle_action.setText("暂停翻译" if active else "继续翻译")

    def show_error(self, message: str) -> None:
        self.tray.showMessage("实时屏幕翻译", message)


def virtual_screen_bounds() -> ScreenBounds:
    screens = QGuiApplication.screens()
    left = min(screen.geometry().left() for screen in screens)
    top = min(screen.geometry().top() for screen in screens)
    right = max(screen.geometry().right() for screen in screens)
    bottom = max(screen.geometry().bottom() for screen in screens)
    return ScreenBounds(left, top, right - left + 1, bottom - top + 1)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    bounds = virtual_screen_bounds()
    overlay = TranslationOverlay(bounds)
    monitor = MonitorThread(bounds, overlay.mask_regions)
    tray = TrayControls(app, monitor)
    monitor.translated.connect(overlay.set_translations)
    overlay.show()
    monitor.start()
    app.aboutToQuit.connect(monitor.requestInterruption)
    app.aboutToQuit.connect(monitor.quit)
    app.aboutToQuit.connect(lambda: monitor.wait(3000))
    app.aboutToQuit.connect(tray.tray.hide)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
