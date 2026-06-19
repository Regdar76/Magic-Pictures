"""Erzeugt das App-Icon (icon.ico) fuer Magic Pictures.
Motiv: gerundetes Kachelsymbol mit Foto (Sonne + Berge) und Magie-Funken.
"""
from PIL import Image, ImageDraw

GROESSE = 256
bild = Image.new("RGBA", (GROESSE, GROESSE), (0, 0, 0, 0))
zeichner = ImageDraw.Draw(bild)

# --- Hintergrund: vertikaler Farbverlauf (lila -> blau) -------------------
oben = (124, 58, 237)      # violett
unten = (37, 99, 235)      # blau
for y in range(GROESSE):
    t = y / GROESSE
    r = int(oben[0] + (unten[0] - oben[0]) * t)
    g = int(oben[1] + (unten[1] - oben[1]) * t)
    b = int(oben[2] + (unten[2] - oben[2]) * t)
    zeichner.line([(0, y), (GROESSE, y)], fill=(r, g, b, 255))

# Verlauf in abgerundete Kachel maskieren
maske = Image.new("L", (GROESSE, GROESSE), 0)
ImageDraw.Draw(maske).rounded_rectangle([8, 8, GROESSE - 8, GROESSE - 8],
                                        radius=48, fill=255)
hintergrund = Image.new("RGBA", (GROESSE, GROESSE), (0, 0, 0, 0))
hintergrund.paste(bild, (0, 0), maske)
bild = hintergrund
zeichner = ImageDraw.Draw(bild)

# --- Weisser Foto-Rahmen --------------------------------------------------
rx0, ry0, rx1, ry1 = 52, 66, 204, 190
zeichner.rounded_rectangle([rx0, ry0, rx1, ry1], radius=14, fill=(255, 255, 255, 255))

# Innenbereich (Himmel)
ix0, iy0, ix1, iy1 = rx0 + 10, ry0 + 10, rx1 - 10, ry1 - 10
zeichner.rounded_rectangle([ix0, iy0, ix1, iy1], radius=8, fill=(186, 230, 253, 255))

# Sonne
zeichner.ellipse([ix0 + 14, iy0 + 12, ix0 + 44, iy0 + 42], fill=(250, 204, 21, 255))

# Berge (zwei Dreiecke)
zeichner.polygon([(ix0, iy1), (ix0 + 52, iy1 - 56), (ix0 + 96, iy1)],
                 fill=(34, 197, 94, 255))
zeichner.polygon([(ix0 + 60, iy1), (ix1 - 30, iy1 - 74), (ix1, iy1)],
                 fill=(22, 163, 74, 255))

# --- Magie-Funken (vier-zackige Sterne) -----------------------------------
def funke(cx, cy, groesse, farbe):
    zeichner.polygon([
        (cx, cy - groesse), (cx + groesse * 0.28, cy - groesse * 0.28),
        (cx + groesse, cy), (cx + groesse * 0.28, cy + groesse * 0.28),
        (cx, cy + groesse), (cx - groesse * 0.28, cy + groesse * 0.28),
        (cx - groesse, cy), (cx - groesse * 0.28, cy - groesse * 0.28),
    ], fill=farbe)

funke(196, 70, 26, (253, 224, 71, 255))
funke(70, 56, 16, (255, 255, 255, 255))
funke(214, 132, 12, (255, 255, 255, 235))

# --- Als Multi-Size-ICO speichern -----------------------------------------
bild.save("icon.ico", format="ICO",
          sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                 (128, 128), (256, 256)])
bild.save("icon.png")
print("icon.ico und icon.png erstellt.")
