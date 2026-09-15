"""Import the per-character sprite sheets into ``assets_chars.py``.

Dev-only script (Pillow).  Usage:

    python tools/build_run_frames.py      # (re)builds sheets/<key>_run.png first
    python tools/import_char_sheets.py

Sources:

* ``sheets/<key>.png`` from the Claude Design "Character Sheets" page.  432x800,
  transparent, 1x, facing right.  One row per animation (order and frame count of
  ``assets_data.ANIMS``), cells 72x80, feet on cell row 77, body centred on cell
  column 36.  Wide frames (long rifles) spill into the neighbouring cell, so
  pixels are not cut by cell: every frame's rectangle is known from the design's
  frame table (FRAME_RECTS) and pixels in overlapping rectangles go to the frame
  they are connected to.
* ``sheets/<key>_run.png`` from tools/build_run_frames.py - upright ``run`` /
  ``shoot_run`` frames that replace the crouched ones of the base sheet.

Every frame gets a 1-px dark outline where its silhouette edge is not already
dark, so the sprite stays readable over any desktop behind the overlay.

Output: ``assets_chars.py`` at the project root with
    CHAR_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba)
rgba = w*h*4 bytes, row major, alpha 0 or 255 (the overlay window uses a colour
key, so soft edges would fringe).  Frame ids follow ``sprites.ANIMS``
(assets_data + assets_extra).
"""
from __future__ import annotations

import base64
import os
import sys
import zlib
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import assets_data  # noqa: E402
import assets_extra  # noqa: E402

SHEET_DIR = os.path.join(ROOT, "sheets")
OUT = os.path.join(ROOT, "assets_chars.py")

CHARS = ["jaehwi", "hyunki", "dongil"]
ROW_ORDER = ["idle", "run", "jump", "fall", "shoot", "shoot_run", "crouch",
             "crouch_shoot", "death", "victory"]
REPLACED = set(assets_extra.ANIMS)            # rows taken from <key>_run.png instead
CELL_W, CELL_H = 72, 80
FOOT_Y, CENTRE_X = 77, 36
RUN_CELL_W, RUN_CELL_H, RUN_FOOT_Y, RUN_CENTRE_X = 100, 80, 77, 50
ALPHA_CUT = 128
OUTLINE = (20, 20, 22, 255)
DARK_LUMA = 70                                 # edge pixels darker than this already read as outline

# design frame table: (w, h, anchor_x, anchor_y) per frame in ROW_ORDER order
FRAME_RECTS = {
    "jaehwi": [(35, 64, 17, 63), (34, 64, 17, 63), (32, 46, 16, 45), (32, 44, 16, 43), (37, 44, 18, 43),
               (36, 44, 18, 43), (44, 44, 22, 43), (42, 45, 21, 44), (37, 65, 18, 64), (39, 59, 19, 58),
               (41, 65, 20, 64), (41, 62, 20, 61), (38, 58, 19, 57), (39, 59, 19, 58), (47, 66, 23, 65),
               (52, 57, 26, 56), (45, 64, 22, 63), (51, 48, 25, 47), (31, 48, 15, 47), (45, 49, 22, 48),
               (45, 58, 22, 57), (52, 58, 26, 57), (51, 56, 25, 55), (35, 56, 17, 55), (33, 55, 16, 54),
               (34, 48, 17, 47), (32, 33, 16, 32), (34, 21, 17, 20), (22, 72, 11, 71), (32, 70, 16, 69),
               (32, 71, 16, 70), (29, 69, 14, 68)],
    "hyunki": [(62, 58, 31, 57), (60, 60, 30, 59), (49, 46, 24, 45), (48, 44, 24, 43), (55, 44, 27, 43),
               (54, 44, 27, 43), (66, 44, 33, 43), (63, 45, 31, 44), (66, 59, 33, 58), (59, 59, 29, 58),
               (65, 59, 32, 58), (62, 56, 31, 55), (56, 53, 28, 52), (56, 53, 28, 52), (83, 60, 41, 59),
               (78, 57, 39, 56), (80, 58, 40, 57), (75, 43, 37, 42), (48, 43, 24, 42), (68, 49, 34, 48),
               (80, 53, 40, 52), (84, 52, 42, 51), (89, 52, 44, 51), (62, 50, 31, 49), (57, 49, 28, 48),
               (61, 43, 30, 42), (57, 29, 28, 28), (50, 21, 25, 20), (36, 65, 18, 64), (51, 63, 25, 62),
               (44, 65, 22, 64), (45, 64, 22, 63)],
    "dongil": [(39, 60, 19, 59), (38, 62, 19, 61), (35, 46, 17, 45), (34, 44, 17, 43), (39, 44, 19, 43),
               (38, 44, 19, 43), (47, 44, 23, 43), (45, 45, 22, 44), (42, 60, 21, 59), (42, 59, 21, 58),
               (47, 60, 23, 59), (47, 58, 23, 57), (43, 55, 21, 54), (44, 55, 22, 54), (53, 62, 26, 61),
               (56, 57, 28, 56), (51, 60, 25, 59), (60, 45, 30, 44), (35, 45, 17, 44), (49, 49, 24, 48),
               (51, 55, 25, 54), (58, 54, 29, 53), (60, 54, 30, 53), (40, 51, 20, 50), (39, 51, 19, 50),
               (39, 45, 19, 44), (36, 30, 18, 29), (36, 21, 18, 20), (25, 67, 12, 66), (33, 65, 16, 64),
               (35, 67, 17, 66), (34, 66, 17, 65)],
}


def build_frame(pixels: dict, anchor: tuple[int, int]):
    """{(x, y): rgba} in sheet coords + sheet anchor -> outlined (w, h, ax, ay, rgba bytes)."""
    xs = [x for x, _ in pixels]
    ys = [y for _, y in pixels]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1   # 1-px pad for the outline
    w, h = x1 - x0 + 1, y1 - y0 + 1
    grid = [[None] * w for _ in range(h)]
    for (x, y), p in pixels.items():
        grid[y - y0][x - x0] = p
    added = 0
    out = bytearray()
    for y in range(h):
        for x in range(w):
            p = grid[y][x]
            if p is None:
                edge = False
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] is not None:
                        r, g, b, _ = grid[ny][nx]
                        if 0.299 * r + 0.587 * g + 0.114 * b > DARK_LUMA:
                            edge = True
                            break
                if edge:
                    out += bytes(OUTLINE)
                    added += 1
                else:
                    out += b"\x00\x00\x00\x00"
            else:
                out += bytes(p)
    return (w, h, anchor[0] - x0, anchor[1] - y0, bytes(out)), added


def opaque_pixels(img: Image.Image, box):
    px = img.load()
    x0, y0, x1, y1 = box
    res = {}
    for y in range(max(0, y0), min(img.height, y1)):
        for x in range(max(0, x0), min(img.width, x1)):
            r, g, b, a = px[x, y]
            if a >= ALPHA_CUT:
                res[(x, y)] = (r, g, b, 255)
    return res


def split_row(img: Image.Image, row: int, rects: list):
    """Assign the row's opaque pixels to frames. rects: [(x0, y0, x1, y1), ...] (x1/y1 exclusive)."""
    pix = opaque_pixels(img, (0, row * CELL_H, img.width, (row + 1) * CELL_H))
    owner = {}
    cands = {}
    for p in pix:
        c = [i for i, (x0, y0, x1, y1) in enumerate(rects) if x0 <= p[0] < x1 and y0 <= p[1] < y1]
        cands[p] = c
        if len(c) == 1:
            owner[p] = c[0]
    # contested pixels: grow ownership from the uncontested ones through connected pixels
    q = deque(owner)
    while q:
        x, y = q.popleft()
        o = owner[(x, y)]
        for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if n in pix and n not in owner and o in cands[n]:
                owner[n] = o
                q.append(n)
    centres = [((x0 + x1) / 2, (y0 + y1) / 2) for x0, y0, x1, y1 in rects]
    for p, c in cands.items():
        if p in owner or not c:
            continue       # outside every rectangle: stray, dropped
        owner[p] = min(c, key=lambda i: (centres[i][0] - p[0]) ** 2 + (centres[i][1] - p[1]) ** 2)
    frames = [dict() for _ in rects]
    for p, o in owner.items():
        frames[o][p] = pix[p]
    return frames


def import_sheet(key: str):
    img = Image.open(os.path.join(SHEET_DIR, f"{key}.png")).convert("RGBA")
    if img.size != (CELL_W * 6, CELL_H * len(ROW_ORDER)):
        raise ValueError(f"{key}.png: unexpected size {img.size}")
    rects_iter = iter(FRAME_RECTS[key])
    frames, outline_px = {}, 0
    for row, anim in enumerate(ROW_ORDER):
        ids = assets_data.ANIMS[anim]
        table = [next(rects_iter) for _ in ids]
        if anim in REPLACED:
            continue
        rects, anchors = [], []
        for col, (w, h, ax, ay) in enumerate(table):
            sx, sy = col * CELL_W + CENTRE_X, row * CELL_H + FOOT_Y
            rects.append((sx - ax, sy - ay, sx - ax + w, sy - ay + h))
            anchors.append((sx, sy))
        for fid, pixels, anchor in zip(ids, split_row(img, row, rects), anchors):
            frames[fid], n = build_frame(pixels, anchor)
            outline_px += n

    run = Image.open(os.path.join(SHEET_DIR, f"{key}_run.png")).convert("RGBA")
    for row, (anim, ids) in enumerate(assets_extra.ANIMS.items()):
        for col, fid in enumerate(ids):
            cx0, cy0 = col * RUN_CELL_W, row * RUN_CELL_H
            pixels = opaque_pixels(run, (cx0, cy0, cx0 + RUN_CELL_W, cy0 + RUN_CELL_H))
            if not pixels:
                raise ValueError(f"{key}_run.png: empty cell for {fid}")
            frames[fid], n = build_frame(pixels, (cx0 + RUN_CENTRE_X, cy0 + RUN_FOOT_Y))
            outline_px += n
    return frames, outline_px


def b64_lines(data: bytes, width: int = 100) -> str:
    s = base64.b64encode(zlib.compress(data, 9)).decode("ascii")
    return "\n".join(f"    '{s[i:i + width]}'" for i in range(0, len(s), width))


def main():
    parts = ['"""GENERATED by tools/import_char_sheets.py - do not edit by hand.',
             "",
             "Per-character RGBA frames cut from sheets/<key>.png and sheets/<key>_run.png.",
             "CHAR_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba); rgba = w*h*4 bytes,",
             "row major, facing right. anchor = bottom-centre (feet). Frame ids follow sprites.ANIMS.",
             '"""',
             "import base64 as _b64",
             "import zlib as _zlib",
             "",
             "CHAR_FRAMES = {}",
             ""]
    for key in CHARS:
        frames, outline_px = import_sheet(key)
        meta, blob = [], bytearray()
        for fid, (w, h, ax, ay, rgba) in frames.items():
            meta.append((fid, w, h, ax, ay, len(blob)))
            blob += rgba
        parts.append(f"_BLOB = _zlib.decompress(_b64.b64decode(\n{b64_lines(bytes(blob))}\n))")
        parts.append("_META = [")
        parts.extend(f"    {m!r}," for m in meta)
        parts.append("]")
        parts.append(f"CHAR_FRAMES[{key!r}] = {{f: (w, h, ax, ay, _BLOB[o:o + w * h * 4]) "
                     f"for f, w, h, ax, ay, o in _META}}")
        parts.append("")
        wide = " ".join(f"{m[0]}:{m[1]}x{m[2]}" for m in meta if m[0] in ("f058", "f235", "r00", "s01"))
        print(f"{key}: {len(meta)} frames, outline px added {outline_px}  ({wide})")
    parts.append("del _META, _BLOB")
    parts.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(parts))
    print(f"-> {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
