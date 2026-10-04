#!/usr/bin/env python3
"""Compatibility entry point for generated board-cell patch planes.

Cell bitmap/screen/color patches are derived from the editable PNG game planes
by compile_c64_assets.py and are written only to build/generated-assets.
"""
from compile_c64_assets import main


if __name__ == "__main__":
    main()
