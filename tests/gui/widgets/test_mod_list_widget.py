"""Tests for ModListWidget / ModListModel / ModDelegate."""
import zipfile
from pathlib import Path

import pytest

from fsmodmanager.core.model.mod import Mod
from fsmodmanager.gui.widgets.mod_list_widget import (
    ModListModel,
    ModListWidget,
    _resolve_icon_entry,
)

# ── helpers ───────────────────────────────────────────────────────────────────

_MOD_DESC = """\
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<modDesc descVersion="72">
    <author>{author}</author>
    <version>{version}</version>
    <title><en>{title}</en></title>
    <iconFilename>icon.png</iconFilename>
</modDesc>"""


def _make_zip(directory: Path, filename: str, title: str, author: str = "A", version: str = "1.0") -> Path:
    p = directory / filename
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("modDesc.xml", _MOD_DESC.format(title=title, author=author, version=version))
        # tiny 1×1 white PNG as icon
        import io
        from PIL import Image
        img = Image.new("RGBA", (1, 1), (255, 255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        zf.writestr("icon.png", buf.getvalue())
    return p


def _mod(
    filename: str,
    title: str = "Title",
    author: str = "Author",
    version: str = "1.0",
    is_map: bool = False,
) -> Mod:
    return Mod(
        filename=filename, title=title, author=author, version=version,
        icon_filename="icon.png", is_map=is_map,
    )


def _make_zip_with_icon_entry(
    directory: Path, filename: str, icon_entry: str, title: str = "Title"
) -> Path:
    """Build a mod ZIP whose modDesc.xml <iconFilename> is "icon.png", but the
    actual icon asset is stored under `icon_entry` (e.g. "icon.dds") – the
    real-world mismatch some FS mods ship (declared .png, shipped .dds)."""
    import io

    from PIL import Image

    p = directory / filename
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("modDesc.xml", _MOD_DESC.format(title=title, author="A", version="1.0"))
        img = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
        buf = io.BytesIO()
        fmt = "DDS" if icon_entry.lower().endswith(".dds") else "PNG"
        img.save(buf, format=fmt)
        zf.writestr(icon_entry, buf.getvalue())
    return p


# ── ModListModel ──────────────────────────────────────────────────────────────

class TestModListModel:
    def test_empty_by_default(self, qtbot) -> None:
        model = ModListModel()
        assert model.rowCount() == 0

    def test_set_mods_updates_row_count(self, qtbot) -> None:
        model = ModListModel()
        model.set_mods([_mod("A.zip"), _mod("B.zip")])
        assert model.rowCount() == 2

    def test_display_role_returns_title(self, qtbot) -> None:
        from PySide6.QtCore import Qt, QModelIndex
        model = ModListModel()
        model.set_mods([_mod("A.zip", title="My Mod")])
        idx = model.index(0)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "My Mod"

    def test_user_role_returns_mod(self, qtbot) -> None:
        from PySide6.QtCore import Qt
        mod = _mod("A.zip")
        model = ModListModel()
        model.set_mods([mod])
        idx = model.index(0)
        assert model.data(idx, Qt.ItemDataRole.UserRole) is mod

    def test_map_mod_has_tooltip(self, qtbot) -> None:
        from PySide6.QtCore import Qt
        model = ModListModel()
        model.set_mods([_mod("Map.zip", is_map=True)])
        idx = model.index(0)
        tooltip = model.data(idx, Qt.ItemDataRole.ToolTipRole)
        assert tooltip is not None
        assert "Karte" in tooltip

    def test_regular_mod_has_no_tooltip(self, qtbot) -> None:
        from PySide6.QtCore import Qt
        model = ModListModel()
        model.set_mods([_mod("Regular.zip", is_map=False)])
        idx = model.index(0)
        assert model.data(idx, Qt.ItemDataRole.ToolTipRole) is None

    def test_invalid_name_mod_has_tooltip(self, qtbot) -> None:
        from PySide6.QtCore import Qt
        model = ModListModel()
        model.set_mods([_mod("Invalid Name (1).zip")])
        idx = model.index(0)
        tooltip = model.data(idx, Qt.ItemDataRole.ToolTipRole)
        assert tooltip is not None
        assert "Invalid mod name" in tooltip

    def test_invalid_name_tooltip_takes_priority_over_map_tooltip(self, qtbot) -> None:
        """A mod can't realistically be both, but if it were, the actionable
        naming problem should be what the user sees, not the map notice."""
        from PySide6.QtCore import Qt
        model = ModListModel()
        model.set_mods([_mod("Invalid Name (1).zip", is_map=True)])
        idx = model.index(0)
        tooltip = model.data(idx, Qt.ItemDataRole.ToolTipRole)
        assert "Invalid mod name" in tooltip

    def test_mods_dropped_signal(self, qtbot) -> None:
        from PySide6.QtCore import QByteArray, QMimeData, Qt, QModelIndex
        model = ModListModel()
        model.set_mods([_mod("A.zip"), _mod("B.zip")])

        mime = QMimeData()
        mime.setData("application/x-fsmod-filenames", QByteArray(b"A.zip\nB.zip"))

        with qtbot.waitSignal(model.mods_dropped, timeout=1000) as blocker:
            model.dropMimeData(mime, Qt.DropAction.MoveAction, -1, -1, QModelIndex())

        assert set(blocker.args[0]) == {"A.zip", "B.zip"}

    def test_mime_data_encodes_filenames(self, qtbot) -> None:
        model = ModListModel()
        model.set_mods([_mod("A.zip"), _mod("B.zip")])
        indexes = [model.index(0), model.index(1)]
        mime = model.mimeData(indexes)
        raw = bytes(mime.data("application/x-fsmod-filenames")).decode()
        assert "A.zip" in raw
        assert "B.zip" in raw


# ── ModListWidget ─────────────────────────────────────────────────────────────

class TestModListWidget:
    def test_widget_shows_mods(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([_mod("A.zip"), _mod("B.zip")])
        assert widget.list_model.rowCount() == 2

    def test_selected_mods_returns_selection(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        mods = [_mod("A.zip"), _mod("B.zip")]
        widget.set_mods(mods)
        widget.show()
        # Select first item programmatically
        idx = widget.list_model.index(0)
        widget.setCurrentIndex(idx)
        selected = widget.selected_mods()
        assert len(selected) == 1
        assert selected[0].filename == "A.zip"

    def test_filter_hides_non_matching_mods(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([
            _mod("FS25_Alpha.zip", title="Alpha Mod", author="Dev"),
            _mod("FS25_Beta.zip",  title="Beta Mod",  author="Dev"),
        ])
        widget.set_filter("alpha")
        assert widget.list_model.rowCount() == 1
        assert widget.list_model.mods()[0].filename == "FS25_Alpha.zip"

    def test_filter_matches_title(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([
            _mod("A.zip", title="Precision Farming", author="Dev"),
            _mod("B.zip", title="Other Mod",         author="Dev"),
        ])
        widget.set_filter("precision")
        assert widget.list_model.rowCount() == 1

    def test_filter_matches_author(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([
            _mod("A.zip", title="Mod X", author="Giants"),
            _mod("B.zip", title="Mod Y", author="Someone"),
        ])
        widget.set_filter("giants")
        assert widget.list_model.rowCount() == 1

    def test_filter_is_case_insensitive(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([_mod("FS25_BigMod.zip", title="Big Mod", author="Dev")])
        widget.set_filter("BIG")
        assert widget.list_model.rowCount() == 1

    def test_filter_cleared_shows_all(self, qtbot) -> None:
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([
            _mod("X1.zip", title="Mod X1", author="Dev"),
            _mod("X2.zip", title="Mod X2", author="Dev"),
            _mod("X3.zip", title="Mod X3", author="Dev"),
        ])
        widget.set_filter("X1")
        assert widget.list_model.rowCount() == 1
        widget.set_filter("")
        assert widget.list_model.rowCount() == 3

    def test_set_mods_reapplies_active_filter(self, qtbot) -> None:
        """When the mod list is replaced, an active filter is preserved."""
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_mods([_mod("FS25_Krone.zip", title="Krone", author="Dev"),
                         _mod("FS25_Claas.zip", title="Claas", author="Dev")])
        widget.set_filter("krone")
        # Replace the list – filter must still apply to the new list
        widget.set_mods([_mod("FS25_Krone.zip",  title="Krone",  author="Dev"),
                         _mod("FS25_Fendt.zip",  title="Fendt",  author="Dev"),
                         _mod("FS25_Deutz.zip",  title="Deutz",  author="Dev")])
        assert widget.list_model.rowCount() == 1
        assert widget.list_model.mods()[0].filename == "FS25_Krone.zip"

    def test_icon_loaded_from_zip(self, qtbot, tmp_path) -> None:
        _make_zip(tmp_path, "FS25_Test.zip", "Test Mod")
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_collection_dir(tmp_path)
        widget.set_mods([_mod("FS25_Test.zip")])
        # Trigger icon load via DecorationRole
        from PySide6.QtCore import Qt
        idx = widget.list_model.index(0)
        pixmap = widget.list_model.data(idx, Qt.ItemDataRole.DecorationRole)
        assert pixmap is not None
        assert not pixmap.isNull()

    def test_icon_loaded_when_png_declared_but_dds_shipped(self, qtbot, tmp_path) -> None:
        """Real-world mismatch (e.g. FS25_BresselUndLadeBumperPack.zip):
        modDesc.xml declares "icon.png" but the ZIP only contains
        "icon.dds". The icon must still resolve and render, not fall back
        to the "N/A" placeholder."""
        _make_zip_with_icon_entry(tmp_path, "FS25_Test.zip", "icon.dds")
        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.set_collection_dir(tmp_path)
        widget.set_mods([_mod("FS25_Test.zip")])  # icon_filename="icon.png"

        from PySide6.QtCore import Qt
        idx = widget.list_model.index(0)
        pixmap = widget.list_model.data(idx, Qt.ItemDataRole.DecorationRole)
        assert pixmap is not None
        assert not pixmap.isNull()

    def test_map_mod_row_rendered_with_amber_background(self, qtbot) -> None:
        """Rendering-level check (not just role plumbing) that map mods are
        actually painted with the highlight color, unselected/unhovered."""
        from fsmodmanager.gui.widgets.mod_list_widget import _MAP_MOD_COLOR

        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.resize(320, 100)
        widget.set_mods([_mod("Map.zip", is_map=True, title="Map Mod")])
        widget.show()
        qtbot.waitExposed(widget)

        img = widget.grab().toImage()
        # Sample near the right edge of the first row - past the text
        # column, still inside the row's fill area.
        color = img.pixelColor(img.width() - 10, 10)
        assert (color.red(), color.green(), color.blue()) == (
            _MAP_MOD_COLOR.red(), _MAP_MOD_COLOR.green(), _MAP_MOD_COLOR.blue(),
        )

    def test_regular_mod_row_not_rendered_with_amber_background(self, qtbot) -> None:
        from fsmodmanager.gui.widgets.mod_list_widget import _MAP_MOD_COLOR

        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.resize(320, 100)
        widget.set_mods([_mod("Regular.zip", is_map=False, title="Regular Mod")])
        widget.show()
        qtbot.waitExposed(widget)

        img = widget.grab().toImage()
        color = img.pixelColor(img.width() - 10, 10)
        assert (color.red(), color.green(), color.blue()) != (
            _MAP_MOD_COLOR.red(), _MAP_MOD_COLOR.green(), _MAP_MOD_COLOR.blue(),
        )

    def test_invalid_name_mod_row_rendered_with_red_background(self, qtbot) -> None:
        from fsmodmanager.gui.widgets.mod_list_widget import _INVALID_NAME_COLOR

        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.resize(320, 100)
        widget.set_mods([_mod("Invalid Name (1).zip", title="Broken Mod")])
        widget.show()
        qtbot.waitExposed(widget)

        img = widget.grab().toImage()
        color = img.pixelColor(img.width() - 10, 10)
        assert (color.red(), color.green(), color.blue()) == (
            _INVALID_NAME_COLOR.red(), _INVALID_NAME_COLOR.green(), _INVALID_NAME_COLOR.blue(),
        )

    def test_invalid_name_takes_priority_over_map_background(self, qtbot) -> None:
        from fsmodmanager.gui.widgets.mod_list_widget import _INVALID_NAME_COLOR

        widget = ModListWidget()
        qtbot.addWidget(widget)
        widget.resize(320, 100)
        widget.set_mods([_mod("Invalid Name (1).zip", is_map=True, title="Broken Map")])
        widget.show()
        qtbot.waitExposed(widget)

        img = widget.grab().toImage()
        color = img.pixelColor(img.width() - 10, 10)
        assert (color.red(), color.green(), color.blue()) == (
            _INVALID_NAME_COLOR.red(), _INVALID_NAME_COLOR.green(), _INVALID_NAME_COLOR.blue(),
        )


# ── icon entry resolution ────────────────────────────────────────────────────

class TestResolveIconEntry:
    def test_exact_match_wins(self) -> None:
        names = ["icon.png", "icon.dds"]
        assert _resolve_icon_entry(names, "icon.png") == "icon.png"

    def test_png_declared_dds_shipped(self) -> None:
        """Matches Java's Main.createMod(), which unconditionally rewrites
        a declared ".png" iconFilename to ".dds" before the ZIP lookup –
        the common real-world FS modding convention."""
        names = ["modDesc.xml", "icon.dds"]
        assert _resolve_icon_entry(names, "icon.png") == "icon.dds"

    def test_dds_declared_png_shipped(self) -> None:
        """Reverse direction – not handled by Java, added robustness."""
        names = ["modDesc.xml", "icon.png"]
        assert _resolve_icon_entry(names, "icon.dds") == "icon.png"

    def test_case_insensitive_fallback(self) -> None:
        names = ["Icon.DDS"]
        assert _resolve_icon_entry(names, "icon.png") == "Icon.DDS"

    def test_no_match_returns_none(self) -> None:
        names = ["modDesc.xml", "other.dds"]
        assert _resolve_icon_entry(names, "icon.png") is None

    def test_no_extension_no_match_returns_none(self) -> None:
        names = ["modDesc.xml"]
        assert _resolve_icon_entry(names, "icon") is None


# ── MainWindow smoke test ─────────────────────────────────────────────────────

class TestMainWindowSmoke:
    def test_window_opens_without_crash(self, qtbot, tmp_path) -> None:
        from fsmodmanager.core.service.collection_service import CollectionService
        from fsmodmanager.core.service.config_service import ConfigService
        from fsmodmanager.core.service.link_service import LinkService
        from fsmodmanager.core.service.settings_service import SettingsService
        from fsmodmanager.core.model.settings import Settings
        from fsmodmanager.gui.main_window import MainWindow
        from fsmodmanager.gui.viewmodels.main_viewmodel import MainViewModel

        source = tmp_path / "mods"
        collection = tmp_path / "collection"
        source.mkdir()
        collection.mkdir()
        data_dir = tmp_path / "data"
        configs_dir = tmp_path / "configs"

        settings = Settings(
            source_mod_folder=str(source),
            mod_collection_folder=str(collection),
            savegame_path=str(tmp_path),
            # Avoids the blocking "Konfigurationen aus Savegames erstellen?"
            # QMessageBox that _do_initialize() would otherwise show – nothing
            # answers it in a headless test, so it would hang forever.
            savegames_read=True,
        )
        svc = SettingsService(data_dir=data_dir)
        svc.save(settings)

        vm = MainViewModel(
            settings_service=SettingsService(data_dir=data_dir),
            config_service=ConfigService(configs_dir=configs_dir),
            link_service=LinkService(),
            collection_service=CollectionService(),
        )
        window = MainWindow(view_model=vm)
        qtbot.addWidget(window)
        # Wait for the QTimer.singleShot(0) initialization to complete
        with qtbot.waitSignal(vm.available_mods_changed, timeout=2000):
            window.show()
        qtbot.waitExposed(window)
        assert window.isVisible()
