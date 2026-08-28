"""Unit tests for dds_converter.

Synthetic DDS byte sequences are built from scratch so no binary fixtures need
to be committed.  The helpers at the bottom of this file produce minimal but
spec-compliant DDS headers; Pillow's DDS reader accepts them.
"""
import io
import struct

from PIL import Image

from fsmodmanager.core.parser.dds_converter import convert_icon


# ---------------------------------------------------------------------------
# Synthetic DDS factories
# ---------------------------------------------------------------------------

def _dds_header(
    width: int,
    height: int,
    fourcc: bytes | None,
    rgb_flags: int = 0,
    bit_count: int = 0,
    r_mask: int = 0,
    g_mask: int = 0,
    b_mask: int = 0,
    a_mask: int = 0,
    linear_size: int = 0,
) -> bytearray:
    """Build a 128-byte DDS header."""
    hdr = bytearray(128)
    hdr[0:4] = b"DDS "
    struct.pack_into("<I", hdr, 4, 124)           # dwSize
    struct.pack_into("<I", hdr, 8, 0x000A1007)    # dwFlags (standard set)
    struct.pack_into("<I", hdr, 12, height)
    struct.pack_into("<I", hdr, 16, width)
    struct.pack_into("<I", hdr, 20, linear_size)
    struct.pack_into("<I", hdr, 28, 1)            # dwMipMapCount
    struct.pack_into("<I", hdr, 76, 32)           # pixel format dwSize
    if fourcc is not None:
        struct.pack_into("<I", hdr, 80, 0x4)      # DDPF_FOURCC
        hdr[84:88] = fourcc
    else:
        struct.pack_into("<I", hdr, 80, rgb_flags)
        struct.pack_into("<I", hdr, 88, bit_count)
        struct.pack_into("<I", hdr, 92, r_mask)
        struct.pack_into("<I", hdr, 96, g_mask)
        struct.pack_into("<I", hdr, 100, b_mask)
        struct.pack_into("<I", hdr, 104, a_mask)
    struct.pack_into("<I", hdr, 108, 0x1000)      # DDSCAPS_TEXTURE
    return hdr


def make_bc1_dds(width: int = 4, height: int = 4) -> bytes:
    """Minimal BC1 / DXT1 DDS (no alpha)."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    hdr = _dds_header(width, height, b"DXT1", linear_size=bw * bh * 8)
    block = struct.pack("<HH4B", 0xF800, 0x001F, 0x00, 0x00, 0x00, 0x00)
    return bytes(hdr) + block * (bw * bh)


def make_bc3_dds(width: int = 4, height: int = 4) -> bytes:
    """Minimal BC3 / DXT5 DDS (with alpha)."""
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    hdr = _dds_header(width, height, b"DXT5", linear_size=bw * bh * 16)
    alpha_block = struct.pack("<BB6B", 0xFF, 0x00, 0, 0, 0, 0, 0, 0)
    color_block = struct.pack("<HH4B", 0xF800, 0x001F, 0x00, 0x00, 0x00, 0x00)
    return bytes(hdr) + (alpha_block + color_block) * (bw * bh)


def make_uncompressed_rgba_dds(width: int = 4, height: int = 4) -> bytes:
    """Minimal uncompressed A8R8G8B8 DDS."""
    hdr = _dds_header(
        width, height, fourcc=None,
        rgb_flags=0x41, bit_count=32,
        r_mask=0x00FF0000, g_mask=0x0000FF00, b_mask=0x000000FF, a_mask=0xFF000000,
        linear_size=width * height * 4,
    )
    return bytes(hdr) + b"\x00\x80\xFF\xFF" * (width * height)


def make_png_bytes(width: int = 4, height: int = 4) -> bytes:
    """Create a minimal PNG in memory."""
    img = Image.new("RGBA", (width, height), color=(255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests – successful conversion
# ---------------------------------------------------------------------------

class TestConvertDds:
    def test_bc1_returns_image(self) -> None:
        assert isinstance(convert_icon(make_bc1_dds(), "icon.dds"), Image.Image)

    def test_bc1_dimensions(self) -> None:
        img = convert_icon(make_bc1_dds(8, 8), "icon.dds")
        assert img.size == (8, 8)

    def test_bc3_returns_image(self) -> None:
        assert isinstance(convert_icon(make_bc3_dds(), "icon.dds"), Image.Image)

    def test_bc3_dimensions(self) -> None:
        assert convert_icon(make_bc3_dds(4, 4), "icon.dds").size == (4, 4)

    def test_uncompressed_rgba_returns_image(self) -> None:
        assert isinstance(convert_icon(make_uncompressed_rgba_dds(), "icon.dds"), Image.Image)


class TestConvertPng:
    def test_png_returns_image(self) -> None:
        assert isinstance(convert_icon(make_png_bytes(), "icon.png"), Image.Image)

    def test_png_dimensions(self) -> None:
        assert convert_icon(make_png_bytes(8, 16), "icon.png").size == (8, 16)

    def test_png_in_subdirectory_path(self) -> None:
        """icon_filename may contain subdirectory (e.g. 'store/icon.png')."""
        assert isinstance(convert_icon(make_png_bytes(), "store/icon.png"), Image.Image)


# ---------------------------------------------------------------------------
# Tests – graceful None fallback (caller shows placeholder)
# ---------------------------------------------------------------------------

class TestFallbackToNone:
    def test_unknown_extension_returns_none(self) -> None:
        assert convert_icon(b"\x00" * 64, "icon.tga") is None

    def test_corrupt_dds_returns_none(self) -> None:
        assert convert_icon(b"\x00" * 16, "icon.dds") is None

    def test_corrupt_png_returns_none(self) -> None:
        assert convert_icon(b"\x00" * 16, "icon.png") is None

    def test_empty_data_returns_none(self) -> None:
        assert convert_icon(b"", "icon.dds") is None

    def test_no_extension_returns_none(self) -> None:
        assert convert_icon(make_png_bytes(), "icon") is None
