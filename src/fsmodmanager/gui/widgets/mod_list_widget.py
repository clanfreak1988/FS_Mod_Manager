"""Mod list widget: model, delegate, and view.

ModListModel  – QAbstractListModel backed by list[Mod], with lazy icon loading
               and drag-and-drop support (MoveAction, custom MIME type).
ModDelegate   – QStyledItemDelegate: icon (64 px) left, title/author/version/
               filename right.
ModListWidget – QListView preconfigured with the model and delegate.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from fsmodmanager.core.model.mod import Mod
from fsmodmanager.core.parser.dds_converter import convert_icon

# ── constants ────────────────────────────────────────────────────────────────

_MIME_TYPE = "application/x-fsmod-filenames"
_HIGHLIGHT_ROLE = Qt.ItemDataRole.UserRole + 1
_NEW_MOD_COLOR  = QColor("#c8e6c9")   # light green
_MAP_MOD_COLOR  = QColor("#ffe0b2")   # light amber – mods with <maps> in modDesc.xml
_INVALID_NAME_COLOR = QColor("#ffcdd2")  # light red – filename FS itself would reject
_ICON_SIZE = 64
_PADDING = 6                           # px between icon and text column
_TEXT_LEFT = _ICON_SIZE + _PADDING * 2
_ROW_VPAD = 8                          # vertical padding above/below the row content


# ── icon loading (called lazily from the model) ───────────────────────────────

def _resolve_icon_entry(names: list[str], icon_filename: str) -> str | None:
    """Find the ZIP entry that actually holds the mod's icon.

    <iconFilename> in modDesc.xml is not always accurate. A common, known FS
    modding convention: mods declare a ".png" icon but only ship the ".dds"
    asset under the same base name (Java's Main.createMod() hard-codes
    exactly this .png -> .dds rewrite before the ZIP lookup, unconditionally
    and in that direction only). The reverse also occurs in the wild
    (".dds" declared, only ".png" shipped), and some packaging tools
    produce entries whose casing doesn't match modDesc.xml.

    Tries, in order:
      1. The declared name verbatim.
      2. The same base name with the extension swapped between .png/.dds.
      3. A case-insensitive match against either of the above.

    Returns the matching entry name, or None if nothing matches.
    """
    if icon_filename in names:
        return icon_filename

    candidates = [icon_filename]
    lower = icon_filename.lower()
    if lower.endswith(".png"):
        candidates.append(icon_filename[: -len(".png")] + ".dds")
    elif lower.endswith(".dds"):
        candidates.append(icon_filename[: -len(".dds")] + ".png")

    for candidate in candidates:
        if candidate in names:
            return candidate

    lower_candidates = {c.lower() for c in candidates}
    for name in names:
        if name.lower() in lower_candidates:
            return name

    return None


def _load_pixmap(mod: Mod, collection_dir: Path) -> QPixmap | None:
    """Open the mod ZIP, extract the icon, convert it, return a scaled QPixmap."""
    if not mod.icon_filename:
        return None
    zip_path = collection_dir / mod.filename
    if not zip_path.exists():
        return None
    try:
        with zipfile.ZipFile(zip_path) as zf:
            entry = _resolve_icon_entry(zf.namelist(), mod.icon_filename)
            if entry is None:
                return None
            data = zf.read(entry)
    except Exception:
        return None

    pil_img = convert_icon(data, entry)
    if pil_img is None:
        return None

    try:
        pil_img = pil_img.convert("RGBA")
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        qimg = QImage.fromData(QByteArray(buf.getvalue()))
        if qimg.isNull():
            return None
        pixmap = QPixmap.fromImage(qimg)
        return pixmap.scaled(
            _ICON_SIZE,
            _ICON_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    except Exception:
        return None


# ── model ─────────────────────────────────────────────────────────────────────

class ModListModel(QAbstractListModel):
    """List model for Mod objects with lazy icon loading and drag-and-drop.

    Signals
    -------
    mods_dropped(list[str])
        Emitted when foreign mod filenames are dropped onto this model.
        The MainWindow forwards these to the ViewModel.
    """

    mods_dropped = Signal(list)   # list[str] – filenames of dragged mods

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._mods: list[Mod] = []
        self._icon_cache: dict[str, QPixmap | None] = {}
        self._collection_dir: Path | None = None
        self._highlighted: set[str] = set()

    # ── public API ────────────────────────────────────────────────────────────

    def set_collection_dir(self, path: Path | None) -> None:
        self._collection_dir = path
        self._icon_cache.clear()
        self.layoutChanged.emit()

    def set_mods(self, mods: list[Mod]) -> None:
        self.beginResetModel()
        self._mods = list(mods)
        self.endResetModel()

    def mods(self) -> list[Mod]:
        return list(self._mods)

    def mod_at(self, index: QModelIndex) -> Mod | None:
        if index.isValid() and 0 <= index.row() < len(self._mods):
            return self._mods[index.row()]
        return None

    def set_highlighted(self, filenames: set[str]) -> None:
        """Mark filenames as newly added (shown with coloured background)."""
        self._highlighted = set(filenames)
        self.layoutChanged.emit()

    # ── QAbstractListModel overrides ──────────────────────────────────────────

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._mods)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._mods)):
            return None
        mod = self._mods[index.row()]
        match role:
            case Qt.ItemDataRole.DisplayRole:
                return mod.title or mod.filename
            case Qt.ItemDataRole.UserRole:
                return mod
            case Qt.ItemDataRole.DecorationRole:
                return self._cached_pixmap(mod)
            case Qt.ItemDataRole.ToolTipRole:
                if mod.has_invalid_name:
                    return (
                        "Ungültiger Dateiname – der Farming Simulator lehnt diesen Mod "
                        "beim Laden ab (\"Invalid mod name\"). Erlaubt sind nur "
                        "Buchstaben, Ziffern und Unterstrich (_); das erste Zeichen "
                        "darf keine Ziffer sein."
                    )
                if mod.is_map:
                    return "Karte (Map-Mod) – enthält <maps> in modDesc.xml"
                return None
        if role == _HIGHLIGHT_ROLE:
            return mod.filename in self._highlighted
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return base | Qt.ItemFlag.ItemIsDropEnabled

    # ── drag-and-drop ─────────────────────────────────────────────────────────

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return [_MIME_TYPE]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        filenames = [
            self._mods[i.row()].filename
            for i in indexes
            if i.isValid() and 0 <= i.row() < len(self._mods)
        ]
        mime.setData(_MIME_TYPE, QByteArray("\n".join(filenames).encode()))
        return mime

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if not data.hasFormat(_MIME_TYPE):
            return False
        raw = bytes(data.data(_MIME_TYPE)).decode()
        filenames = [f for f in raw.split("\n") if f]
        if filenames:
            self.mods_dropped.emit(filenames)
        return True

    # ── private helpers ────────────────────────────────────────────────────────

    def _cached_pixmap(self, mod: Mod) -> QPixmap | None:
        if mod.filename not in self._icon_cache:
            if self._collection_dir is not None:
                self._icon_cache[mod.filename] = _load_pixmap(mod, self._collection_dir)
            else:
                return None
        return self._icon_cache[mod.filename]


# ── delegate ──────────────────────────────────────────────────────────────────

class ModDelegate(QStyledItemDelegate):
    """Renders each mod row as: [64×64 icon] [title bold] [author] [version] [filename]."""

    _TITLE_FONT: QFont | None = None
    _META_FONT: QFont | None = None

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        _, _, _, _, row_height = self._layout_metrics(option)
        return QSize(option.rect.width(), row_height)

    @classmethod
    def _layout_metrics(
        cls, option: QStyleOptionViewItem
    ) -> tuple[QFontMetrics, QFontMetrics, int, int, int]:
        """Shared font-metrics/row-height math, used by both sizeHint() and paint()
        so the two never drift apart.

        Returns (fm_title, fm_meta, title_h, meta_h, row_height).
        """
        fm_title = QFontMetrics(cls._title_font(option))
        fm_meta = QFontMetrics(cls._meta_font(option))
        title_h = fm_title.height()
        meta_h = fm_meta.height()
        # title + author + version + filename, stacked
        block_h = title_h + meta_h * 3
        row_height = max(_ICON_SIZE + _ROW_VPAD, block_h + _ROW_VPAD)
        return fm_title, fm_meta, title_h, meta_h, row_height

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()

        mod: Mod | None = index.data(Qt.ItemDataRole.UserRole)

        # Selection / invalid-name / new-mod / map-mod / hover background, in
        # that priority: selection always wins; an invalid filename is a real
        # problem the user needs to fix, so it outranks the merely-transient
        # "just collected" highlight and the permanent "this is a map"
        # marker; map mods still stand out against plain/hovered rows the
        # rest of the time.
        is_new = bool(index.data(_HIGHLIGHT_ROLE))
        is_map = bool(mod is not None and mod.is_map)
        is_invalid_name = bool(mod is not None and mod.has_invalid_name)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif is_invalid_name:
            painter.fillRect(option.rect, _INVALID_NAME_COLOR)
        elif is_new:
            painter.fillRect(option.rect, _NEW_MOD_COLOR)
        elif is_map:
            painter.fillRect(option.rect, _MAP_MOD_COLOR)
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, option.palette.alternateBase())

        if mod is None:
            painter.restore()
            return

        r = option.rect
        top = r.top() + (r.height() - _ICON_SIZE) // 2   # vertically centered

        # ── icon ──────────────────────────────────────────────────────────────
        pixmap: QPixmap | None = index.data(Qt.ItemDataRole.DecorationRole)
        icon_rect = QRect(r.left() + _PADDING, top, _ICON_SIZE, _ICON_SIZE)

        if pixmap is not None:
            # Center within the icon_rect in case the scaled pixmap is smaller
            px_x = icon_rect.left() + (icon_rect.width() - pixmap.width()) // 2
            px_y = icon_rect.top() + (icon_rect.height() - pixmap.height()) // 2
            painter.drawPixmap(px_x, px_y, pixmap)
        else:
            # Placeholder: grey box with "N/A"
            painter.fillRect(icon_rect, QColor(200, 200, 200))
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "N/A")

        # ── text column ───────────────────────────────────────────────────────
        text_left = r.left() + _TEXT_LEFT
        text_width = r.width() - _TEXT_LEFT - _PADDING

        # Chosen text color (invert on selection)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(option.palette.text().color())

        title_font = self._title_font(option)
        meta_font = self._meta_font(option)
        fm_title, fm_meta, title_h, meta_h, _ = self._layout_metrics(option)

        # Vertical layout: title / author / version / filename, packed together
        block_h = title_h + meta_h * 3
        text_top = r.top() + (r.height() - block_h) // 2

        title_rect = QRect(text_left, text_top, text_width, title_h)
        author_rect = QRect(text_left, text_top + title_h, text_width, meta_h)
        version_rect = QRect(text_left, text_top + title_h + meta_h, text_width, meta_h)
        filename_rect = QRect(text_left, text_top + title_h + meta_h * 2, text_width, meta_h)

        painter.setFont(title_font)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_title.elidedText(mod.title or mod.filename, Qt.TextElideMode.ElideRight, text_width),
        )

        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(option.palette.highlightedText().color())
        else:
            painter.setPen(QColor(100, 100, 100))

        painter.setFont(meta_font)
        if mod.author:
            painter.drawText(
                author_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                fm_meta.elidedText(mod.author, Qt.TextElideMode.ElideRight, text_width),
            )
        if mod.version:
            painter.drawText(
                version_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                mod.version,
            )
        painter.drawText(
            filename_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_meta.elidedText(mod.filename, Qt.TextElideMode.ElideRight, text_width),
        )

        painter.restore()

    # ── font helpers ──────────────────────────────────────────────────────────

    @classmethod
    def _title_font(cls, option: QStyleOptionViewItem) -> QFont:
        if cls._TITLE_FONT is None:
            f = QFont(option.font)
            f.setBold(True)
            cls._TITLE_FONT = f
        return cls._TITLE_FONT

    @classmethod
    def _meta_font(cls, option: QStyleOptionViewItem) -> QFont:
        if cls._META_FONT is None:
            f = QFont(option.font)
            f.setPointSize(max(f.pointSize() - 1, 7))
            cls._META_FONT = f
        return cls._META_FONT


# ── view ──────────────────────────────────────────────────────────────────────

class ModListWidget(QListView):
    """QListView preconfigured for mod display with drag-and-drop.

    The widget owns the full mod list internally.  A text filter can be
    applied via set_filter(); only mods whose filename, title, or author
    contain the filter string (case-insensitive) are then shown.  The
    underlying model always reflects the *filtered* view; the complete list
    is kept in _all_mods so that set_filter() can re-apply at any time.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = ModListModel(self)
        self.setModel(self._model)
        self.setItemDelegate(ModDelegate(self))

        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setUniformItemSizes(True)
        self.setSpacing(1)

        self._all_mods: list[Mod] = []
        self._filter_text: str = ""

    # ── convenience passthrough ───────────────────────────────────────────────

    @property
    def list_model(self) -> ModListModel:
        return self._model

    def set_collection_dir(self, path: Path | None) -> None:
        self._model.set_collection_dir(path)

    def set_mods(self, mods: list[Mod]) -> None:
        self._all_mods = list(mods)
        self._apply_filter()

    def set_filter(self, text: str) -> None:
        """Show only mods matching *text* in filename, title, or author."""
        self._filter_text = text
        self._apply_filter()

    def selected_mods(self) -> list[Mod]:
        mods = []
        for index in self.selectedIndexes():
            mod = self._model.mod_at(index)
            if mod is not None:
                mods.append(mod)
        return mods

    # ── private ───────────────────────────────────────────────────────────────

    def _apply_filter(self) -> None:
        if not self._filter_text:
            self._model.set_mods(self._all_mods)
            return
        lower = self._filter_text.lower()
        filtered = [
            m for m in self._all_mods
            if lower in m.filename.lower()
            or lower in (m.title or "").lower()
            or lower in (m.author or "").lower()
        ]
        self._model.set_mods(filtered)
