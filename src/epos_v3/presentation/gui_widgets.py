"""Reusable Qt widgets for the optional EPOS desktop GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class SubmitTextEdit(QTextEdit):
    """Text input where Enter submits and Shift+Enter inserts a newline."""

    submit_requested = Signal()

    def keyPressEvent(self, event) -> None:
        """Handle Enter as submit while preserving Shift+Enter."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            event.accept()
            self.submit_requested.emit()
            return
        super().keyPressEvent(event)


class ImagePreviewLabel(QLabel):
    """Clickable image preview."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        """Emit clicked when the preview contains an image."""
        if event.button() == Qt.LeftButton and self.pixmap() is not None:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ZoomableGraphicsView(QGraphicsView):
    """Image view with mouse-wheel zoom and drag panning."""

    def __init__(self, scene: QGraphicsScene) -> None:
        """Configure pan and zoom behavior."""
        super().__init__(scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(Qt.black)

    def wheelEvent(self, event) -> None:
        """Zoom around the cursor."""
        self.scale(1.25 if event.angleDelta().y() > 0 else 0.8, 1.25 if event.angleDelta().y() > 0 else 0.8)
        event.accept()


class ImageViewer(QDialog):
    """Standalone image viewer with zoom and pan."""

    def __init__(self, path: Path, parent=None) -> None:
        """Open one generated image."""
        super().__init__(parent)
        self.setWindowTitle(path.name)
        self.resize(1100, 800)
        layout = QVBoxLayout(self)
        scene = QGraphicsScene(self)
        item = QGraphicsPixmapItem(QPixmap(str(path)))
        scene.addItem(item)
        view = ZoomableGraphicsView(scene)
        view.fitInView(item, Qt.KeepAspectRatio)
        layout.addWidget(view)
