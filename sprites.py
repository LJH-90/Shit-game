"""Runtime sprite bank: palette-swapped, scaled, flipped tk.PhotoImage frames.

Pure standard library (zlib / struct / base64 / tkinter).  Pixel data comes from
the generated ``assets_data`` module (see tools/recolor.py); every frame is a
byte per pixel ``(class << 4) | shade`` and this module turns it into RGBA PNGs
for ``tk.PhotoImage(data=...)`` with real alpha transparency.
"""
from __future__ import annotations

import base64
import struct
import zlib

import assets_data

CLASSES = assets_data.CLASSES
CLASS_INDEX = {name: idx for idx, name in CLASSES.items()}

# shade multipliers, index = shade nibble (0 dark .. 3 light); shade 2 = base
SHADE_MUL = (0.55, 0.78, 1.0, 1.25)

_BLACK_HAIR = "#1c1c1c"
_SKIN = "#e6b48c"
_OUTLINE = "#141414"
_WHITE = "#f4f4f4"
_FX = "#e02828"
_SHOE = "#1e1e1e"
_GUN = "#3c3c40"
_BROWN_HAIR = "#6e4320"


def _pal(shirt, pants, hair=_BROWN_HAIR, gun=_GUN, skin=_SKIN, outline=_OUTLINE,
         white=_WHITE, fx=_FX, shoe=_SHOE):
    return {"outline": outline, "hair": hair, "skin": skin, "shirt": shirt,
            "pants": pants, "gun": gun, "shoe": shoe, "white": white, "fx": fx}


PALETTES: dict[str, dict[str, str]] = {
    # players
    "jaehwi": _pal("#b8b8b8", "#3a5a9c", hair=_BLACK_HAIR),
    "hyunki": _pal("#1f2a5c", "#8a8a8a", hair=_BLACK_HAIR),
    "dongil": _pal("#202020", "#242424", hair=_BLACK_HAIR),
    # grunts: white shirt -> progressively darker grey suits
    "intern": _pal("#f0f0f0", "#c4c4c4"),
    "staff": _pal("#d4d4d4", "#a0a0a0"),
    "assistant": _pal("#aaaaaa", "#7e7e7e"),
    "manager": _pal("#848484", "#5c5c5c"),
    # elites: navy / charcoal suits
    "deputy": _pal("#2e3c66", "#26324f"),
    "general": _pal("#3a3a46", "#2a2a34"),
    "teamlead": _pal("#242838", "#1a1d2a"),
    # mid bosses: black suits, greying hair
    "director": _pal("#26262c", "#1c1c20", hair="#5a5a5a"),
    "md": _pal("#202026", "#18181c", hair="#7a7a7a"),
    "evp": _pal("#1c1c22", "#141418", hair="#969696"),
    # final bosses
    "ceo": _pal("#1e1e26", "#16161c", hair="#505050", gun="#c9a227"),
    "chairman": _pal("#141418", "#0e0e12", hair="#e6e6e6"),
    # lab: white coat + grey pants
    "lab1": _pal("#f4f4f4", "#8c8c8c"),
    "lab2": _pal("#f4f4f4", "#808080"),
    "lab3": _pal("#f4f4f4", "#747474"),
    "lab4": _pal("#f4f4f4", "#666666"),
    "lab5": _pal("#f4f4f4", "#5a5a5a", hair="#a4a4a4"),
}


def hex_to_rgb(s: str) -> tuple[int, int, int]:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def shade_color(base_hex: str, shade: int) -> tuple[int, int, int]:
    """Base colour (shade 2) darkened / lightened by SHADE_MUL, clamped."""
    r, g, b = hex_to_rgb(base_hex)
    m = SHADE_MUL[max(0, min(3, shade))]
    return (min(255, int(r * m + 0.5)), min(255, int(g * m + 0.5)),
            min(255, int(b * m + 0.5)))


def palette_lut(palette: str) -> list[bytes]:
    """256-entry table: pixel byte -> 4-byte RGBA."""
    pal = PALETTES[palette]
    lut = [b"\x00\x00\x00\x00"] * 256
    for cls, name in CLASSES.items():
        if cls == 0:
            continue
        base = pal.get(name)
        if base is None:
            continue
        for shade in range(4):
            r, g, b = shade_color(base, shade)
            lut[(cls << 4) | shade] = bytes((r, g, b, 255))
    return lut


def _chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def encode_png(width: int, height: int, rgba_rows: list[bytes]) -> bytes:
    raw = b"".join(b"\x00" + row for row in rgba_rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(raw, 6)) + _chunk(b"IEND", b""))


def render_rgba_rows(frame_id: str, palette: str, flip: bool, scale: int,
                     lut: list[bytes] | None = None) -> tuple[int, int, list[bytes]]:
    """Return (width, height, rows) of RGBA bytes for a frame, scaled and flipped."""
    w, h, _ax, _ay, data = assets_data.FRAMES[frame_id]
    lut = lut or palette_lut(palette)
    rows = []
    for y in range(h):
        line = data[y * w:(y + 1) * w]
        if flip:
            line = line[::-1]
        if scale == 1:
            row = b"".join(lut[p] for p in line)
        else:
            row = b"".join(lut[p] * scale for p in line)
        rows.extend([row] * scale)
    return w * scale, h * scale, rows


class SpriteBank:
    """Cached tk.PhotoImage factory keyed by (anim, frame, palette, flip, scale)."""

    def __init__(self, tk_root, base_scale: int = 2):
        import tkinter as tk  # local import keeps module importable headless
        self._tk = tk
        self.root = tk_root
        self.base_scale = int(base_scale)
        self._cache: dict[tuple, object] = {}
        self._luts: dict[str, list[bytes]] = {}

    # -- lookups ---------------------------------------------------------
    def _frame_id(self, anim: str, frame: int) -> str:
        ids = assets_data.ANIMS[anim]
        return ids[frame % len(ids)]

    def anim_len(self, anim: str) -> int:
        return len(assets_data.ANIMS[anim])

    def frame_time(self, anim: str) -> float:
        fps = assets_data.ANIM_FPS.get(anim, 8.0)
        return 1.0 / fps if fps > 0 else 0.1

    def size(self, anim: str, frame: int, scale: int | None = None) -> tuple[int, int]:
        s = self.base_scale if scale is None else int(scale)
        w, h = assets_data.FRAMES[self._frame_id(anim, frame)][:2]
        return w * s, h * s

    def anchor(self, anim: str, frame: int, flip: bool = False,
               scale: int | None = None) -> tuple[int, int]:
        s = self.base_scale if scale is None else int(scale)
        w, _h, ax, ay = assets_data.FRAMES[self._frame_id(anim, frame)][:4]
        if flip:
            ax = w - 1 - ax
        return ax * s + s // 2, ay * s + s - 1

    # -- images ----------------------------------------------------------
    def _lut(self, palette: str) -> list[bytes]:
        lut = self._luts.get(palette)
        if lut is None:
            lut = self._luts[palette] = palette_lut(palette)
        return lut

    def get(self, anim: str, frame: int, palette: str, flip: bool = False,
            scale: int | None = None):
        s = self.base_scale if scale is None else int(scale)
        fid = self._frame_id(anim, frame)
        key = (fid, palette, bool(flip), s)
        img = self._cache.get(key)
        if img is None:
            w, h, rows = render_rgba_rows(fid, palette, bool(flip), s, self._lut(palette))
            png = encode_png(w, h, rows)
            img = self._tk.PhotoImage(master=self.root, data=base64.b64encode(png).decode("ascii"))
            self._cache[key] = img
        return img

    def preload(self, palettes: list[str], scales=(2,)) -> None:
        for pal in palettes:
            for anim, ids in assets_data.ANIMS.items():
                for i in range(len(ids)):
                    for s in scales:
                        for flip in (False, True):
                            self.get(anim, i, pal, flip, s)


__all__ = ["PALETTES", "SpriteBank", "CLASSES", "shade_color", "palette_lut",
           "encode_png", "render_rgba_rows"]
