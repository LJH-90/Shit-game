"""Segment the source sprite sheet into individual frame crops.

Dev-only script (Pillow / numpy / scipy).  Usage:

    python tools/extract_sprites.py

Outputs:
    tools/frames/f{idx:03d}.png   RGBA crops (background transparent)
    tools/contact.png             2x nearest contact sheet with index labels
    tools/frames/index.txt        idx, x, y, w, h of every crop on the sheet
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHEET = os.path.join(ROOT, "스프라이트 시트.png")
OUT_DIR = os.path.join(HERE, "frames")
CONTACT = os.path.join(HERE, "contact.png")

MIN_H = 14          # blobs shorter than this are fx crumbs -> dropped
MIN_W = 6
SPLIT_W = 58        # blobs wider than this are checked for internal column gaps
SPLIT_H = 60        # blobs taller than this are checked for internal row gaps
# solid horizontal band lines of the sheet (measured); dilation must not cross them
BAND_ROWS = [0, 1, 47, 174, 175, 268, 354, 355, 447, 448, 572, 573, 640, 641,
             703, 704, 769, 854, 916, 917]


def masks(rgb: np.ndarray, alpha: np.ndarray):
    r = rgb[..., 0].astype(int)
    g = rgb[..., 1].astype(int)
    b = rgb[..., 2].astype(int)
    mn = rgb.min(axis=2).astype(int)
    mx = rgb.max(axis=2).astype(int)
    bg = mn > 225
    grid = (g > r) & (g > b) & (mn > 110) & (mx < 215) & ((g - b) > 25)
    fg = (~bg) & (~grid) & (alpha > 8)
    return bg, grid, fg


def split_runs(profile: np.ndarray, min_len: int):
    """Return [(start, end)] runs of non-zero entries in a 1-D profile."""
    runs = []
    inside = False
    start = 0
    for i, v in enumerate(profile):
        if v and not inside:
            inside, start = True, i
        elif not v and inside:
            inside = False
            if i - start >= min_len:
                runs.append((start, i))
    if inside and len(profile) - start >= min_len:
        runs.append((start, len(profile)))
    return runs


def segment(fg: np.ndarray):
    """Connected components with dilation, then split merged frames on gaps."""
    dil = ndimage.binary_dilation(fg, iterations=3)
    for r in BAND_ROWS:            # never let dilation bridge a band line
        dil[r, :] = False
    lab, n = ndimage.label(dil)
    boxes = []
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        boxes.append((x0, y0, x1, y1, k))

    # iterative split: first by empty rows, then by empty columns, repeat
    out = []
    todo = boxes
    while todo:
        x0, y0, x1, y1, k = todo.pop()
        own = fg[y0:y1, x0:x1] & (lab[y0:y1, x0:x1] == k)
        ys, xs = np.nonzero(own)
        if len(xs) == 0:
            continue
        # tighten to this label's own pixels
        tx0, tx1 = x0 + xs.min(), x0 + xs.max() + 1
        ty0, ty1 = y0 + ys.min(), y0 + ys.max() + 1
        sub = fg[ty0:ty1, tx0:tx1] & (lab[ty0:ty1, tx0:tx1] == k)
        h, w = sub.shape
        if h > SPLIT_H:
            rows = split_runs(sub.sum(axis=1) > 0, 3)
            if len(rows) > 1:
                for a, b in rows:
                    todo.append((tx0, ty0 + a, tx1, ty0 + b, k))
                continue
        if w > SPLIT_W:
            cols = split_runs(sub.sum(axis=0) > 0, 2)
            if len(cols) <= 1 and w > 1.5 * h:
                # frames touching each other: cut at very sparse columns
                cols = [c for c in split_runs(sub.sum(axis=0) > 2, 10)]
                cols = [(max(0, a - 1), min(w, b + 1)) for a, b in cols]
            if len(cols) > 1:
                for a, b in cols:
                    todo.append((tx0 + a, ty0, tx0 + b, ty1, k))
                continue
        out.append((tx0, ty0, tx1, ty1, k))
    return out, lab


def order_boxes(boxes):
    """Sort reading order: group by row bands (by y-centre clustering), then x."""
    boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    rows = []
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        for row in rows:
            if abs(row["cy"] - cy) < 22:
                row["items"].append(b)
                row["cy"] = (row["cy"] * (len(row["items"]) - 1) + cy) / len(row["items"])
                break
        else:
            rows.append({"cy": cy, "items": [b]})
    rows.sort(key=lambda r: r["cy"])
    ordered = []
    for row in rows:
        ordered.extend(sorted(row["items"], key=lambda b: b[0]))
    return ordered


def main():
    img = Image.open(SHEET).convert("RGBA")
    arr = np.asarray(img)
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    bg, grid, fg = masks(rgb, alpha)
    fg = ndimage.binary_opening(fg, iterations=1) | (fg & ndimage.binary_dilation(
        ndimage.binary_opening(fg, iterations=1), iterations=2))

    boxes, lab = segment(fg)
    boxes = [b for b in boxes if (b[3] - b[1]) >= MIN_H and (b[2] - b[0]) >= MIN_W]
    boxes = order_boxes(boxes)
    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(OUT_DIR):
        if f.startswith("f") and f.endswith(".png"):
            os.remove(os.path.join(OUT_DIR, f))

    crops = []
    with open(os.path.join(OUT_DIR, "index.txt"), "w", encoding="utf-8") as fh:
        for idx, (x0, y0, x1, y1, k) in enumerate(boxes):
            m = fg[y0:y1, x0:x1] & (lab[y0:y1, x0:x1] == k)
            crop = arr[y0:y1, x0:x1].copy()
            # soft alpha: keep source alpha where fg; feather 1px of edge pixels that are
            # not pure background/grid so anti-aliased outlines survive
            a = np.where(m, 255, 0).astype(np.uint8)
            crop[..., 3] = a
            im = Image.fromarray(crop, "RGBA")
            im.save(os.path.join(OUT_DIR, f"f{idx:03d}.png"))
            crops.append((idx, im))
            fh.write(f"{idx} {x0} {y0} {x1 - x0} {y1 - y0}\n")

    # contact sheet
    cell = 104
    cols = 14
    rows = (len(crops) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 14)), (40, 40, 48))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=12)
    except TypeError:
        font = ImageFont.load_default()
    for i, (idx, im) in enumerate(crops):
        cx = (i % cols) * cell
        cy = (i // cols) * (cell + 14)
        w, h = im.size
        s = min(2, (cell - 4) / max(w, h))
        if s >= 1:
            s = int(s)
        big = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.NEAREST)
        tile = Image.new("RGBA", (cell, cell), (235, 235, 225, 255))
        tile.alpha_composite(big, (2, cell - 2 - big.height))
        sheet.paste(tile.convert("RGB"), (cx, cy + 14))
        draw.text((cx + 2, cy), f"{idx}:{w}x{h}", fill=(255, 230, 0), font=font)
    sheet.save(CONTACT)
    print(f"{len(crops)} frames -> {OUT_DIR}, contact {CONTACT} ({sheet.size[0]}x{sheet.size[1]})")


if __name__ == "__main__":
    sys.exit(main())
