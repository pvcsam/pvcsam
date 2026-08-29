#!/usr/bin/env python3
"""Prepare a photo for ASCII conversion.

A flatly-lit or dark-backgrounded photo converts to an unreadable blob, so this
does three things before `make_ascii_svg.py` ever sees it:

  1. remove the background so only the subject survives   (rembg, optional)
  2. boost local contrast so a flat face gains highlights (CLAHE, optional)
  3. composite onto pure white so the background lands on the blank end of the
     ASCII ramp

Only pillow and numpy are hard requirements. rembg needs Python >= 3.10 and
opencv is a large wheel, so both are detected at import time and skipped with a
warning when missing -- the script still produces usable output without them.

    python scripts/prep_photo.py assets/source-photo.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

# Optional dependencies. Absence is a downgrade, not an error.
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from rembg import remove as rembg_remove
except ImportError:
    rembg_remove = None


def strip_background(img: Image.Image) -> Image.Image:
    """Isolate the subject. Returns RGBA; alpha is all-opaque if rembg is absent."""
    if rembg_remove is None:
        print("  ! rembg unavailable -- keeping the original background", file=sys.stderr)
        return img.convert("RGBA")
    print("  - removing background (rembg)")
    return rembg_remove(img.convert("RGBA"))


def on_white(img: Image.Image) -> Image.Image:
    """Flatten transparency onto pure white, so the background reads as blank."""
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, img.convert("RGBA")).convert("RGB")


def boost_contrast(gray: Image.Image, clip: float, grid: int) -> Image.Image:
    """CLAHE when opencv is available, plain autocontrast otherwise."""
    if cv2 is None:
        print("  ! opencv unavailable -- falling back to PIL autocontrast", file=sys.stderr)
        return ImageOps.autocontrast(gray, cutoff=2)
    print(f"  - CLAHE local contrast (clip={clip}, grid={grid}x{grid})")
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    return Image.fromarray(clahe.apply(np.array(gray)))


def vignette(gray: Image.Image, strength: float) -> Image.Image:
    """Fade the frame edges toward white.

    Stands in for background removal when rembg is unavailable: a busy backdrop
    is pushed toward the blank end of the ramp while the centered subject stays.
    """
    if strength <= 0:
        return gray
    print(f"  - center vignette (strength={strength})")
    arr = np.array(gray, dtype=np.float32)
    h, w = arr.shape
    yy, xx = np.mgrid[0:h, 0:w]
    # Normalised distance from centre, 0 at the middle and 1 at the nearest edge.
    dist = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    fade = np.clip((dist - (1.0 - strength)) / max(strength, 1e-6), 0.0, 1.0)
    arr = arr + (255.0 - arr) * fade
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", default="assets/source-photo.png",
                    help="input photo (default: assets/source-photo.png)")
    ap.add_argument("-o", "--out", default="assets/source-prepped.png",
                    help="output grayscale PNG (default: assets/source-prepped.png)")
    ap.add_argument("--clip", type=float, default=3.0, help="CLAHE clip limit")
    ap.add_argument("--grid", type=int, default=8, help="CLAHE tile grid size")
    ap.add_argument("--vignette", type=float, default=0.0, metavar="0..1",
                    help="fade edges to white; useful when rembg is unavailable")
    ap.add_argument("--invert", action="store_true",
                    help="invert brightness (for a light subject on a dark background)")
    args = ap.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"error: {src} not found", file=sys.stderr)
        return 1

    print(f"prepping {src}")
    img = Image.open(src)
    img = strip_background(img)
    gray = on_white(img).convert("L")

    if args.invert:
        print("  - inverting brightness")
        gray = ImageOps.invert(gray)

    gray = boost_contrast(gray, args.clip, args.grid)
    gray = vignette(gray, args.vignette)
    gray = ImageOps.autocontrast(gray, cutoff=1)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    gray.save(out)
    print(f"wrote {out} ({gray.width}x{gray.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
