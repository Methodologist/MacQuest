"""
Render map pin textures (128x128 RGBA TGA) -> SpeedLevel/Media/
  Pin.tga      the numbered badge: soft drop shadow, thin dark outline, bevelled ring (white, so
               SetVertexColor gives it the route colour), glossy dark core.  Tinting multiplies, so the
               core stays near-black and the white number stays readable on any map.
  PinGlow.tga  soft radial glow (white), tinted behind the current pin.
  PinHalo.tga  thin soft ring, scaled up and faded out behind the current pin ("ping").
"""
import math
import struct
from pathlib import Path

S, SS = 128, 3
OUT = Path(__file__).resolve().parent.parent / "SpeedLevel" / "Media"
OUT.mkdir(parents=True, exist_ok=True)


def write_tga(path, pixels):
    hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, S, S, 32, 8)
    path.write_bytes(hdr + bytes(pixels))


def render(fn):
    pix = bytearray()
    for y in range(S - 1, -1, -1):          # TGA origin bottom-left
        for x in range(S):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(SS):
                for sx in range(SS):
                    px = x + (sx + 0.5) / SS - S / 2
                    py = y + (sy + 0.5) / SS - S / 2
                    r, g, b, a = fn(px, py)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            n = SS * SS
            a = acc[3] / n
            if a > 0:
                r, g, b = acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3]
            else:
                r = g = b = 0
            pix += bytes((int(min(1, b) * 255), int(min(1, g) * 255), int(min(1, r) * 255), int(min(1, a) * 255)))
    return pix


def smooth(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


R_EDGE = 50.0      # outer edge of the dark outline
R_OUT = 47.5       # outer edge of the coloured ring
R_IN = 37.0        # inner edge of the ring = edge of the core


def pin(px, py):
    py = -py          # the loop runs over file rows bottom-up: make +py point up on screen
    d = math.hypot(px, py)
    if d <= R_IN:
        # core: dark, lighter towards the top, darker just inside the ring (inner shadow)
        shade = 0.13 + 0.07 * (py / R_IN)
        shade *= 0.65 + 0.35 * (1 - smooth(R_IN - 7, R_IN, d))
        # gloss: a soft ellipse over the upper half
        gx, gy = px / (R_IN * 0.78), (py - R_IN * 0.42) / (R_IN * 0.46)
        g = 1 - (gx * gx + gy * gy)
        if g > 0:
            shade += 0.16 * smooth(0, 0.6, g)
        return shade, shade, shade, 0.96
    if d <= R_OUT:
        # ring: bevel - lighter on the upper-left, a bright lip along the middle of the ring
        t = (d - R_IN) / (R_OUT - R_IN)
        ang = (px * -0.6 + py * 0.8) / max(d, 1)          # light from the upper left
        light = 0.80 + 0.14 * ang
        light += 0.10 * (1 - abs(t - 0.45) * 2.2)
        light = max(0.55, min(1.0, light))
        return light, light, light, 1.0
    if d <= R_EDGE:
        # thin dark outline: contrast on bright maps
        return 0.04, 0.04, 0.05, 0.9
    # soft drop shadow below
    ds = math.hypot(px - 1.5, py + 4.5)       # shadow sits below the badge
    if ds <= R_EDGE + 9:
        return 0, 0, 0, 0.5 * (1 - smooth(R_EDGE - 2, R_EDGE + 9, ds))
    return 0, 0, 0, 0


def glow(px, py):
    d = math.hypot(px, py) / (S / 2)
    if d >= 1:
        return 1, 1, 1, 0
    return 1, 1, 1, (1 - d) ** 2.2


def halo(px, py):
    d = math.hypot(px, py)
    r, w = S / 2 - 8, 4.5
    a = max(0.0, 1 - abs(d - r) / w)
    return 1, 1, 1, a * a * (3 - 2 * a)


write_tga(OUT / "Pin.tga", render(pin))
write_tga(OUT / "PinGlow.tga", render(glow))
write_tga(OUT / "PinHalo.tga", render(halo))
print("wrote", OUT / "Pin.tga", OUT / "PinGlow.tga", OUT / "PinHalo.tga")
