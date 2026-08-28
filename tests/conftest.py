import os

# Headless Qt rendering for CI and development without a display.
# Must be set before QApplication is created (i.e. before any test imports PySide6).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
