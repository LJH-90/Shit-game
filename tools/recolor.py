"""Quantise + classify mapped frames and emit assets_data.py.

Dev-only (Pillow / numpy / scipy).  Usage:

    python tools/recolor.py

Reads tools/frames/f###.png (from extract_sprites.py) and tools/anim_map.py,
classifies every pixel into a body-part class with a 0-3 shade level, writes
``assets_data.py`` at the project root and a palette preview at
tools/preview.png.
"""
from __future__ import annotations

import base64
import colorsys
import os
import sys
import zlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from anim_map import ANIM_FPS, ANIM_MAP, FRAME_SCALE  # noqa: E402

FRAMES_DIR = os.path.join(HERE, "frames")
OUT_DATA = os.path.join(ROOT, "assets_data.py")
PREVIEW = os.path.join(HERE, "preview.png")

CLASSES = {0: "transparent", 1: "outline", 2: "hair", 3: "skin", 4: "shirt", 5: "pants",
           6: "gun", 7: "shoe", 8: "white", 9: "fx"}
C_TRANS, C_OUT, C_HAIR, C_SKIN, C_SHIRT, C_PANTS, C_GUN, C_SHOE, C_WHITE, C_FX = range(10)

N_COLORS = 18
MIN_COMPONENT = 10      # stray pixel clusters smaller than this are dropped


# --------------------------------------------------------------------------- load
def load_frame(idx: int) -> np.ndarray:
    im = Image.open(os.path.join(FRAMES_DIR, f"f{idx:03d}.png")).convert("RGBA")
    s = FRAME_SCALE.get(idx, 1.0)
    if abs(s - 1.0) > 1e-6:
        # premultiply so background does not bleed into edges when resampling
        a = np.asarray(im).astype(np.float32)
        rgb = a[..., :3] * (a[..., 3:4] / 255.0)
        pm = Image.fromarray(np.concatenate([rgb, a[..., 3:4]], axis=2).astype(np.uint8), "RGBA")
        pm = pm.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.BICUBIC)
        b = np.asarray(pm).astype(np.float32)
        al = b[..., 3:4]
        rgb = np.where(al > 0, b[..., :3] * 255.0 / np.maximum(al, 1), 0)
        b = np.concatenate([np.clip(rgb, 0, 255), al], axis=2).astype(np.uint8)
        b[..., 3] = np.where(b[..., 3] >= 110, 255, 0)
        return b
    return np.asarray(im).copy()


def clean_alpha(arr: np.ndarray) -> np.ndarray:
    """Drop tiny disconnected specks (grid remnants) from the alpha mask."""
    m = arr[..., 3] > 0
    lab, n = ndimage.label(m, structure=np.ones((3, 3)))
    if n > 1:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        for k, sl in enumerate(ndimage.find_objects(lab), start=1):
            bh = sl[0].stop - sl[0].start
            bw = sl[1].stop - sl[1].start
            # drop specks and thin dotted grid remnants (1-2 px wide/tall lines)
            keep[k] = sizes[k - 1] >= MIN_COMPONENT and min(bh, bw) > 2
        keep[0] = False
        m = keep[lab]
    # thin protrusions (dotted divider lines glued to the body): keep only the
    # parts of 1-2 px thin structures that hug the solid body
    solid = ndimage.binary_opening(m, structure=np.ones((3, 3)))
    if solid.any():
        m = m & ndimage.binary_dilation(solid, iterations=2)
    arr = arr.copy()
    arr[..., 3] = np.where(m, 255, 0)
    return arr


# --------------------------------------------------------------------------- classify
def quantize(arr: np.ndarray):
    """Return (index_map, palette_rgb list).

    Only opaque pixels are quantised (as a 1xN strip) with Pillow's
    MAXCOVERAGE method; MEDIANCUT averages this blurry art into mud.
    Transparent pixels get index -1.
    """
    alpha = arr[..., 3] > 0
    fg = arr[alpha][:, :3]
    im = Image.fromarray(fg.reshape(1, -1, 3), "RGB")
    q = im.quantize(colors=N_COLORS, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
    pal = q.getpalette()[: 3 * N_COLORS]
    colors = [tuple(pal[i:i + 3]) for i in range(0, len(pal), 3)]
    idx = np.full(alpha.shape, -1, np.int32)
    idx[alpha] = np.asarray(q, dtype=np.int32).ravel()
    return idx, colors


def hsv(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360.0, s, v


def family(rgb) -> str:
    """Coarse colour family of one palette entry (no spatial info)."""
    h, s, v = hsv(rgb)
    if v < 0.13 or (v < 0.2 and s < 0.35):
        return "outline"
    if s > 0.45 and v > 0.45 and (h < 14 or h > 335):
        return "fx"
    if s < 0.2:
        # neutral / barely tinted: white highlights, grey metal, or a pale
        # tint of one of the garments
        if v > 0.86 or (s < 0.07 and v > 0.72):
            return "white"
        if v < 0.66:
            return "gun"
        if 170 <= h <= 265:
            return "shirt"
        if 55 <= h < 170:
            return "pants"
        return "skin" if s > 0.1 else "white"
    if 175 <= h <= 265:
        return "shirt"
    if 55 <= h <= 174:
        return "pants"
    if 8 <= h <= 55:
        # brown / tan family: skin is light and moderately saturated,
        # everything darker or more saturated is hair-or-gun (decided spatially)
        if v > 0.55 and s < 0.6:
            return "skin"
        return "brown"
    if h < 8 or h > 335:
        return "brown"        # dull reddish brown
    return "gun"


def despeckle(cls: np.ndarray, iterations: int = 2) -> np.ndarray:
    """Replace class specks (fewer than 3 same-class 8-neighbours) with the
    majority class of their opaque neighbours.  Keeps 1-px lines mostly intact."""
    cls = cls.copy()
    h, w = cls.shape
    for _ in range(iterations):
        pad = np.pad(cls, 1, constant_values=0)
        neigh = np.stack([pad[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)
                          if not (dy == 1 and dx == 1)], axis=0)
        same = (neigh == cls[None]).sum(axis=0)
        opaque = cls > 0
        weak = opaque & (same < 3)
        if not weak.any():
            break
        counts = np.zeros((10, h, w), np.int32)
        for c in range(1, 10):
            counts[c] = (neigh == c).sum(axis=0)
        counts[0] = -1
        best = counts.argmax(axis=0)
        cls[weak] = best[weak]
    return cls


def classify(arr: np.ndarray):
    """Return (cls, shade) uint8 maps for an RGBA frame."""
    h, w = arr.shape[:2]
    alpha = arr[..., 3] > 0
    idx, colors = quantize(arr)
    fam = [family(c) for c in colors] + ["transparent"]
    fam_map = np.array(fam)[np.where(idx < 0, len(colors), idx)]

    cls = np.zeros((h, w), np.uint8)
    base_map = {"outline": C_OUT, "white": C_WHITE, "fx": C_FX, "shirt": C_SHIRT,
                "pants": C_PANTS, "gun": C_GUN, "skin": C_SKIN}
    for name, c in base_map.items():
        cls[fam_map == name] = c

    # ---- head locator: biggest skin blob (the face) -----------------------
    skin = fam_map == "skin"
    brown = fam_map == "brown"
    head_c = None
    lab, n = ndimage.label(skin, structure=np.ones((3, 3)))
    if n:
        sizes = ndimage.sum(skin, lab, range(1, n + 1))
        k = int(np.argmax(sizes)) + 1
        ys, xs = np.nonzero(lab == k)
        head_c = (ys.mean(), xs.mean())
        face_r = max(6.0, 1.9 * np.sqrt(sizes[k - 1]))
    else:
        face_r = 10.0
    # hair = brown pixels connected to / near the face; the rest is gun
    if head_c is not None:
        yy, xx = np.mgrid[0:h, 0:w]
        dist = np.sqrt((yy - head_c[0]) ** 2 + (xx - head_c[1]) ** 2)
        near = dist < face_r * 1.6
        # grow "hair" from brown pixels near the face through connected brown
        blab, bn = ndimage.label(brown, structure=np.ones((3, 3)))
        hair = np.zeros_like(brown)
        for k in range(1, bn + 1):
            comp = blab == k
            if (comp & near).sum() >= max(3, 0.12 * comp.sum()) and comp.sum() > 0:
                # component touches the head; but a gun stock may also touch the
                # head region -> only keep the part within a generous radius
                hair |= comp & (dist < face_r * 3.2)
        cls[brown & hair] = C_HAIR
        cls[brown & ~hair] = C_GUN
        # hands: skin far from the head that is small is still skin (keep),
        # but light rifle wood far from the head misclassified as skin -> gun
        for k in range(1, n + 1):
            comp = lab == k
            if comp.sum() < 4:
                continue
            cy, cx = ndimage.center_of_mass(comp)
            d = np.hypot(cy - head_c[0], cx - head_c[1])
            if d > face_r * 3.0 and comp.sum() > 0.35 * sizes.max():
                cls[comp] = C_GUN
    else:
        cls[brown] = C_HAIR

    # ---- shoes: dark/olive pixels in the bottom band that are not gun -------
    # (not attempted; boots in the sheet are outline-dark already)

    # ---- neutral greys: garment shading or actual gun metal? --------------
    # relabel each grey component by the class that borders it most
    grey = (fam_map == "gun") & (cls == C_GUN)
    glab, gn = ndimage.label(grey, structure=np.ones((3, 3)))
    if gn:
        ring_struct = np.ones((3, 3))
        for k in range(1, gn + 1):
            comp = glab == k
            ring = ndimage.binary_dilation(comp, structure=ring_struct) & ~comp
            nb = cls[ring]
            nb = nb[(nb != C_TRANS) & (nb != C_OUT) & (nb != C_GUN)]
            if nb.size == 0:
                continue
            n_p = int((nb == C_PANTS).sum())
            n_s = int((nb == C_SHIRT).sum())
            n_k = int((nb == C_SKIN).sum())
            tot = nb.size
            if comp.sum() < 25 and n_k >= 0.4 * tot:
                cls[comp] = C_SKIN          # hand shading, not a weapon
            elif n_p >= n_s and n_p >= 0.3 * tot:
                cls[comp] = C_PANTS
            elif n_s > n_p and n_s >= 0.3 * tot:
                cls[comp] = C_SHIRT

    # ---- positional garment fix (upright frames only) ----------------------
    # small run frames draw the trousers blue-grey and desaturated legs read
    # as "gun"; anything shirt/gun-coloured below the waist is trousers.
    if h >= 0.9 * w:
        n_opaque = max(1, int(alpha.sum()))
        pants_frac = float((cls == C_PANTS).sum()) / n_opaque
        waist = 0.58 if pants_frac < 0.06 else 0.72
        yy = np.arange(h)[:, None] / float(h)
        low = np.broadcast_to(yy > waist, cls.shape)
        cls[low & ((cls == C_SHIRT) | (cls == C_GUN))] = C_PANTS
    yy = np.arange(h)[:, None] / float(h)
    lowg = np.broadcast_to(yy > 0.7, cls.shape)
    cls[lowg & (cls == C_GUN) & grey] = C_PANTS

    cls[~alpha] = C_TRANS
    cls = despeckle(cls)
    cls[~alpha] = C_TRANS

    # ---- shades: per class, relative to that class's median value ---------
    vmap = arr[..., :3].max(axis=2).astype(np.float32) / 255.0
    vmap = ndimage.median_filter(vmap, size=3, mode="nearest")
    shade = np.full((h, w), 2, np.uint8)
    for c in range(1, 10):
        m = cls == c
        if not m.any():
            continue
        v = vmap[m]
        med = float(np.median(v))
        s = np.full(v.shape, 2, np.uint8)
        s[v < med - 0.10] = 1
        s[v < med - 0.26] = 0
        s[v > med + 0.11] = 3
        shade[m] = s
    shade[cls == C_OUT] = np.minimum(shade[cls == C_OUT], 1)

    # ---- edge halo removal ---------------------------------------------------
    # The sheet is a blurry upscale: the anti-aliased rim between the body and the
    # off-white background survives the alpha mask as pale/white pixels. Strip
    # any near-background or white-class pixel that sits within 2 px of
    # transparency (interior whites such as eyes/teeth are untouched).
    cross = ndimage.generate_binary_structure(2, 1)
    rgbmin = arr[..., :3].min(axis=2)
    bgish = (rgbmin > 205) & alpha
    for _ in range(3):
        near_t = ndimage.binary_dilation(cls == C_TRANS, structure=cross, iterations=2)
        kill = near_t & ((cls == C_WHITE) | bgish)
        if not kill.any():
            break
        cls[kill] = C_TRANS
    # 1-px slivers left hanging after the strip
    body = ndimage.binary_opening(cls != C_TRANS, structure=np.ones((2, 2)))
    cls[(cls != C_TRANS) & ~ndimage.binary_dilation(body, structure=cross)] = C_TRANS
    shade[cls == C_TRANS] = 0
    return cls, shade


# --------------------------------------------------------------------------- emit
def process_frame(idx: int):
    arr = clean_alpha(load_frame(idx))
    cls, shade = classify(arr)
    ys, xs = np.nonzero(cls)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    cls, shade = cls[y0:y1, x0:x1], shade[y0:y1, x0:x1]
    h, w = cls.shape
    data = ((cls.astype(np.uint16) << 4) | shade).astype(np.uint8).tobytes()
    return w, h, w // 2, h - 1, data


def write_assets(frames: dict, anims: dict):
    order = list(frames)
    blob = b"".join(frames[f][4] for f in order)
    comp = base64.b64encode(zlib.compress(blob, 9)).decode("ascii")
    lines = [
        '"""GENERATED by tools/recolor.py - do not edit by hand.',
        "",
        "Pixel classes (high nibble) / shade (low nibble, 0 dark .. 3 light).",
        "FRAMES: frame_id -> (w, h, anchor_x, anchor_y, data); data = w*h bytes, row major,",
        "each byte (class << 4) | shade. anchor = bottom-centre (feet).",
        '"""',
        "import base64 as _b64",
        "import zlib as _zlib",
        "",
        f"CLASSES = {CLASSES!r}",
        "",
        "_BLOB = _zlib.decompress(_b64.b64decode(",
    ]
    for i in range(0, len(comp), 96):
        lines.append(f"    {comp[i:i + 96]!r}")
    lines.append("))")
    lines.append("")
    lines.append("_META = [")
    off = 0
    for f in order:
        w, h, ax, ay, data = frames[f]
        lines.append(f"    ({f!r}, {w}, {h}, {ax}, {ay}, {off}),")
        off += len(data)
    lines.append("]")
    lines.append("")
    lines.append("FRAMES = {f: (w, h, ax, ay, _BLOB[o:o + w * h]) for f, w, h, ax, ay, o in _META}")
    lines.append("")
    lines.append(f"ANIMS = {anims!r}")
    lines.append("")
    lines.append(f"ANIM_FPS = {ANIM_FPS!r}")
    lines.append("")
    lines.append("del _META, _BLOB")
    lines.append("")
    with open(OUT_DATA, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# --------------------------------------------------------------------------- preview
def write_preview(frames, anims, palettes=("jaehwi", "intern", "lab1", "ceo"), scale=3):
    import importlib
    import sprites
    importlib.reload(importlib.import_module("assets_data"))
    importlib.reload(sprites)
    font = ImageFont.load_default(size=13)
    seq = [(a, i, f) for a, ids in anims.items() for i, f in enumerate(ids)]
    cell_w = max(frames[f][0] for f in frames) * scale + 6
    cell_h = max(frames[f][1] for f in frames) * scale + 6
    pals = list(palettes) + ["source"]
    W = cell_w * len(seq)
    H = (cell_h + 16) * len(pals)
    sheet = Image.new("RGB", (W, H), (70, 74, 80))
    d = ImageDraw.Draw(sheet)
    for r, pal in enumerate(pals):
        y = r * (cell_h + 16)
        for c, (a, i, f) in enumerate(seq):
            x = c * cell_w
            w, h, ax, ay, data = frames[f]
            if pal == "source":
                idx = int(f[1:4])
                src = clean_alpha(load_frame(idx))
                cls, _ = classify(src)
                ys, xs = np.nonzero(cls)
                src = src[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                im = Image.fromarray(src, "RGBA")
            else:
                _, _, rows = sprites.render_rgba_rows(f, pal, False, 1)
                im = Image.frombytes("RGBA", (w, h), b"".join(rows))
            im = im.resize((w * scale, h * scale), Image.NEAREST)
            tile = Image.new("RGBA", (cell_w, cell_h), (200, 204, 196, 255))
            tile.alpha_composite(im, (3, cell_h - 3 - im.height))
            sheet.paste(tile.convert("RGB"), (x, y + 16))
            if r == 0:
                d.text((x + 2, y + 1), f"{a}[{i}] {f}", fill=(255, 230, 0), font=font)
            elif c == 0:
                d.text((x + 2, y + 1), pal, fill=(255, 230, 0), font=font)
        d.text((2, y + 1), pal, fill=(120, 240, 120), font=font)
    sheet.save(PREVIEW)
    print(f"preview {PREVIEW} ({W}x{H})")


def main():
    frames = {}
    anims = {}
    for anim, idxs in ANIM_MAP.items():
        ids = []
        for idx in idxs:
            fid = f"f{idx:03d}"
            if fid not in frames:
                frames[fid] = process_frame(idx)
            ids.append(fid)
        anims[anim] = ids
    write_assets(frames, anims)
    size = os.path.getsize(OUT_DATA)
    print(f"{len(frames)} frames, {sum(len(v[4]) for v in frames.values())} px bytes -> "
          f"{OUT_DATA} ({size} bytes)")
    for a, ids in anims.items():
        print(f"  {a:13s} {len(ids)} frames  " + " ".join(f"{frames[f][0]}x{frames[f][1]}" for f in ids))
    write_preview(frames, anims)


if __name__ == "__main__":
    sys.exit(main())
