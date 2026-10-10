"""Dessine l'icône de ReAble et produit packaging/ReAble.icns (outil de développement : nécessite Pillow et iconutil).

Motif : une flèche circulaire (« remettre en état ») autour d'une coche, blanc sur le bleu d'accent de l'interface."""
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZE = 1024
SS = 2                                  # sur-échantillonnage pour des bords nets
ACCENT = (10, 91, 211)                  # --pr-accent
ACCENT_DARK = (6, 62, 150)


def squircle_mask(n: int, radius_ratio: float = 0.2237) -> Image.Image:
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, n - 1, n - 1), radius=int(n * radius_ratio), fill=255)
    return m


def draw(n: int = SIZE * SS) -> Image.Image:
    # fond : dégradé vertical discret, dans la forme d'icône macOS (marge de 10 % autour)
    bg = Image.new("RGB", (n, n), ACCENT)
    px = bg.load()
    for y in range(n):
        t = y / n
        c = tuple(int(ACCENT[i] * (1 - t * 0.35) + ACCENT_DARK[i] * t * 0.35) for i in range(3))
        for x in range(n):
            px[x, y] = c
    margin = int(n * 0.098)
    shape = squircle_mask(n - 2 * margin)
    icon = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    icon.paste(bg.crop((margin, margin, n - margin, n - margin)), (margin, margin), shape)

    # motif
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = cy = n / 2
    r = n * 0.255
    w = int(n * 0.062)
    white = (255, 255, 255, 255)
    start, end = -52, 228                       # degrés (PIL : 0° = droite, sens horaire) ; ouverture en haut à droite
    ro = r + w / 2                              # Pillow trace l'arc vers l'intérieur de son cadre : on donne le rayon extérieur
    d.arc((cx - ro, cy - ro, cx + ro, cy + ro), start, end, fill=white, width=w)
    a0 = math.radians(start)                    # bout arrondi seulement côté « départ » ; l'autre bout porte la flèche
    x, y = cx + r * math.cos(a0), cy + r * math.sin(a0)
    d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=white)
    # pointe de flèche au bout « end » : triangle isocèle ancré sur l'arc, orienté dans le sens de rotation
    a = math.radians(end)
    tx, ty = -math.sin(a), math.cos(a)          # tangente (sens horaire)
    nx, ny = math.cos(a), math.sin(a)           # normale sortante
    base = (cx + r * nx - tx * n * 0.022, cy + r * ny - ty * n * 0.022)      # base reculée : recouvre le bout de l'arc
    half, length = n * 0.098, n * 0.150
    tip = (base[0] + tx * length, base[1] + ty * length)
    p1 = (base[0] + nx * half, base[1] + ny * half)
    p2 = (base[0] - nx * half, base[1] - ny * half)
    d.polygon([tip, p1, p2], fill=white)
    # coche au centre
    pts = [(cx - n * 0.085, cy + n * 0.005), (cx - n * 0.022, cy + n * 0.07), (cx + n * 0.095, cy - n * 0.07)]
    d.line(pts, fill=white, width=int(n * 0.056), joint="curve")
    for p in (pts[0], pts[-1]):
        rr = n * 0.028
        d.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=white)
    # ombre légère sous le motif
    shadow = layer.copy().filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(n * 0.006))
    shadow = Image.merge("RGBA", (Image.new("L", (n, n), 0),) * 3 + (shadow.split()[3].point(lambda v: int(v * 0.28)),))
    icon = Image.alpha_composite(icon, Image.alpha_composite(Image.new("RGBA", (n, n), (0, 0, 0, 0)),
                                 shadow.transform((n, n), Image.AFFINE, (1, 0, 0, 0, 1, -n * 0.008))))
    return Image.alpha_composite(icon, layer).resize((SIZE, SIZE), Image.LANCZOS)


def main() -> int:
    master = draw()
    master.save(HERE / "ReAble-icon-1024.png")
    iconset = HERE / "ReAble.iconset"
    shutil.rmtree(iconset, ignore_errors=True)
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        master.resize((base, base), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
        master.resize((base * 2, base * 2), Image.LANCZOS).save(iconset / f"icon_{base}x{base}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "ReAble.icns")], check=True)
    shutil.rmtree(iconset)
    print("OK :", HERE / "ReAble.icns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
