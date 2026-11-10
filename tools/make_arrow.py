"""Render the guide arrow texture (64x64 RGBA TGA, pointing up) -> SpeedLevel/Media/Arrow.tga"""
import math
import struct
from pathlib import Path

S = 64
SS = 4  # supersampling


def inside(px, py):
    # chevron arrow: tip at top centre, two wings, notch at bottom
    tip = (32, 4)
    left = (8, 56)
    notch = (32, 42)
    right = (56, 56)
    poly = [tip, right, notch, left]
    # point in polygon
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
            c = not c
        j = i
    return c


def edge_dist(px, py):
    tip, right, notch, left = (32, 4), (56, 56), (32, 42), (8, 56)
    segs = [(tip, right), (right, notch), (notch, left), (left, tip)]
    best = 1e9
    for (ax, ay), (bx, by) in segs:
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


pix = bytearray()
for y in range(S - 1, -1, -1):  # TGA default origin bottom-left
    for x in range(S):
        cover = 0
        border = 0
        for sy in range(SS):
            for sx in range(SS):
                px = x + (sx + 0.5) / SS
                py = y + (sy + 0.5) / SS
                if inside(px, py):
                    cover += 1
                    if edge_dist(px, py) < 2.2:
                        border += 1
        a = cover / (SS * SS)
        b = border / max(cover, 1)
        # body: warm gold, border: dark
        r = int(255 * (1 - b) + 30 * b)
        g = int(210 * (1 - b) + 20 * b)
        bl = int(40 * (1 - b) + 10 * b)
        pix += bytes((bl, g, r, int(255 * a)))  # BGRA

hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, S, S, 32, 8)
out = Path(__file__).resolve().parent.parent / "SpeedLevel" / "Media" / "Arrow.tga"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(hdr + bytes(pix))
print("wrote", out, len(pix) + len(hdr), "bytes")
