import io
from pathlib import Path

from PIL import Image


def convert_icon(data: bytes, filename: str) -> Image.Image | None:
    """Try to convert raw icon bytes to a PIL Image.

    - .dds / .png → decoded by Pillow.
    - Unsupported DDS variant, corrupt data, unknown extension → None.

    The caller is responsible for displaying a placeholder (e.g. "N/A")
    when None is returned.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in (".dds", ".png"):
        return None

    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # force decode so errors surface here, not later
        return img
    except Exception:
        return None
