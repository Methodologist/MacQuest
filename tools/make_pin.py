"""
Render map pin textures (64x64 RGBA TGA) -> SpeedLevel/Media/
  Pin.tga      dark core + white ring + soft drop shadow.  Tinted with SetVertexColor the ring takes
               the step colour while the core stays near-black (multiply), so numbers stay readable.
  PinGlow.tga  soft radial glow (white), tinted and pulsed behind the current pin.
"""
import math
import struct
from pathlib import Path

S, SS = 64, 4
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
            pix += bytes((int(b * 255), int(g * 255), int(r * 255), int(min(1, a) * 255)))
    return pix


def pin(px, py):
    # drop shadow offset down-right, then ring, then core
    d = math.hypot(px, py)
    ds = math.hypot(px - 1.5, py + 2.0)    # y grows upwards here (bottom-left origin loop)
    R_OUT, R_RING = 26.0, 20.0
    if d <= R_RING:
        # core: very dark, slight vertical gradient for depth
        shade = 0.10 + 0.06 * (py / R_RING)
        return shade, shade, shade, 0.95
    if d <= R_OUT:
        # ring with a subtle bevel (lighter towards the top)
        t = (d - R_RING) / (R_OUT - R_RING)
        light = 0.82 + 0.18 * (py / R_OUT) * (1 - abs(t - 0.5) * 2)
        return light, light, light, 1.0
    if ds <= R_OUT + 5:
        fall = 1 - (ds - R_OUT) / 5 if ds > R_OUT else 1
        return 0, 0, 0, 0.45 * max(0, fall)
    return 0, 0, 0, 0


def glow(px, py):
    d = math.hypot(px, py) / (S / 2)
    if d >= 1:
        return 1, 1, 1, 0
    a = (1 - d) ** 2
    return 1, 1, 1, a


write_tga(OUT / "Pin.tga", render(pin))
write_tga(OUT / "PinGlow.tga", render(glow))
print("wrote", OUT / "Pin.tga", OUT / "PinGlow.tga")
