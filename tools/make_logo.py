"""
Render the Mac Quest logo (128x128 RGBA TGA) -> SpeedLevel/Media/Logo.tga
A round badge: deep navy face with a soft top gloss, a bevelled gold ring, and a bold "M" whose two
peaks rise like route chevrons.  Optional: python tools/make_logo.py preview.png (writes a PNG too).
"""
import math
import struct
import sys
import zlib
from pathlib import Path

S, SS = 128, 3
C = S / 2
OUT = Path(__file__).resolve().parent.parent / "SpeedLevel" / "Media"

R_RING_OUT, R_RING_IN = 60.0, 51.0
M_PTS = [(-27, -25), (-27, 21), (0, -5), (27, 21), (27, -25)]     # y up
M_W = 7.0                                                          # half stroke width


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def m_dist(px, py):
    return min(seg_dist(px, py, M_PTS[i], M_PTS[i + 1]) for i in range(len(M_PTS) - 1))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


GOLD_HI, GOLD_LO = (1.00, 0.86, 0.42), (0.70, 0.46, 0.12)
NAVY_HI, NAVY_LO = (0.17, 0.22, 0.42), (0.05, 0.06, 0.14)


def logo(px, py):
    d = math.hypot(px, py)
    # the "M": warm white at the top fading to gold, with a thin dark outline for contrast
    md = m_dist(px, py)
    if d < R_RING_IN and md <= M_W + 1.6:
        if md > M_W:
            return (0.03, 0.03, 0.06), 0.85
        t = (py + 25) / 46
        return mix((0.93, 0.66, 0.20), (1.00, 0.97, 0.86), max(0, min(1, t))), 1.0
    if d <= R_RING_IN:
        # face: radial + vertical gradient, gloss on the upper half
        t = max(0.0, min(1.0, 0.5 + py / (2 * R_RING_IN)))
        col = mix(NAVY_LO, NAVY_HI, t * (1 - 0.35 * d / R_RING_IN))
        g = math.hypot(px, py - 30)
        if py > 4 and g < 44:
            k = 0.10 * (1 - g / 44)
            col = mix(col, (1, 1, 1), k)
        return col, 1.0
    if d <= R_RING_OUT:
        # bevelled gold ring: lighter towards the top-left, darker bottom-right; dark seams
        r = (d - R_RING_IN) / (R_RING_OUT - R_RING_IN)
        light = 0.5 + 0.5 * ((-px + py) / (math.sqrt(2) * d) if d else 0)
        col = mix(GOLD_LO, GOLD_HI, light)
        if r < 0.12 or r > 0.88:
            col = mix(col, (0.25, 0.15, 0.04), 0.6)
        return col, 1.0
    # soft drop shadow below
    ds = math.hypot(px - 1.5, py + 2.5)
    if ds <= R_RING_OUT + 3.5:
        return (0, 0, 0), 0.45 * (1 - (ds - R_RING_OUT) / 3.5) if ds > R_RING_OUT else 0.45
    return (0, 0, 0), 0.0


def render():
    rows = []
    for y in range(S):                          # top row first
        row = []
        for x in range(S):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(SS):
                for sx in range(SS):
                    px = x + (sx + 0.5) / SS - C
                    py = C - (y + (sy + 0.5) / SS)
                    (r, g, b), a = logo(px, py)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            a = acc[3] / (SS * SS)
            r, g, b = (acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]) if acc[3] > 0 else (0, 0, 0)
            row.append((int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5), int(min(1, a) * 255 + 0.5)))
        rows.append(row)
    return rows


def write_tga(path, rows):
    hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, S, S, 32, 8)
    body = bytearray()
    for row in reversed(rows):                  # TGA origin bottom-left
        for r, g, b, a in row:
            body += bytes((b, g, r, a))
    path.write_bytes(hdr + bytes(body))


def write_png(path, rows, bg=(40, 40, 46)):
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for r, g, b, a in row:                  # composite on a dark grey like the guide window
            k = a / 255
            raw += bytes(int(c * k + bg[i] * (1 - k)) for i, c in enumerate((r, g, b)))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", S, S, 8, 2, 0, 0, 0)) \
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    img = render()
    write_tga(OUT / "Logo.tga", img)
    print("wrote", OUT / "Logo.tga")
    if len(sys.argv) > 1:
        write_png(sys.argv[1], img)
        print("preview", sys.argv[1])
