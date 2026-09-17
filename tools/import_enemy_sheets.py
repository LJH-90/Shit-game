"""Import the five monster sprite sheets in ``적/`` into ``assets_enemy.py``.

Dev-only script (Pillow).  Usage:

    python tools/import_enemy_sheets.py            # writes assets_enemy.py (+ per-anim preview strips)
    python tools/import_enemy_sheets.py --contact  # only writes labelled contact sheets (cell picking aid)

Sources -> keys:

* ``적/적 (1).png``  dark-blue bg   -> ``dino`` (+ ``dino_red``, ``dino_gold`` partial rows)
* ``적/적 (3).png``  dark-blue bg   -> ``golem`` (+ ``golem_blue``, ``golem_green`` partial rows)
* ``적/적 (4).png``  dark-blue bg   -> ``slime`` (+ ``slime_red``, ``slime_blue`` partial rows)
* ``적/적 (2).png``  blue bg (two blues: sheet + cell) -> ``mario``, ``luigi``, ``mario_fire``
* ``적/적 (1).gif``  magenta bg + transparent filler   -> ``bomber_w``, ``bomber_b`` (head + body cells)

The background colour of a sheet is its (0, 0) pixel (plus the extra colours in BG_EXTRA and any
fully transparent pixel).  Cells are the connected non-background bboxes grouped into row bands
(a band = consecutive rows containing any sprite pixel; a cell = a run of columns inside the band
containing any sprite pixel), giving every cell (row, col) indices.  ``--contact`` writes the
labelled contact sheets used to hand pick the ``CELLS`` table below.

Every frame: opaque = non-background pixels, cropped to the bbox, alpha 0/255, 1-px dark outline
where the silhouette edge is not already dark (tools/import_boss_sheets.py rule), normalised to
face RIGHT (sheet rows that face left are mirrored - see FACING_LEFT / FACING), anchor = bottom-
centre of the bbox; ``proj`` / ``proj2`` are anchored at their centre (w//2, h//2).

Colour variants that only have partial rows (dino_red, golem_blue, slime_red, ...) use their own
cells where they exist; the remaining anims are the base key's frames recoloured through an
exact colour LUT learnt from pose-identical (base, variant) cell pairs, falling back to an HSV hue
shift toward the variant's dominant colour for colours the LUT does not know.

Sheets without a projectile get a synthesized pixel-art one (fireball / bomb / slime blob).

Output ``assets_enemy.py``:
    ENEMY_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba)     (1x, facing right)
    ENEMY_ANIMS[key] = {"idle","run","attack","attack2","hurt","death","jump","proj"(,"proj2"): [ids]}
    ENEMY_ANIM_FPS[key] = {anim: fps}
    ENEMY_PROJ[key] = {"proj": (w, h)(, "proj2": (w, h))}
    ENEMY_HIT[key] = (w, h) of idle frame 0
frame ids are ``<key>_<anim>_<n>``.
"""
from __future__ import annotations

import base64
import colorsys
import os
import sys
import zlib
from collections import Counter

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets_enemy.py")
CONTACT_DIR = os.environ.get("ENEMY_CONTACT_DIR") or os.path.join(HERE, "contact")

SHEETS = {
    "dino": os.path.join(ROOT, "적", "적 (1).png"),
    "golem": os.path.join(ROOT, "적", "적 (3).png"),
    "slime": os.path.join(ROOT, "적", "적 (4).png"),
    "mario": os.path.join(ROOT, "적", "적 (2).png"),
    "bomber": os.path.join(ROOT, "적", "적 (1).gif"),
}
# extra background colours besides the (0, 0) pixel
BG_EXTRA = {"mario": {(68, 145, 190)}}
# contact sheet zoom (small NES / Bomberman sprites need 2x to be readable)
CONTACT_ZOOM = {"dino": 1, "golem": 1, "slime": 1, "mario": 2, "bomber": 2}
MIN_CELL = {"dino": 6, "golem": 6, "slime": 6, "mario": 4, "bomber": 4}
# bridge 1-px gaps inside a sprite (0 for the Mario sheet whose frame cells touch through 1-px separators)
DILATE = {"dino": 1, "golem": 1, "slime": 1, "mario": 0, "bomber": 1}

# key -> (sheet, base key or None)
KEYS = {
    "dino": ("dino", None), "dino_red": ("dino", "dino"), "dino_gold": ("dino", "dino"),
    "golem": ("golem", None), "golem_blue": ("golem", "golem"), "golem_green": ("golem", "golem"),
    "slime": ("slime", None), "slime_red": ("slime", "slime"), "slime_blue": ("slime", "slime"),
    "mario": ("mario", None), "luigi": ("mario", None), "mario_fire": ("mario", None),
    "bomber_w": ("bomber", None), "bomber_b": ("bomber", None),
}
ANIM_ORDER = ["idle", "run", "attack", "attack2", "hurt", "death", "jump", "proj", "proj2"]
REQUIRED = ANIM_ORDER[:-1]
ANIM_FPS = {"idle": 6, "run": 10, "attack": 10, "attack2": 10, "hurt": 8, "death": 8, "jump": 8,
            "proj": 10, "proj2": 10}
CENTRE_ANCHORED = {"proj", "proj2"}
# when an anim is missing from CELLS, fill from (in order) these anims of the same key
FILL_FROM = {"attack2": ["attack"], "jump": ["run", "idle"], "hurt": ["idle"], "death": ["hurt", "idle"],
             "run": ["idle"], "attack": ["idle"], "idle": ["run"]}
MAX_FRAMES = 8
OUTLINE = (20, 20, 22, 255)
DARK_LUMA = 70

# Which sheets face LEFT by default (mirror every frame); FACING[key][anim] overrides per anim
# with "left" / "right" (set after looking at the contact sheets).
FACING_LEFT = {"dino": False, "golem": False, "slime": False, "mario": True, "bomber": False}
FACING: dict[str, dict[str, str]] = {}

# ---------------------------------------------------------------------------------------- CELLS
# CELLS[key][anim] = list of cell specs, one frame each:
#   (row, col)             one cell
#   (row, col0, col1)      union of cells col0..col1 (inclusive) of that row (detached parts)
#   ("stack", (r, c), (r2, c2), overlap)   Bomberman: head cell over body cell, body top at head
#                                          bottom + 1 - overlap, body centred under the head
#   ("split", (r, c), n, i)  i-th of n equal-width slices of a cell holding n sprites side by side
# Hand picked from tools/contact/<sheet>_cells_<n>.png (connected-component cells, see detect_cells).
CELLS: dict[str, dict[str, list]] = {
    # -- 적 (1).png : armoured dinosaur, faces right ---------------------------------------------
    "dino": {
        "idle": [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)],          # row 1: standing, arms shifting
        "run": [(3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5)],   # row 3: charging run (3,6 = skid)
        "attack": [(6, 0), (6, 1), (6, 2), (6, 3)],                # row 6: crouch, lunge, bite, stretch
        "attack2": [(13, 0), (13, 1), (13, 2)],                    # row 13: rear up, inhale, fire roar
        "hurt": [(12, 0), (12, 1), (12, 2)],                       # row 12: stunned, sparks
        "death": [(12, 3), (12, 4), (12, 5), (12, 6)],             # row 12: falls back, lies flat
        "jump": [(7, 0), (7, 4)],                                  # row 7: crouch, airborne
        "proj": [("split", (13, 3), 4, i) for i in range(4)],      # 4 small flames in one cell
        "proj2": [(14, 3), (14, 4)],                               # long fire-breath streams
    },
    "dino_red": {"attack2": [(14, 0), (14, 1), (14, 2)]},         # red rows: same 3 fire-roar poses
    "dino_gold": {"attack2": [(15, 0), (15, 1), (15, 2)],
                  "proj2": [(15, 3), (15, 4)]},                    # gold: big fireballs
    # -- 적 (3).png : rock golem, faces right ------------------------------------------------------
    "golem": {
        "idle": [(1, 0), (1, 1), (1, 2), (1, 3)],                  # row 1: standing, thumb flick
        "run": [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (2, 7)],   # row 2: heavy walk
        "attack": [(4, 5), (4, 4), (4, 3), (4, 0)],                # row 4: elbow wind-up, punches
        "attack2": [(7, 0), (7, 1), (7, 2)],                       # row 7: raise rock, orb throw
        "hurt": [(12, 0), (12, 1), (12, 2)],                       # row 12: stunned, sparks
        "death": [(12, 3), (12, 4), (12, 5), (12, 6)],             # row 12: crumbles, lies flat
        "jump": [(5, 4)],                                          # row 5: leap, arms up
        "proj": [(7, 3)],                                          # rock ball
        "proj2": [(9, 3)],                                         # green poison ball
    },
    "golem_blue": {"attack2": [(8, 0), (8, 1), (8, 2)], "proj": [(8, 3), (8, 4)]},   # ice chunks
    "golem_green": {"attack2": [(9, 0), (9, 1), (9, 2)], "proj2": [(9, 3)]},
    # -- 적 (4).png : green slime brute, faces right ------------------------------------------------
    "slime": {
        "idle": [(0, 0), (0, 1), (0, 2), (0, 3)],                  # row 0: standing, fist pumping
        "run": [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4)],           # row 2: run
        "attack": [(3, 4), (3, 3), (3, 5)],                        # row 3: punch, hook, lunge spit
        "attack2": [(9, 0), (9, 1), (9, 2), (9, 3), (9, 4)],       # row 9: balled up, rolling
        "hurt": [(11, 0), (11, 1), (11, 2)],                       # row 11: hunched, hands on face
        "death": [(11, 3), (11, 4), (11, 5), (11, 6)],             # row 11: falls, puddles
        "jump": [(8, 0), (8, 1)],                                  # row 8: crouch, leap
        "proj": [(3, 6), (3, 7), (3, 8)],                          # slime droplets
    },
    "slime_red": {"attack": [(17, 2), (17, 3)], "proj": [(17, 4), (17, 5), (17, 6)]},
    "slime_blue": {"attack": [(18, 2), (18, 3)], "proj": [(18, 4), (18, 5), (18, 6)]},
    # -- 적 (2).png : SMB3 (faces left -> mirrored) --------------------------------------------------
    "mario": {
        "idle": [(1, 0)], "run": [(1, 1), (1, 2), (1, 3)], "attack": [(1, 8), (1, 9), (1, 10)],
        "hurt": [(1, 4)], "death": [(1, 17)], "jump": [(1, 6)],
    },
    "luigi": {
        "idle": [(3, 0)], "run": [(3, 1), (3, 2), (3, 3)], "attack": [(3, 8), (3, 9), (3, 10)],
        "hurt": [(3, 4)], "death": [(3, 17)], "jump": [(3, 6)],
    },
    "mario_fire": {
        "idle": [(11, 0)], "run": [(11, 1), (11, 2), (11, 0)], "attack": [(11, 16), (11, 15)],   # wind-up, throw
        "hurt": [(11, 4)], "death": [(12, 0), (12, 1), (12, 2), (12, 3)], "jump": [(11, 6)],
        "proj": [(12, 10), (12, 11), (12, 12), (12, 13)],
    },
    # -- 적 (1).gif : Bomberman, head row + body row (white block rows 0-20, black block +21) -------
    "bomber_w": {
        "idle": [("stack", (0, 21), (1, 21), 1)],
        "run": [("stack", (0, c), (1, c), 1) for c in range(22, 28)],          # right-facing walk
        "attack": [("stack", (11, c), (12, c), 1) for c in range(12, 16)],     # right-facing throw
        "hurt": [("stack", (2, 3), (3, 3), 1), ("stack", (4, 1), (5, 1), 1)],  # shocked, dizzy
        "death": [("stack", (19, c), (20, c), 1) for c in range(0, 10)],       # spin, dissolve
    },
    "bomber_b": {
        "idle": [("stack", (21, 21), (22, 21), 1)],
        "run": [("stack", (21, c), (22, c), 1) for c in range(22, 28)],
        "attack": [("stack", (32, c), (33, c), 1) for c in range(12, 16)],
        "hurt": [("stack", (23, 3), (24, 3), 1), ("stack", (25, 1), (26, 1), 1)],
        "death": [("stack", (40, c), (41, c), 1) for c in range(0, 10)],
    },
}


# ------------------------------------------------------------------------------- cell detection
def load_sheet(sheet: str):
    """(rgba image, is_bg(pixel) predicate)."""
    img = Image.open(SHEETS[sheet]).convert("RGBA")
    p0 = img.getpixel((0, 0))
    bg = {p0[:3]} | BG_EXTRA.get(sheet, set())

    def is_bg(p):
        return p[3] == 0 or p[:3] in bg

    return img, is_bg


def detect_cells(img: Image.Image, is_bg, min_cell: int = 6, dilate: int = 1):
    """Rows of cell boxes (x0, y0, x1, y1; exclusive): connected components of non-background
    pixels (8-connected, 1-px gaps bridged), grouped into rows by vertical overlap; rows top to
    bottom, cells left to right."""
    w, h = img.size
    px = img.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if not is_bg(px[x, y]):
                mp[x, y] = 255
    dil = (mask.filter(ImageFilter.MaxFilter(3)) if dilate else mask).load()
    # scanline union-find over runs of the dilated mask
    parent: list[int] = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    runs_prev: list[tuple[int, int, int]] = []          # (x0, x1, id) of the previous line
    run_rows: list[tuple[int, int, int, int]] = []       # (y, x0, x1, id)
    for y in range(h):
        runs, x = [], 0
        while x < w:
            if not dil[x, y]:
                x += 1
                continue
            x0 = x
            while x < w and dil[x, y]:
                x += 1
            rid = len(parent)
            parent.append(rid)
            for (px0, px1, pid) in runs_prev:
                if px0 <= x and x0 <= px1:                 # touching/overlapping (8-conn)
                    union(pid, rid)
            runs.append((x0, x, rid))
            run_rows.append((y, x0, x, rid))
        runs_prev = runs
    boxes: dict[int, list[int]] = {}
    for y, x0, x1, rid in run_rows:
        r = find(rid)
        b = boxes.get(r)
        if b is None:
            boxes[r] = [x0, y, x1, y + 1]
        else:
            b[0], b[1], b[2], b[3] = min(b[0], x0), min(b[1], y), max(b[2], x1), max(b[3], y + 1)
    cells = []
    for x0, y0, x1, y1 in boxes.values():
        # shrink the dilated bbox back to the real foreground pixels
        xs = [x for x in range(max(0, x0), min(w, x1)) for y in range(max(0, y0), min(h, y1)) if mp[x, y]]
        if not xs:
            continue
        ys = [y for x in range(max(0, x0), min(w, x1)) for y in range(max(0, y0), min(h, y1)) if mp[x, y]]
        bx0, bx1, by0, by1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
        if bx1 - bx0 >= min_cell and by1 - by0 >= min_cell:
            cells.append((bx0, by0, bx1, by1))
    cells.sort(key=lambda c: (c[1], c[0]))
    # two passes: typical-height cells define the rows, oversized cells (palette tables, lightning
    # columns, mugshots) attach afterwards to the row they overlap most instead of bridging rows
    hs = sorted(c[3] - c[1] for c in cells)
    typical = hs[len(hs) // 2] * 2.2 if hs else 0
    rows: list[list] = []
    ranges: list[list[int]] = []
    big = []
    for c in cells:
        if c[3] - c[1] > typical:
            big.append(c)
            continue
        placed = False
        for row, rng in zip(rows, ranges):
            ov = min(c[3], rng[1]) - max(c[1], rng[0])
            if ov > 0.4 * min(c[3] - c[1], rng[1] - rng[0]):
                row.append(c)
                rng[0], rng[1] = min(rng[0], c[1]), max(rng[1], c[3])
                placed = True
                break
        if not placed:
            rows.append([c])
            ranges.append([c[1], c[3]])
    for c in big:
        best, best_ov = None, 0
        for i, rng in enumerate(ranges):
            ov = min(c[3], rng[1]) - max(c[1], rng[0])
            if ov > best_ov:
                best, best_ov = i, ov
        if best is None:
            rows.append([c])
            ranges.append([c[1], c[3]])
        else:
            rows[best].append(c)
    order = sorted(range(len(rows)), key=lambda i: ranges[i][0])
    return [sorted(rows[i], key=lambda c: c[0]) for i in order]


def contact_sheets(sheet: str, img: Image.Image, rows, out_dir: str, zoom: int = 1,
                   chunk_h: int = 700) -> list[str]:
    """Labelled contact sheets (sheet pixels with 'r,c' tags), chunked to ~chunk_h tall (pre-zoom)."""
    os.makedirs(out_dir, exist_ok=True)
    rgb = img.convert("RGB")
    paths, start, part = [], 0, 0
    while start < len(rows):
        end, height = start, 0
        while end < len(rows):
            rh = max(c[3] - c[1] for c in rows[end]) + 14
            if height and height + rh > chunk_h:
                break
            height += rh
            end += 1
        page = Image.new("RGB", (rgb.width * zoom, height * zoom), (40, 40, 40))
        draw = ImageDraw.Draw(page)
        y = 0
        for r in range(start, end):
            rh = max(c[3] - c[1] for c in rows[r])
            for c, (x0, y0, x1, y1) in enumerate(rows[r]):
                cell = rgb.crop((x0, y0, x1, y1))
                if zoom != 1:
                    cell = cell.resize(((x1 - x0) * zoom, (y1 - y0) * zoom), Image.NEAREST)
                page.paste(cell, (x0 * zoom, (y + 12) * zoom))
                draw.rectangle((x0 * zoom, (y + 12) * zoom, x1 * zoom - 1, (y + 12 + (y1 - y0)) * zoom - 1),
                               outline=(255, 255, 0))
                draw.text((x0 * zoom + 1, y * zoom + 1), f"{r},{c}", fill=(255, 255, 255))
            y += rh + 14
        path = os.path.join(out_dir, f"{sheet}_cells_{part}.png")
        page.save(path)
        paths.append(path)
        start, part = end, part + 1
    return paths


# --------------------------------------------------------------------------------- frame cutting
def cut_cell(img: Image.Image, is_bg, box) -> dict:
    """{(x, y): (r, g, b, 255)} of non-background pixels inside a cell box (sheet coords)."""
    x0, y0, x1, y1 = box
    px = img.load()
    res = {}
    for y in range(y0, y1):
        for x in range(x0, x1):
            p = px[x, y]
            if not is_bg(p):
                res[(x, y)] = (p[0], p[1], p[2], 255)
    return res


def cell_pixels(img, is_bg, rows, spec, where: str) -> dict:
    """Resolve one CELLS spec to a pixel dict (sheet coords, stacked parts re-positioned)."""
    def one(r, c):
        if r >= len(rows) or c >= len(rows[r]):
            raise ValueError(f"{where}: cell ({r},{c}) does not exist")
        pix = cut_cell(img, is_bg, rows[r][c])
        if not pix:
            raise ValueError(f"{where}: cell ({r},{c}) is empty")
        return pix

    if spec[0] == "split":
        _, (r, c), n, i = spec
        pix = one(r, c)
        x0, x1 = min(x for x, _ in pix), max(x for x, _ in pix) + 1
        lo, hi = x0 + (x1 - x0) * i // n, x0 + (x1 - x0) * (i + 1) // n
        return {(x, y): p for (x, y), p in pix.items() if lo <= x < hi}
    if spec[0] == "stack":
        _, head, body, overlap = spec
        hp, bp = one(*head), one(*body)
        head_bottom = max(y for _, y in hp)
        body_top = min(y for _, y in bp)
        dy = (head_bottom + 1 - overlap) - body_top
        # centre the body under the head horizontally
        hx = (min(x for x, _ in hp) + max(x for x, _ in hp)) / 2
        bx = (min(x for x, _ in bp) + max(x for x, _ in bp)) / 2
        dx = int(round(hx - bx))
        out = {(x + dx, y + dy): p for (x, y), p in bp.items()}
        out.update(hp)                      # head drawn over the body
        return out
    if len(spec) == 2:
        return one(*spec)
    r, c0, c1 = spec
    out = {}
    for c in range(c0, c1 + 1):
        out.update(one(r, c))
    return out


def build_frame(pixels: dict, mirror: bool, centre: bool = False):
    """{(x, y): rgba} -> outlined (w, h, ax, ay, rgba bytes); anchor = bottom-centre of the opaque
    bbox or the frame centre (projectiles).  ``mirror`` flips horizontally (left-facing sources)."""
    xs = [x for x, _ in pixels]
    ys = [y for _, y in pixels]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    x0, y0 = bx0 - 1, by0 - 1                                  # 1-px pad for the outline
    w, h = bx1 - bx0 + 3, by1 - by0 + 3
    grid = [[None] * w for _ in range(h)]
    for (x, y), p in pixels.items():
        grid[y - y0][x - x0] = p
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
                out += bytes(OUTLINE) if edge else b"\x00\x00\x00\x00"
            else:
                out += bytes(p)
    ax = 1 + (bx1 - bx0) // 2
    ay = h - 2
    if mirror:
        mirrored = bytearray()
        for y in range(h):
            row = out[y * w * 4:(y + 1) * w * 4]
            mirrored += b"".join(row[i:i + 4] for i in range(len(row) - 4, -1, -4))
        out = mirrored
        ax = w - 1 - ax
    if centre:
        ax, ay = w // 2, h // 2
    return w, h, ax, ay, bytes(out)


def subsample(items: list, n: int = MAX_FRAMES) -> list:
    if len(items) <= n:
        return items
    return [items[int(i * len(items) / n)] for i in range(n)]


# ------------------------------------------------------------------------------------ recolour
def frame_pixels(frame) -> list[tuple[int, int, int, int]]:
    w, h, _ax, _ay, data = frame
    return [tuple(data[i:i + 4]) for i in range(0, len(data), 4)]


def dominant_hue(frames) -> tuple[float, float, float]:
    """Saturation-weighted mean (hue, sat, val) of the opaque non-outline pixels of some frames."""
    sx = sy = 0.0
    sats, vals = [], []
    for fr in frames:
        for r, g, b, a in frame_pixels(fr):
            if a == 0 or (r, g, b, a) == OUTLINE:
                continue
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if ss < 0.25 or vv < 0.2:
                continue
            import math
            sx += math.cos(hh * 6.283185) * ss
            sy += math.sin(hh * 6.283185) * ss
            sats.append(ss)
            vals.append(vv)
    import math
    hue = (math.atan2(sy, sx) / 6.283185) % 1.0
    return hue, (sum(sats) / len(sats) if sats else 0.0), (sum(vals) / len(vals) if vals else 0.0)


def learn_lut(base_frames, var_frames) -> dict:
    """Exact colour map from pose-identical (base, variant) frame pairs (same size)."""
    lut: dict = {}
    votes: dict = {}
    for bf, vf in zip(base_frames, var_frames):
        if bf[:2] != vf[:2]:
            continue
        for bp, vp in zip(frame_pixels(bf), frame_pixels(vf)):
            if bp[3] == 0 or vp[3] == 0 or bp == OUTLINE or vp == OUTLINE:
                continue
            votes.setdefault(bp, Counter())[vp] += 1
    for bp, c in votes.items():
        lut[bp] = c.most_common(1)[0][0]
    return lut


def recolour(frame, lut: dict, hue_delta: float, sat_mul: float):
    """Apply the learnt LUT, hue-shifting (and re-saturating) every colour it does not know."""
    w, h, ax, ay, data = frame
    out = bytearray()
    cache: dict = {}
    for i in range(0, len(data), 4):
        p = tuple(data[i:i + 4])
        if p[3] == 0 or p == OUTLINE:
            out += bytes(p)
            continue
        q = lut.get(p)
        if q is None:
            q = cache.get(p)
            if q is None:
                r, g, b, a = p
                hh, ss, vv = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if ss >= 0.12:
                    hh = (hh + hue_delta) % 1.0
                    ss = max(0.0, min(1.0, ss * sat_mul))
                r2, g2, b2 = colorsys.hsv_to_rgb(hh, ss, vv)
                q = cache[p] = (int(r2 * 255 + 0.5), int(g2 * 255 + 0.5), int(b2 * 255 + 0.5), 255)
        out += bytes(q)
    return w, h, ax, ay, bytes(out)


# -------------------------------------------------------------------------- synthesized sprites
def _draw_to_frame(pattern: list[str], palette: dict[str, tuple], centre: bool = True):
    """ASCII pixel art -> frame; '.' transparent, other chars looked up in palette (rgb)."""
    pixels = {}
    for y, line in enumerate(pattern):
        for x, ch in enumerate(line):
            if ch != ".":
                r, g, b = palette[ch]
                pixels[(x + 4, y + 4)] = (r, g, b, 255)
    return build_frame(pixels, mirror=False, centre=centre)


FIRE_PAL = {"o": (232, 88, 16), "y": (248, 184, 40), "w": (252, 244, 180), "r": (176, 40, 8)}
FIREBALL = [
    [".oooo...", "oyyyyo..", "oywwyyo.", "oywwyyoo", "oyyyyyoo", ".oyyyoo.", "..oooo..", "........"],
    ["..oooo..", ".oyyyyo.", "oyywwyyo", "oyywwyyo", ".oyyyyo.", "..oooo..", "........", "........"],
    ["...oooo.", "..oyyyyo", ".oyywwyo", "ooyywwyo", "ooyyyyyo", ".ooyyyo.", "..oooo..", "........"],
    ["..oooo..", ".oyyyyo.", "oyyyyyyo", "oywwyyyo", ".oywwyo.", "..oooo..", "........", "........"],
]
BOMB_PAL = {"k": (28, 28, 34), "g": (70, 70, 84), "h": (120, 120, 140), "f": (200, 160, 80),
            "s": (252, 220, 60), "r": (240, 80, 30)}
BOMB = [
    ["......f.........", ".....f..........", ".....kk.........", "....kkkk........", "..kkkkkkkk......",
     ".kkkhhkkkkk.....", ".kkhhkkkkkk.....", "kkkhkkkkkkkk....", "kkkkkkkkkkkk....", "kkkkkkkkkkkk....",
     ".kkkkkkkkkk.....", ".kkkkkkkkkk.....", "..kkkkkkkk......", "....kkkk........", "................",
     "................"],
    ["......s.........", ".....fs.........", ".....kk.........", "....kkkk........", "..kkkkkkkk......",
     ".kkkhhkkkkk.....", ".kkhhkkkkkk.....", "kkkhkkkkkkkk....", "kkkkkkkkkkkk....", "kkkkkkkkkkkk....",
     ".kkkkkkkkkk.....", ".kkkkkkkkkk.....", "..kkkkkkkk......", "....kkkk........", "................",
     "................"],
    [".....rs.........", ".....fr.........", ".....gg.........", "....gggg........", "..gggggggg......",
     ".ggghhggggg.....", ".gghhgggggg.....", "ggghgggggggg....", "gggggggggggg....", "gggggggggggg....",
     ".gggggggggg.....", ".gggggggggg.....", "..gggggggg......", "....gggg........", "................",
     "................"],
]
SLIME_PAL = {"g": (56, 168, 56), "l": (120, 232, 96), "d": (24, 104, 32)}
SLIME_BLOB = [
    ["..gggg..", ".gllllg.", "gllllllg", "glllllgg", "gllllggg", ".gggggd.", "..dddd..", "........"],
    ["...ggg..", "..glllg.", ".glllllg", "gllllllg", "glllllgg", ".ggggggd", "...dddd.", "........"],
    ["........", "..gggg..", ".gllllg.", "gllllllg", "gllllggg", "glllgggd", ".gddddd.", "........"],
]


def synth(kind: str):
    if kind == "fireball":
        return [_draw_to_frame(p, FIRE_PAL) for p in FIREBALL]
    if kind == "bomb":
        return [_draw_to_frame(p, BOMB_PAL) for p in BOMB]
    if kind == "slime":
        return [_draw_to_frame(p, SLIME_PAL) for p in SLIME_BLOB]
    raise KeyError(kind)


SYNTH_PROJ = {"mario": "fireball", "luigi": "fireball", "mario_fire": "fireball",
              "bomber_w": "bomb", "bomber_b": "bomb", "slime": "slime", "slime_red": "slime",
              "slime_blue": "slime"}


# --------------------------------------------------------------------------------------- import
_SHEET_CACHE: dict = {}


def sheet_data(sheet: str):
    if sheet not in _SHEET_CACHE:
        img, is_bg = load_sheet(sheet)
        rows = detect_cells(img, is_bg, MIN_CELL[sheet], DILATE[sheet])
        _SHEET_CACHE[sheet] = (img, is_bg, rows)
    return _SHEET_CACHE[sheet]


def own_frames(key: str) -> dict[str, list]:
    """{anim: [frame...]} for the anims the key has cells for (raw, before filling)."""
    sheet = KEYS[key][0]
    img, is_bg, rows = sheet_data(sheet)
    res = {}
    for anim, specs in CELLS.get(key, {}).items():
        face = FACING.get(key, {}).get(anim)
        mirror = FACING_LEFT[sheet] if face is None else (face == "left")
        frames = []
        for spec in subsample(list(specs)):
            pix = cell_pixels(img, is_bg, rows, spec, f"{key}/{anim}")
            frames.append(build_frame(pix, mirror, centre=anim in CENTRE_ANCHORED))
        res[anim] = frames
    return res


def import_key(key: str, base: dict[str, list] | None) -> dict[str, list]:
    """Complete {anim: [frame...]} for a key (own cells, recoloured base fill, synth proj)."""
    mine = own_frames(key)
    result = dict(mine)
    if base is not None:
        # learn the palette swap from pose-identical frames: same size and same alpha silhouette
        def mask(f):
            return bytes(f[4][i + 3] for i in range(0, len(f[4]), 4))
        base_frames = [b for fr in base.values() for b in fr]
        pairs_b, pairs_v = [], []
        for fr in mine.values():
            for v in fr:
                mv = mask(v)
                best, best_diff = None, None
                for b in base_frames:
                    if b[:2] != v[:2]:
                        continue
                    mb = mask(b)
                    diff = sum(1 for x, y in zip(mb, mv) if x != y)
                    if best is None or diff < best_diff:
                        best, best_diff = b, diff
                if best is not None and best_diff <= 0.03 * len(mv):
                    pairs_b.append(best)
                    pairs_v.append(v)
        lut = learn_lut(pairs_b, pairs_v)
        bh, bs, _ = dominant_hue([f for fr in base.values() for f in fr if fr])
        vh, vs, _ = dominant_hue([f for fr in mine.values() for f in fr if fr])
        delta = vh - bh
        sat_mul = (vs / bs) if bs > 0.05 else 1.0
        for anim, bf in base.items():
            if anim not in result:
                # projectiles keep their own colours (fire stays fire, rock stays rock)
                result[anim] = list(bf) if anim in CENTRE_ANCHORED else [recolour(f, lut, delta, sat_mul) for f in bf]
        print(f"  {key}: own {sorted(mine)}; {len(pairs_b)} matched poses, LUT {len(lut)} colours, hue shift {delta * 360:+.0f} deg, "
              f"sat x{sat_mul:.2f} for {sorted(set(base) - set(mine))}")
    if "proj" not in result:
        result["proj"] = synth(SYNTH_PROJ[key])
        print(f"  {key}: synthesized proj ({SYNTH_PROJ[key]})")
    for anim in REQUIRED:
        if anim not in result:
            for src in FILL_FROM[anim]:
                if src in result:
                    fr = result[src]
                    result[anim] = [fr[0]] if anim in ("jump", "hurt") and src in ("run", "idle") else list(fr)
                    print(f"  {key}: filled {anim} <- {src}")
                    break
            else:
                raise ValueError(f"{key}: cannot fill {anim}")
    return {a: result[a] for a in ANIM_ORDER if a in result}


def write_previews(key: str, anims: dict[str, list], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    for anim, fr in anims.items():
        mh = max(f[1] for f in fr) + 8
        sheet = Image.new("RGBA", (sum(f[0] + 6 for f in fr) + 6, mh + 12), (110, 110, 110, 255))
        draw = ImageDraw.Draw(sheet)
        x = 6
        for i, (w, h, ax, ay, data) in enumerate(fr):
            im = Image.frombytes("RGBA", (w, h), data)
            sheet.alpha_composite(im, (x, mh - h))
            draw.point((x + ax, mh - h + ay), fill=(0, 255, 0, 255))
            draw.text((x, mh + 1), str(i), fill=(255, 255, 255, 255))
            x += w + 6
        sheet.save(os.path.join(out_dir, f"{key}_{anim}.png"))


def b64_lines(data: bytes, width: int = 100) -> str:
    s = base64.b64encode(zlib.compress(data, 9)).decode("ascii")
    return "\n".join(f"    '{s[i:i + width]}'" for i in range(0, len(s), width))


def main(argv):
    if "--contact" in argv:
        for sheet in SHEETS:
            img, is_bg, rows = sheet_data(sheet)
            print(f"{sheet}: {len(rows)} rows, cells per row: {[len(r) for r in rows]}")
            for p in contact_sheets(sheet, img, rows, CONTACT_DIR, CONTACT_ZOOM[sheet]):
                print("  ->", p)
        return 0
    parts = ['"""GENERATED by tools/import_enemy_sheets.py - do not edit by hand.',
             "",
             "Monster RGBA frames cut from the sheets in 적/ (dino / golem / slime / mario / bomber).",
             "ENEMY_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba); rgba = w*h*4 bytes, row major,",
             "1x, facing right, anchor = bottom-centre of the opaque bbox (feet); 'proj' / 'proj2' frames",
             "(projectile sprites, flying right) are anchored at their centre (w//2, h//2).",
             "ENEMY_ANIMS[key][anim] = [frame_id...] for idle/run/attack/attack2/hurt/death/jump/proj(/proj2);",
             "ENEMY_ANIM_FPS[key][anim] = fps; ENEMY_PROJ[key] = {'proj': (w, h)(, 'proj2': (w, h))};",
             "ENEMY_HIT[key] = (w, h) of idle frame 0 (1x hitbox reference).",
             '"""',
             "import base64 as _b64",
             "import zlib as _zlib",
             "",
             "ENEMY_FRAMES = {}",
             "ENEMY_ANIMS = {}",
             "ENEMY_ANIM_FPS = {}",
             "ENEMY_PROJ = {}",
             "ENEMY_HIT = {}",
             ""]
    preview = None if "--no-preview" in argv else CONTACT_DIR
    done: dict[str, dict[str, list]] = {}
    report = []
    for key, (sheet, base) in KEYS.items():
        if key not in CELLS:
            raise ValueError(f"no CELLS for {key}")
        anims = import_key(key, done.get(base) if base else None)
        done[key] = anims
        if preview:
            write_previews(key, anims, preview)
        frames, ids = {}, {}
        for anim, fr in anims.items():
            ids[anim] = []
            for i, f in enumerate(fr):
                fid = f"{key}_{anim}_{i}"
                frames[fid] = f
                ids[anim].append(fid)
        meta, blob = [], bytearray()
        for fid, (w, h, ax, ay, rgba) in frames.items():
            meta.append((fid, w, h, ax, ay, len(blob)))
            blob += rgba
        parts.append(f"_BLOB = _zlib.decompress(_b64.b64decode(\n{b64_lines(bytes(blob))}\n))")
        parts.append("_META = [")
        parts.extend(f"    {m!r}," for m in meta)
        parts.append("]")
        parts.append(f"ENEMY_FRAMES[{key!r}] = {{f: (w, h, ax, ay, _BLOB[o:o + w * h * 4]) "
                     f"for f, w, h, ax, ay, o in _META}}")
        parts.append(f"ENEMY_ANIMS[{key!r}] = {{")
        parts.extend(f"    {a!r}: {i!r}," for a, i in ids.items())
        parts.append("}")
        parts.append(f"ENEMY_ANIM_FPS[{key!r}] = {({a: ANIM_FPS[a] for a in ids})!r}")
        proj = {a: anims[a][0][:2] for a in ("proj", "proj2") if a in anims}
        parts.append(f"ENEMY_PROJ[{key!r}] = {proj!r}")
        hit = anims["idle"][0][:2]
        parts.append(f"ENEMY_HIT[{key!r}] = {hit!r}")
        parts.append("")
        line = (f"{key}: idle {hit[0]}x{hit[1]}, proj {proj}, "
                + " ".join(f"{a}={len(i)}" for a, i in ids.items()))
        print(line)
        report.append(line)
    parts.append("del _META, _BLOB")
    parts.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(parts))
    print(f"-> {OUT} ({os.path.getsize(OUT)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
