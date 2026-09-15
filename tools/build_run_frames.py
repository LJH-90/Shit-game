"""Build standing run / run-and-shoot frames from the source sheet.

Dev-only script (Pillow only, no numpy).  Usage:

    python tools/build_run_frames.py

The original ``run`` / ``shoot_run`` animations came from crouched dash frames.
The source sheet also has an upright rifle run (4 frames) and an upright
run-and-shoot cycle; this script cuts them, classifies every pixel into the
body-part classes used by ``assets_data`` (outline/hair/skin/shirt/...), then:

* writes ``assets_extra.py``  - class-byte frames + ANIMS overrides for the
  palette-swapped enemies (same format as assets_data);
* writes ``sheets/<key>_run.png`` for each player character - the frames painted
  with that character's colour ramps and body proportions, with the head (and
  its accessories: headband / glasses) taken from the character's own idle
  frame.  Layout: row 0 = run, row 1 = shoot_run; cells 100x80, feet on cell
  row 77, body centred on cell column 50.  ``tools/import_char_sheets.py``
  reads these.
* writes ``tools/run_preview.png`` for eyeballing.
"""
from __future__ import annotations

import base64
import colorsys
import math
import os
import sys
import zlib
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SOURCE = os.path.join(ROOT, "스프라이트 시트.png")
SHEET_DIR = os.path.join(ROOT, "sheets")
OUT_EXTRA = os.path.join(ROOT, "assets_extra.py")
PREVIEW = os.path.join(HERE, "run_preview.png")

# (frame_id, source box) - boxes are generous; the biggest blob inside wins
RUN_SRC = [("r00", (602, 850, 644, 918)), ("r01", (643, 850, 695, 918)),
           ("r02", (692, 848, 748, 918)), ("r03", (745, 850, 800, 918))]
SHOOT_RUN_SRC = [("s00", (800, 850, 858, 918)), ("s01", (855, 848, 921, 918)),
                 ("s02", (980, 850, 1050, 918))]
NEW_ANIMS = {"run": [f for f, _ in RUN_SRC], "shoot_run": [f for f, _ in SHOOT_RUN_SRC]}
NEW_FPS = {"run": 10.0, "shoot_run": 10.0}

C_TRANS, C_OUT, C_HAIR, C_SKIN, C_SHIRT, C_PANTS, C_GUN, C_SHOE, C_WHITE, C_FX = range(10)
AMBIG = 99                                     # classify(): not decided yet
CLASS_NAMES = {0: "transparent", 1: "outline", 2: "hair", 3: "skin", 4: "shirt", 5: "pants",
               6: "gun", 7: "shoe", 8: "white", 9: "fx"}
SHADE_MUL = (0.55, 0.78, 1.0, 1.25)          # same as sprites.SHADE_MUL

CELL_W, CELL_H, FOOT_Y, CENTRE_X = 100, 80, 77, 50

# per-character colour ramps (shade-2 base colours read off sheets/<key>.png)
# and body proportions (width, height) relative to the source frames
CHARS = {
    "jaehwi": {"pal": {C_OUT: "#141416", C_HAIR: "#1c1c1c", C_SKIN: "#e6b48c", C_SHIRT: "#38a6e0",
                       C_PANTS: "#1f2a4a", C_GUN: "#7a7f88", C_SHOE: "#141416", C_WHITE: "#f4f4f4",
                       C_FX: "#e02828"},
               "scale": (0.84, 1.08)},
    "hyunki": {"pal": {C_OUT: "#141416", C_HAIR: "#3a2a20", C_SKIN: "#e6b48c", C_SHIRT: "#8c1e1e",
                       C_PANTS: "#34363a", C_GUN: "#4a3a2a", C_SHOE: "#141416", C_WHITE: "#f4f4f4",
                       C_FX: "#e02828"},
               "scale": (1.4, 1.0)},
    "dongil": {"pal": {C_OUT: "#141416", C_HAIR: "#26262c", C_SKIN: "#e6b48c", C_SHIRT: "#f2f2f2",
                       C_PANTS: "#26262c", C_GUN: "#7c8896", C_SHOE: "#141416", C_WHITE: "#f4f4f4",
                       C_FX: "#e02828"},
               "scale": (0.94, 1.02)},
}


# --------------------------------------------------------------------------- helpers
def neighbours8(x, y, w, h):
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    yield nx, ny


def components(mask, w, h):
    """8-connected components of a 2-D bool list -> list of pixel lists, biggest first."""
    seen = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y][x] and not seen[y][x]:
                seen[y][x] = True
                q = deque([(x, y)])
                pts = []
                while q:
                    cx, cy = q.popleft()
                    pts.append((cx, cy))
                    for nx, ny in neighbours8(cx, cy, w, h):
                        if mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            q.append((nx, ny))
                out.append(pts)
    out.sort(key=len, reverse=True)
    return out


def hex_rgb(s):
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def shade_rgb(base, shade):
    m = SHADE_MUL[shade]
    return tuple(min(255, int(c * m + 0.5)) for c in hex_rgb(base))


# --------------------------------------------------------------------------- cut
def is_fg(p):
    r, g, b, a = p
    mn, mx = min(r, g, b), max(r, g, b)
    if a < 8 or mn > 225:
        return False
    return not (g > r and g > b and mn > 110 and mx < 215 and (g - b) > 25)   # sheet grid


def cut(box):
    """Crop a source box to its main figure -> list of rows of (r,g,b) or None."""
    im = Image.open(SOURCE).convert("RGBA").crop(box)
    w, h = im.size
    px = im.load()
    mask = [[is_fg(px[x, y]) for x in range(w)] for y in range(h)]
    comps = components(mask, w, h)
    keep = set(comps[0])          # the figure is one blob; muzzle flashes / smoke / grid bits are separate
    grid = [[None] * w for _ in range(h)]
    for (x, y) in keep:
        grid[y][x] = px[x, y][:3]
    # halo strip: pale pixels within 2 px of transparency (anti-aliased rim of the cream background)
    for _ in range(3):
        kill = []
        for y in range(h):
            for x in range(w):
                c = grid[y][x]
                if c is None or not (min(c) > 185 or (min(c) > 150 and max(c) - min(c) < 45)):
                    continue
                if any(not (0 <= x + dx < w and 0 <= y + dy < h) or grid[y + dy][x + dx] is None
                       for dy in range(-2, 3) for dx in range(-2, 3)):
                    kill.append((x, y))
        if not kill:
            break
        for (x, y) in kill:
            grid[y][x] = None
    # drop 1-px slivers left hanging
    for y in range(h):
        for x in range(w):
            if grid[y][x] is not None and sum(grid[ny][nx] is not None for nx, ny in neighbours8(x, y, w, h)) <= 1:
                grid[y][x] = None
    return trim(grid)


def trim(grid):
    h, w = len(grid), len(grid[0])
    ys = [y for y in range(h) if any(c is not None for c in grid[y])]
    xs = [x for x in range(w) if any(grid[y][x] is not None for y in range(h))]
    return [row[min(xs):max(xs) + 1] for row in grid[min(ys):max(ys) + 1]]


# --------------------------------------------------------------------------- classify
def family(rgb):
    """Coarse colour family (port of tools/recolor.py family())."""
    h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
    h *= 360.0
    if v < 0.13 or (v < 0.2 and s < 0.35):
        return C_OUT
    if s > 0.45 and v > 0.45 and (h < 14 or h > 335):
        return C_FX
    if s < 0.2:
        if v > 0.86 or (s < 0.07 and v > 0.72):
            return C_WHITE
        if v < 0.66:
            return C_GUN
        if 170 <= h <= 265:
            return C_SHIRT
        if 55 <= h < 170:
            return C_PANTS
        return C_SKIN if s > 0.1 else C_WHITE
    if 175 <= h <= 265:
        return C_SHIRT
    if 55 <= h <= 174:
        return C_PANTS
    if 8 <= h <= 55:
        return C_SKIN if (v > 0.55 and s < 0.6) else "brown"
    return "brown"


def classify(grid):
    """-> (cls, shade) 2-D lists."""
    h, w = len(grid), len(grid[0])
    fam = [[(family(c) if c is not None else C_TRANS) for c in row] for row in grid]
    # head: biggest skin blob in the top 40%
    skin_mask = [[fam[y][x] == C_SKIN and y < 0.4 * h for x in range(w)] for y in range(h)]
    faces = components(skin_mask, w, h)
    if faces:
        face = faces[0]
        hy = sum(p[1] for p in face) / len(face)
        hx = sum(p[0] for p in face) / len(face)
        face_r = max(6.0, 1.9 * math.sqrt(len(face)))
        chin = max(p[1] for p in face)
    else:
        hx, hy, face_r = w / 2, h * 0.15, 8.0
        chin = int(h * 0.3)
    cls = [[C_TRANS] * w for _ in range(h)]
    brown_mask = [[fam[y][x] == "brown" for x in range(w)] for y in range(h)]
    for comp in components(brown_mask, w, h):
        near = sum(1 for (x, y) in comp if math.hypot(x - hx, y - hy) < face_r * 1.6)
        for (x, y) in comp:
            # hair only on the head: brown below the chin is the backpack / rifle / shading
            hair = (near >= max(3, 0.12 * len(comp)) and math.hypot(x - hx, y - hy) < face_r * 3.2
                    and y <= chin + 1)
            cls[y][x] = C_HAIR if hair else AMBIG
    for y in range(h):
        for x in range(w):
            f = fam[y][x]
            if f == C_TRANS:
                continue
            _h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in grid[y][x]))
            if f == "brown":
                # red-brown / tan off the head is the rifle; olive brown (hue >= 40) is trouser shading
                if cls[y][x] == AMBIG and _h * 360 < 40:
                    cls[y][x] = C_GUN
                continue
            if f == C_SKIN and s >= 0.5:
                f = C_GUN                      # light rifle wood
            elif f in (C_GUN, C_WHITE):
                f = AMBIG                      # grey / pale: garment shading, decided by neighbours
            cls[y][x] = f
    resolve_ambiguous(cls, grid)
    # below the waist, shirt is trousers; dark pixels in the bottom band are shoes
    for y in range(h):
        for x in range(w):
            c = cls[y][x]
            if y > 0.62 * h and c == C_SHIRT:
                cls[y][x] = C_PANTS
            if (y > 0.9 * h and c == C_OUT) or (y > 0.85 * h and c in (C_SKIN, C_GUN)):
                cls[y][x] = C_SHOE        # boots (olive/tan in the source)
    despeckle(cls)
    # shades relative to each class median brightness
    vals = {}
    for y in range(h):
        for x in range(w):
            if cls[y][x]:
                vals.setdefault(cls[y][x], []).append(max(grid[y][x]) / 255.0)
    med = {c: sorted(v)[len(v) // 2] for c, v in vals.items()}
    shade = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = cls[y][x]
            if not c:
                continue
            v = max(grid[y][x]) / 255.0
            m = med[c]
            s = 2
            if v < m - 0.10:
                s = 1
            if v < m - 0.26:
                s = 0
            if v > m + 0.11:
                s = 3
            if c in (C_OUT, C_SHOE):
                s = min(s, 1)
            shade[y][x] = s
    return cls, shade


def resolve_ambiguous(cls, grid):
    """Grey / pale / dull-brown pixels: pale ones on the silhouette edge are background
    rim and are dropped; the rest take the class of the nearest confident pixel."""
    h, w = len(cls), len(cls[0])
    for y in range(h):
        for x in range(w):
            if cls[y][x] != AMBIG:
                continue
            r, g, b = grid[y][x]
            if min(r, g, b) > 140 and any(
                    not (0 <= x + dx < w and 0 <= y + dy < h) or cls[y + dy][x + dx] == C_TRANS
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                cls[y][x] = C_TRANS
    q = deque((x, y) for y in range(h) for x in range(w) if cls[y][x] not in (C_TRANS, AMBIG, C_OUT))
    while q:
        x, y = q.popleft()
        for nx, ny in neighbours8(x, y, w, h):
            if cls[ny][nx] == AMBIG:
                cls[ny][nx] = cls[y][x]
                q.append((nx, ny))
    for y in range(h):
        for x in range(w):
            if cls[y][x] == AMBIG:
                cls[y][x] = C_OUT


def despeckle(cls, iterations=2):
    h, w = len(cls), len(cls[0])
    for _ in range(iterations):
        changes = []
        for y in range(h):
            for x in range(w):
                c = cls[y][x]
                if not c:
                    continue
                nb = [cls[ny][nx] for nx, ny in neighbours8(x, y, w, h)]
                if sum(1 for n in nb if n == c) >= 2:
                    continue
                counts = {}
                for n in nb:
                    if n:
                        counts[n] = counts.get(n, 0) + 1
                if counts:
                    changes.append((x, y, max(counts, key=counts.get)))
        if not changes:
            break
        for x, y, c in changes:
            cls[y][x] = c


# --------------------------------------------------------------------------- geometry
def scale_map(m, sx, sy):
    h, w = len(m), len(m[0])
    nw, nh = max(1, round(w * sx)), max(1, round(h * sy))
    return [[m[min(h - 1, int((y + 0.5) / sy))][min(w - 1, int((x + 0.5) / sx))] for x in range(nw)]
            for y in range(nh)]


def outline_rgba(rows, color=(20, 20, 22, 255)):
    """Pad 1 px and paint transparent pixels that 4-touch the silhouette."""
    h, w = len(rows), len(rows[0])
    out = [[(0, 0, 0, 0)] * (w + 2) for _ in range(h + 2)]
    for y in range(h):
        for x in range(w):
            out[y + 1][x + 1] = rows[y][x]
    res = [row[:] for row in out]
    for y in range(h + 2):
        for x in range(w + 2):
            if out[y][x][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w + 2 and 0 <= ny < h + 2 and out[ny][nx][3]:
                    res[y][x] = color
                    break
    return res


def idle_head(key):
    """RGBA rows of the character's idle head (rows above the chin, collar excluded) + face anchor."""
    sheet = Image.open(os.path.join(SHEET_DIR, f"{key}.png")).convert("RGBA")
    cell = sheet.crop((0, 0, 72, 80))
    px = cell.load()
    w, h = cell.size
    skin = hex_rgb(CHARS[key]["pal"][C_SKIN])
    skin_ramp = {shade_rgb(CHARS[key]["pal"][C_SKIN], s) for s in range(4)}
    shirt_ramp = {shade_rgb(CHARS[key]["pal"][C_SHIRT], s) for s in range(4)}
    del skin
    top = min(y for y in range(h) for x in range(w) if px[x, y][3])
    face = [(x, y) for y in range(top, top + 26) for x in range(w)
            if px[x, y][3] and px[x, y][:3] in skin_ramp]
    chin = max(y for _, y in face)
    fx = sum(x for x, _ in face) / len(face)
    pts = {}
    for y in range(top, chin + 1):
        for x in range(w):
            p = px[x, y]
            if p[3] and p[:3] not in shirt_ramp:
                pts[(x, y)] = p
    return pts, fx, chin


def paint(key, cls, shade):
    pal = CHARS[key]["pal"]
    sx, sy = CHARS[key]["scale"]
    cls = scale_map(cls, sx, sy)
    shade = scale_map(shade, sx, sy)
    h, w = len(cls), len(cls[0])
    rows = [[(0, 0, 0, 0)] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            c = cls[y][x]
            if c:
                rows[y][x] = shade_rgb(pal[c], shade[y][x]) + (255,)
    # head swap: remove the source hair/face, paste the character's own head
    face = [(x, y) for y in range(int(h * 0.45)) for x in range(w) if cls[y][x] == C_SKIN]
    head_pts, hfx, hchin = idle_head(key)
    if face:
        tfx = sum(x for x, _ in face) / len(face)
        tchin = max(y for _, y in face if y < h * 0.4) if any(y < h * 0.4 for _, y in face) else max(y for _, y in face)
        dx, dy = round(tfx - hfx), tchin - hchin
        hx0 = min(x for x, _ in head_pts) + dx - 2
        hx1 = max(x for x, _ in head_pts) + dx + 2
        head_top = min(y for _, y in head_pts) + dy
        for y in range(0, min(h, tchin + 1)):
            for x in range(w):
                c = cls[y][x]
                if (y < head_top or c in (C_HAIR, C_SKIN)
                        or (hx0 <= x <= hx1 and c not in (C_SHIRT, C_PANTS))):
                    rows[y][x] = (0, 0, 0, 0)     # source hair / curls / face: replaced by the pasted head
        # grow the canvas if the pasted head sticks out
        min_x = min(0, min(x for x, _ in head_pts) + dx)
        max_x = max(w - 1, max(x for x, _ in head_pts) + dx)
        min_y = min(0, min(y for _, y in head_pts) + dy)
        if min_x < 0 or max_x >= w or min_y < 0:
            nw, nh = max_x - min_x + 1, h - min_y
            grown = [[(0, 0, 0, 0)] * nw for _ in range(nh)]
            for y in range(h):
                for x in range(w):
                    grown[y - min_y][x - min_x] = rows[y][x]
            rows, h, w = grown, nh, nw
            dx -= min_x
            dy -= min_y
        for (x, y), p in head_pts.items():
            rows[y + dy][x + dx] = p
    rows = trim_rgba(rows)
    return outline_rgba(rows)


def trim_rgba(rows):
    h, w = len(rows), len(rows[0])
    ys = [y for y in range(h) if any(p[3] for p in rows[y])]
    xs = [x for x in range(w) if any(rows[y][x][3] for y in range(h))]
    return [row[min(xs):max(xs) + 1] for row in rows[min(ys):max(ys) + 1]]


def outline_cls(cls, shade):
    h, w = len(cls), len(cls[0])
    oc = [[0] * (w + 2) for _ in range(h + 2)]
    osd = [[0] * (w + 2) for _ in range(h + 2)]
    for y in range(h):
        for x in range(w):
            oc[y + 1][x + 1] = cls[y][x]
            osd[y + 1][x + 1] = shade[y][x]
    res_c = [row[:] for row in oc]
    for y in range(h + 2):
        for x in range(w + 2):
            if oc[y][x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w + 2 and 0 <= ny < h + 2 and oc[ny][nx]:
                    res_c[y][x] = C_OUT
                    osd[y][x] = 1
                    break
    return res_c, osd


# --------------------------------------------------------------------------- main
def main():
    srcs = RUN_SRC + SHOOT_RUN_SRC
    classified = {}
    for fid, box in srcs:
        grid = cut(box)
        classified[fid] = classify(grid)
        print(f"{fid}: {len(grid[0])}x{len(grid)} from {box}")

    # enemies: class frames
    meta, blob, off = [], bytearray(), 0
    for fid, _ in srcs:
        cls, shade = outline_cls(*classified[fid])
        h, w = len(cls), len(cls[0])
        data = bytes((cls[y][x] << 4) | shade[y][x] for y in range(h) for x in range(w))
        meta.append((fid, w, h, w // 2, h - 1, off))
        blob += data
        off += len(data)
    comp = base64.b64encode(zlib.compress(bytes(blob), 9)).decode("ascii")
    lines = ['"""GENERATED by tools/build_run_frames.py - do not edit by hand.', "",
             "Upright run / run-and-shoot frames for the palette-swapped sprites. Same format as",
             "assets_data.FRAMES; ANIMS entries here replace the ones in assets_data.", '"""',
             "import base64 as _b64", "import zlib as _zlib", "", "_BLOB = _zlib.decompress(_b64.b64decode("]
    lines += [f"    {comp[i:i + 96]!r}" for i in range(0, len(comp), 96)]
    lines += ["))", "", "_META = ["] + [f"    {m!r}," for m in meta] + ["]", "",
              "FRAMES = {f: (w, h, ax, ay, _BLOB[o:o + w * h]) for f, w, h, ax, ay, o in _META}", "",
              f"ANIMS = {NEW_ANIMS!r}", "", f"ANIM_FPS = {NEW_FPS!r}", "", "del _META, _BLOB", ""]
    with open(OUT_EXTRA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print(f"-> {OUT_EXTRA}")

    # characters: painted sheets
    previews = []
    for key in CHARS:
        sheet = Image.new("RGBA", (CELL_W * 4, CELL_H * 2), (0, 0, 0, 0))
        row_imgs = []
        for row, (anim, ids) in enumerate(NEW_ANIMS.items()):
            for col, fid in enumerate(ids):
                rows = paint(key, *classified[fid])
                h, w = len(rows), len(rows[0])
                im = Image.new("RGBA", (w, h))
                im.putdata([p for r in rows for p in r])
                if w > CELL_W - 2 or h > CELL_H - 3:
                    raise ValueError(f"{key} {fid}: {w}x{h} does not fit the cell")
                # feet: bottom row on FOOT_Y, body centre on CENTRE_X
                sheet.alpha_composite(im, (col * CELL_W + CENTRE_X - w // 2, row * CELL_H + FOOT_Y - (h - 1)))
                row_imgs.append(im)
                print(f"  {key} {fid}: {w}x{h}")
        path = os.path.join(SHEET_DIR, f"{key}_run.png")
        sheet.save(path)
        previews.append(sheet)
        print(f"-> {path}")

    bg = Image.new("RGBA", (CELL_W * 4, CELL_H * 2 * len(previews)), (58, 62, 70, 255))
    for i, s in enumerate(previews):
        bg.alpha_composite(s, (0, i * CELL_H * 2))
    bg.resize((bg.width * 3, bg.height * 3), Image.NEAREST).save(PREVIEW)
    print(f"-> {PREVIEW}")


if __name__ == "__main__":
    sys.exit(main())
