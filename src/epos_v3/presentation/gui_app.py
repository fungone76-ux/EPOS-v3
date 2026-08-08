"""Optional PySide6 desktop GUI for EPOS v3.1."""

from __future__ import annotations

import argparse
import asyncio
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.persistence.json_store import JsonStore

from .gui_controller import GuiController
from .gui_widgets import ImagePreviewLabel, ImageViewer, SubmitTextEdit


STYLESHEET = """
QMainWindow, QWidget { background:#16181d; color:#eceff4; font-size:15px; }
QFrame#panel { background:#20232a; border:1px solid #343944; border-radius:10px; }
QLabel#title { font-size:20px; font-weight:700; padding:4px; }
QTextEdit { background:#111318; border:1px solid #3a404d; border-radius:8px; padding:10px; }
QPushButton { background:#3b6ea8; border:0; border-radius:8px; padding:10px 16px; font-weight:700; }
QPushButton#secondary { background:#343944; }
QPushButton:disabled { background:#343841; color:#777; }
"""


class WorkerBridge(QObject):
    """Deliver worker-thread results safely to the GUI thread."""

    result_ready = Signal(object)


class EposWindow(QMainWindow):
    """Three-panel EPOS desktop window: State | Scene | Story."""

    def __init__(self, controller: GuiController, state: WorldState) -> None:
        """Create the desktop application window."""
        super().__init__()
        self.controller = controller
        self.state = state
        self.bridge = WorkerBridge()
        self.bridge.result_ready.connect(self._on_result)
        self.busy = False
        self.current_image: Path | None = None
        self.viewer: ImageViewer | None = None
        self.last_prompt = ""
        self.last_negative = ""
        self.last_loras: object = []
        self.setWindowTitle(f"EPOS v3.1 — {state.session_id}")
        self.resize(1450, 850)
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(STYLESHEET)
        self._build_ui()
        self._refresh_state()

    def _panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("title")
        layout.addWidget(heading)
        return frame, layout

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_state_panel())
        splitter.addWidget(self._build_scene_panel())
        splitter.addWidget(self._build_story_panel())
        splitter.setSizes([360, 520, 570])
        self.setCentralWidget(splitter)

    def _build_state_panel(self) -> QWidget:
        frame, layout = self._panel("Situazione")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: 0; }")
        scroll_body = QWidget()
        scroll_body.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_body)
        scroll_layout.setContentsMargins(2, 2, 8, 2)
        self.state_text = QLabel()
        self.state_text.setTextFormat(Qt.TextFormat.RichText)
        self.state_text.setWordWrap(True)
        self.state_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.state_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.state_text.setStyleSheet("background: transparent;")
        scroll_layout.addWidget(self.state_text)
        scroll_layout.addStretch(1)
        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, 1)
        self.advance_button = QPushButton("Avanza")
        self.advance_button.clicked.connect(self._advance)
        layout.addWidget(self.advance_button)
        self.resume_button = QPushButton("Resume")
        self.resume_button.setObjectName("secondary")
        self.resume_button.clicked.connect(self._resume)
        layout.addWidget(self.resume_button)
        return frame

    def _build_scene_panel(self) -> QWidget:
        frame, layout = self._panel("Scena")
        self.image = ImagePreviewLabel("Immagine non generata")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(360, 360)
        self.image.setStyleSheet("background:#0d0f13;border:1px solid #3a404d;border-radius:8px;")
        self.image.clicked.connect(self._open_image)
        layout.addWidget(self.image, 3)
        self.prompt_button = QPushButton("Mostra prompt visuale")
        self.prompt_button.setObjectName("secondary")
        self.prompt_button.clicked.connect(self._toggle_prompt)
        layout.addWidget(self.prompt_button)
        self.prompt_debug = QTextEdit()
        self.prompt_debug.setReadOnly(True)
        self.prompt_debug.setVisible(False)
        layout.addWidget(self.prompt_debug, 2)
        return frame

    def _build_story_panel(self) -> QWidget:
        frame, layout = self._panel("Storia")
        self.story = QTextEdit()
        self.story.setReadOnly(True)
        layout.addWidget(self.story, 1)
        self.input = SubmitTextEdit()
        self.input.setPlaceholderText("Scrivi liberamente ciò che fai o dici…")
        self.input.setMaximumHeight(100)
        self.input.submit_requested.connect(self._submit)
        layout.addWidget(self.input)
        row = QHBoxLayout()
        self.send_button = QPushButton("Invia")
        self.send_button.clicked.connect(self._submit)
        row.addWidget(self.send_button)
        layout.addLayout(row)
        return frame

    def _submit(self) -> None:
        if self.busy:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self._append(f"\nTU > {text}\n")
        self._run("turn", lambda: self.controller.play(text))

    def _advance(self) -> None:
        if not self.busy:
            self._run("advance", self.controller.advance)

    def _resume(self) -> None:
        if not self.busy:
            self._run("resume", self.controller.resume)

    def _run(self, kind: str, operation) -> None:
        self._set_busy(True)

        def worker() -> None:
            try:
                result = asyncio.run(operation())
                self.bridge.result_ready.emit((kind, result, None))
            except Exception as exc:
                self.bridge.result_ready.emit((kind, None, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, payload: object) -> None:
        kind, result, error = payload
        if error is not None:
            self._append(f"\n[ERRORE {kind}: {error}]\n")
            self._set_busy(False)
            return
        if kind == "advance":
            self._append(f"\n⏩ Giorno {result['day']} — {result['phase']}\n")
            if result.get("narration"):
                self._append(str(result["narration"]) + "\n")
        else:
            self._append("\n📖 " + str(result.get("narration", "")) + "\n")
            self._update_visual(result)
        asyncio.run(self._reload_state())
        self._set_busy(False)

    async def _reload_state(self) -> None:
        self.state = await self.controller.state()
        self._refresh_state()

    def _update_visual(self, result: dict[str, object]) -> None:
        self.last_prompt = str(result.get("visual_prompt") or "")
        self.last_negative = str(result.get("visual_negative_prompt") or "")
        self.last_loras = result.get("visual_loras", [])
        visual_error = str(result.get("visual_error") or "")
        debug_text = (
            f"POSITIVE\n{self.last_prompt or '[nessun prompt compilato]'}"
            f"\n\nNEGATIVE\n{self.last_negative or '[nessun negative prompt compilato]'}"
            f"\n\nLoRA\n{self.last_loras}"
        )
        if visual_error:
            debug_text += f"\n\nERRORE VISUALE\n{visual_error}"
        self.prompt_debug.setPlainText(debug_text)
        image_path = result.get("image_path")
        if isinstance(image_path, str) and image_path:
            path = Path(image_path)
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.current_image = path
                self.image.setPixmap(
                    pixmap.scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

    def _toggle_prompt(self) -> None:
        visible = not self.prompt_debug.isVisible()
        self.prompt_debug.setVisible(visible)
        self.prompt_button.setText("Nascondi prompt visuale" if visible else "Mostra prompt visuale")

    def _open_image(self) -> None:
        if self.current_image is None or not self.current_image.exists():
            return
        self.viewer = ImageViewer(self.current_image, self)
        self.viewer.show()

    def _refresh_state(self) -> None:
        self.state_text.setText(self.controller.state_view(self.state))

    def _append(self, text: str) -> None:
        self.story.moveCursor(QTextCursor.MoveOperation.End)
        self.story.insertPlainText(text)
        self.story.ensureCursorVisible()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_button.setEnabled(not busy)
        self.advance_button.setEnabled(not busy)
        self.resume_button.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.statusBar().showMessage("Elaborazione…" if busy else "Pronta")


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for the desktop UI."""
    parser = argparse.ArgumentParser(description="EPOS v3.1 desktop GUI")
    parser.add_argument("--worldpack", type=Path, required=True)
    parser.add_argument("--session-id", default="gui")
    return parser


def main_sync() -> None:
    """Launch the optional PySide6 desktop GUI."""
    load_dotenv()
    args = build_parser().parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    store = JsonStore("./data/sessions")
    controller = GuiController(
        store=store,
        worldpack_path=args.worldpack,
        session_id=args.session_id,
    )
    state = asyncio.run(controller.initialize())
    window = EposWindow(controller, state)
    window.show()
    app.exec()


if __name__ == "__main__":
    main_sync()
