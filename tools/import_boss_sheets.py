"""Import the three KOF-style mid-boss sprite sheets into ``assets_boss.py``.

Dev-only script (Pillow).  Usage:

    python tools/import_boss_sheets.py            # writes assets_boss.py (+ per-anim previews)
    python tools/import_boss_sheets.py --contact  # only writes labelled contact sheets (cell picking aid)

Sources (palette PNGs, characters facing RIGHT):

* ``적/여자 보스.png`` -> key ``mai``  (Mai Shiranui)
* ``적/남자 보스.png`` -> key ``choi`` (Choi Bounge)
* ``적/뚱뚱보 보스.png`` -> key ``chang`` (Chang Koehan, iron ball on a chain)

Sheet layout: cells are magenta (#FF00FF) rectangles separated by 1-px black
lines / black filler areas.  One animation runs left-to-right along a row, several
sequences per row, wrapping to the next row.  Cells are detected as the runs of
non-black columns inside every black-separated row band, giving each cell
(row, col) indices; the animation table below (CELLS) is hand picked from the
contact sheets written by ``--contact``.

Every frame: opaque = pixels != magenta, cropped to the opaque bbox, alpha 0/255,
1-px dark outline where the silhouette edge is not already dark (same rule as
tools/import_char_sheets.py), anchor = bottom-centre of the bbox.  The "proj" anim
(the boss's projectile: mai fan / choi claw-wind slash / chang iron ball) is anchored
at its centre (w//2, h//2) instead - the game draws bullets around their centre.

Output: ``assets_boss.py`` with
    BOSS_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba)   (1x, facing right)
    BOSS_ANIMS[key] = {"idle","run","attack","attack2","hurt","death","jump","proj": [frame_id...]}
    BOSS_ANIM_FPS[key] = {anim: fps}
    BOSS_PROJ[key] = (w, h)            1x size of proj frame 0 (hitbox reference)
frame ids are ``<key>_<anim>_<n>``.
"""
from __future__ import annotations

import base64
import os
import sys
import zlib

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets_boss.py")
PREVIEW_DIR = os.environ.get("BOSS_PREVIEW_DIR") or os.path.join(HERE, "boss_preview")

SOURCES = {
    "mai": os.path.join(ROOT, "적", "여자 보스.png"),
    "choi": os.path.join(ROOT, "적", "남자 보스.png"),
    "chang": os.path.join(ROOT, "적", "뚱뚱보 보스.png"),
}
KEY_COLOR = (255, 0, 255)                     # cell background (palette index maps to exact #FF00FF)
BLACK = (0, 0, 0)
OUTLINE = (20, 20, 22, 255)
DARK_LUMA = 70                                # edge pixels darker than this already read as outline
ANIM_ORDER = ["idle", "run", "attack", "attack2", "hurt", "death", "jump", "proj"]
ANIM_FPS = {"idle": 8, "run": 10, "attack": 12, "attack2": 10, "hurt": 8, "death": 8, "jump": 8, "proj": 12}
CENTRE_ANCHORED = {"proj"}                    # anims anchored at the frame centre instead of the feet

# hand-picked cells per animation: list of (row, first col, count); ranges are concatenated in
# order, so a sequence may wrap rows or skip cells.  Picked from the --contact sheets.
CELLS = {
    "mai": {
        "idle": [(0, 0, 12)],                   # row 0: standing breathing loop (fan in hand)
        "run": [(0, 12, 6)],                    # row 0: walk forward (0,18.. is walk back)
        "attack": [(3, 5, 6)],                  # row 3: standing high kick (prep, kick, recover)
        "attack2": [(7, 12, 5)],                # row 7: Kachousen fan throw (crouch, throw, fan leaves)
        "hurt": [(4, 20, 2)],                   # row 4: heavy stand hit (head back, recoil)
        "death": [(5, 3, 3), (5, 10, 3)],       # row 5: knocked back, launched, flip, slide, face down, lying
        "jump": [(1, 1, 4)],                    # row 1: takeoff crouch, rise, apex, tuck
        "proj": [(15, 15, 4)],                  # row 15: thrown Kachousen - open fan tumbling, white blur trail
    },
    "choi": {
        "idle": [(0, 0, 6)],                    # row 0: hunched stance, claws twitching
        "run": [(0, 6, 6)],                     # row 0: hunched walk forward (0,12.. is walk back)
        "attack": [(6, 8, 1), (6, 10, 4)],      # row 6: overhead claw slash (6,9 is the slash fx cell, skipped)
        "attack2": [(7, 4, 6)],                 # row 7: crouched claw-forward spin (rolling claw special)
        "hurt": [(2, 3, 2)],                    # row 2: stand hit (head snapped back, doubled over)
        "death": [(5, 13, 4), (6, 3, 1), (7, 21, 1)],  # stagger, launched back x3, sliding on back, lying face up
        "jump": [(0, 20, 3), (0, 24, 1)],       # row 0: crouch, tuck x2, falling
        "proj": [(7, 19, 1), (11, 16, 1)],      # horizontal blue claw-wind slashes (thick, thin) - flicker loop
    },
    "chang": {
        "idle": [(0, 1, 8)],                    # row 0: standing stance, ball on the shoulder, breathing
        "run": [(0, 10, 5)],                    # row 0: heavy walk forward (0,15.. is the crouch)
        "attack": [(17, 5, 5)],                 # row 17: ball raised overhead, slammed down into the ground
        "attack2": [(6, 5, 6)],                 # row 6: wind-up, ball flung out forward on the chain, hangs, back
        "hurt": [(10, 4, 2)],                   # row 10: stand hit (head snapped back, torso back)
        "death": [(11, 6, 5)],                  # row 11: launched, flipped, falling, lands on back, lying
        "jump": [(9, 4, 5)],                    # row 9: crouch, rise x2, in the air x2 (chain flying)
        "proj": [(0, 0, 1)],                    # cell 0,0: the iron ball alone (no chain)
    },
}


# ----------------------------------------------------------------------------- cell detection
def detect_cells(img: Image.Image) -> list[list[tuple[int, int, int, int]]]:
    """Rows of cell boxes (x0, y0, x1, y1; exclusive) - rows top to bottom, cells left to right."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    row_has = [any(px[x, y] != BLACK for x in range(w)) for y in range(h)]
    bands, y = [], 0
    while y < h:
        if not row_has[y]:
            y += 1
            continue
        y0 = y
        while y < h and row_has[y]:
            y += 1
        bands.append((y0, y))
    rows = []
    for y0, y1 in bands:
        col_has = [any(px[x, yy] != BLACK for yy in range(y0, y1)) for x in range(w)]
        cells, x = [], 0
        while x < w:
            if not col_has[x]:
                x += 1
                continue
            x0 = x
            while x < w and col_has[x]:
                x += 1
            # trim the cell vertically to its own non-black rows (cells in a band may differ in height)
            ys = [yy for yy in range(y0, y1) if any(px[xx, yy] != BLACK for xx in range(x0, x))]
            if ys and (x - x0) >= 8 and (ys[-1] - ys[0]) >= 8:
                cells.append((x0, ys[0], x, ys[-1] + 1))
        if cells:
            rows.append(cells)
    return rows


def contact_sheets(key: str, img: Image.Image, rows, out_dir: str, chunk_h: int = 440) -> list[str]:
    """Write labelled contact sheets (source pixels with 'r,c' tags), split into ~chunk_h tall images."""
    os.makedirs(out_dir, exist_ok=True)
    rgb = img.convert("RGB")
    paths, start, part = [], 0, 0
    while start < len(rows):
        end, height = start, 0
        while end < len(rows):
            rh = max(c[3] - c[1] for c in rows[end]) + 16
            if height and height + rh > chunk_h:
                break
            height += rh
            end += 1
        sheet = Image.new("RGB", (rgb.width, height), (40, 40, 40))
        draw = ImageDraw.Draw(sheet)
        y = 0
        for r in range(start, end):
            rh = max(c[3] - c[1] for c in rows[r])
            for c, (x0, y0, x1, y1) in enumerate(rows[r]):
                sheet.paste(rgb.crop((x0, y0, x1, y1)), (x0, y + 14))
                draw.rectangle((x0, y + 14, x1 - 1, y + 14 + (y1 - y0) - 1), outline=(255, 255, 0))
                draw.text((x0 + 2, y + 1), f"{r},{c}", fill=(255, 255, 255))
            y += rh + 16
        path = os.path.join(out_dir, f"{key}_cells_{part}.png")
        sheet.save(path)
        paths.append(path)
        start, part = end, part + 1
    return paths


# ----------------------------------------------------------------------------- frame cutting
def cut_cell(rgb: Image.Image, box) -> dict:
    """{(x, y): (r, g, b, 255)} of non-key pixels inside a cell box (sheet coords)."""
    x0, y0, x1, y1 = box
    px = rgb.load()
    res = {}
    for y in range(y0, y1):
        for x in range(x0, x1):
            p = px[x, y]
            if p != KEY_COLOR:
                res[(x, y)] = (p[0], p[1], p[2], 255)
    return res


def build_frame(pixels: dict, centre: bool = False):
    """{(x, y): rgba} -> outlined (w, h, ax, ay, rgba bytes); anchor = bottom-centre of the opaque bbox,
    or the frame centre (w//2, h//2) when ``centre`` (projectiles)."""
    xs = [x for x, _ in pixels]
    ys = [y for _, y in pixels]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    x0, x1, y0, y1 = bx0 - 1, bx1 + 1, by0 - 1, by1 + 1        # 1-px pad for the outline
    w, h = x1 - x0 + 1, y1 - y0 + 1
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
    ax = (bx0 - x0) + (bx1 - bx0) // 2
    ay = by1 - y0
    # The sheets face LEFT; the game's base frames face RIGHT -> mirror every row.
    mirrored = bytearray()
    for y in range(h):
        row = out[y * w * 4:(y + 1) * w * 4]
        mirrored += b"".join(row[i:i + 4] for i in range(len(row) - 4, -1, -4))
    ax = w - 1 - ax
    if centre:
        ax, ay = w // 2, h // 2
    return w, h, ax, ay, bytes(mirrored)


def import_boss(key: str, preview_dir: str | None):
    img = Image.open(SOURCES[key])
    rgb = img.convert("RGB")
    rows = detect_cells(img)
    frames, anims = {}, {}
    for anim in ANIM_ORDER:
        ids = []
        for row, col0, count in CELLS[key][anim]:
            for col in range(col0, col0 + count):
                if row >= len(rows) or col >= len(rows[row]):
                    raise ValueError(f"{key}/{anim}: cell ({row},{col}) does not exist")
                pixels = cut_cell(rgb, rows[row][col])
                if not pixels:
                    raise ValueError(f"{key}/{anim}: cell ({row},{col}) is empty")
                fid = f"{key}_{anim}_{len(ids)}"
                frames[fid] = build_frame(pixels, centre=anim in CENTRE_ANCHORED)
                ids.append(fid)
        anims[anim] = ids
    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        for anim, ids in anims.items():
            fr = [frames[f] for f in ids]
            mh = max(f[1] for f in fr) + 8
            sheet = Image.new("RGBA", (sum(f[0] + 6 for f in fr) + 6, mh + 12), (110, 110, 110, 255))
            draw = ImageDraw.Draw(sheet)
            x = 6
            for i, (w, h, ax, ay, data) in enumerate(fr):
                im = Image.frombytes("RGBA", (w, h), data)
                sheet.alpha_composite(im, (x, mh - h))          # feet aligned on a common baseline
                draw.point((x + ax, mh - h + ay), fill=(0, 255, 0, 255))
                draw.text((x, mh + 1), str(i), fill=(255, 255, 255, 255))
                x += w + 6
            sheet.save(os.path.join(preview_dir, f"{key}_{anim}.png"))
    return frames, anims


def b64_lines(data: bytes, width: int = 100) -> str:
    s = base64.b64encode(zlib.compress(data, 9)).decode("ascii")
    return "\n".join(f"    '{s[i:i + width]}'" for i in range(0, len(s), width))


def main(argv):
    if "--contact" in argv:
        for key, path in SOURCES.items():
            img = Image.open(path)
            rows = detect_cells(img)
            print(f"{key}: {len(rows)} rows, cells per row: {[len(r) for r in rows]}")
            for p in contact_sheets(key, img, rows, PREVIEW_DIR):
                print("  ->", p)
        return 0
    parts = ['"""GENERATED by tools/import_boss_sheets.py - do not edit by hand.',
             "",
             "Mid-boss RGBA frames cut from 적/여자 보스.png (mai), 적/남자 보스.png (choi) and",
             "적/뚱뚱보 보스.png (chang).",
             "BOSS_FRAMES[key][frame_id] = (w, h, anchor_x, anchor_y, rgba); rgba = w*h*4 bytes, row major,",
             "1x, facing right, anchor = bottom-centre of the opaque bbox (feet); the 'proj' frames",
             "(projectile sprite, flying right) are anchored at their centre (w//2, h//2).",
             "BOSS_ANIMS[key][anim] = [frame_id...] for idle/run/attack/attack2/hurt/death/jump/proj;",
             "BOSS_ANIM_FPS[key][anim] = fps; BOSS_PROJ[key] = (w, h) of proj frame 0 (1x, hitbox reference).",
             '"""',
             "import base64 as _b64",
             "import zlib as _zlib",
             "",
             "BOSS_FRAMES = {}",
             "BOSS_ANIMS = {}",
             "BOSS_ANIM_FPS = {}",
             "BOSS_PROJ = {}",
             ""]
    preview = None if "--no-preview" in argv else PREVIEW_DIR
    for key in SOURCES:
        frames, anims = import_boss(key, preview)
        meta, blob = [], bytearray()
        for fid, (w, h, ax, ay, rgba) in frames.items():
            meta.append((fid, w, h, ax, ay, len(blob)))
            blob += rgba
        parts.append(f"_BLOB = _zlib.decompress(_b64.b64decode(\n{b64_lines(bytes(blob))}\n))")
        parts.append("_META = [")
        parts.extend(f"    {m!r}," for m in meta)
        parts.append("]")
        parts.append(f"BOSS_FRAMES[{key!r}] = {{f: (w, h, ax, ay, _BLOB[o:o + w * h * 4]) "
                     f"for f, w, h, ax, ay, o in _META}}")
        parts.append(f"BOSS_ANIMS[{key!r}] = {{")
        parts.extend(f"    {a!r}: {ids!r}," for a, ids in anims.items())
        parts.append("}")
        parts.append(f"BOSS_ANIM_FPS[{key!r}] = {dict(ANIM_FPS)!r}")
        pw, ph = frames[anims["proj"][0]][:2]
        parts.append(f"BOSS_PROJ[{key!r}] = ({pw}, {ph})")
        parts.append("")
        hs = [m[2] for m in meta if not m[0].startswith(f"{key}_proj_")]
        print(f"{key}: {len(meta)} frames, body height {min(hs)}..{max(hs)}, proj {pw}x{ph}, "
              + " ".join(f"{a}={len(i)}" for a, i in anims.items()))
    parts.append("del _META, _BLOB")
    parts.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(parts))
    print(f"-> {OUT} ({os.path.getsize(OUT)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
