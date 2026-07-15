"""
Magic Pictures - Bilder verkleinern fuer Windows 11
====================================================
Eine kleine Desktop-App zum Verkleinern von Bildern auf HD/1080p mit
optionaler Einblendung des Aufnahmedatums.

Funktionen:
  * Bilder importieren / auswaehlen (Mehrfachauswahl oder Drag & Drop)
  * Aufnahmedatum (aus EXIF) optional ins Bild einblenden
      - Auswahl der Ecke (oben/unten, links/rechts)
      - Auswahl der Textfarbe
  * Ausgabeordner frei waehlbar (Vorschlag: Unterordner "HD" neben den Bildern)
  * Ausgabe in HD-Qualitaet (max. 1920 x 1080, Seitenverhaeltnis bleibt erhalten)
  * Qualitaet standardmaessig 80 (entspricht max. ~20 % Qualitaetsverlust)
  * Qualitaet bei Bedarf manuell einstellbar (1 - 100)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Drag & Drop ist optional - ohne tkinterdnd2 laeuft die App normal weiter
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_VERFUEGBAR = True
except Exception:
    DND_VERFUEGBAR = False

__version__ = "1.1.0"

# ----------------------------------------------------------------------------
# Konstanten
# ----------------------------------------------------------------------------
ZIEL_BREITE = 1920          # HD / 1080p Breite
ZIEL_HOEHE = 1080           # HD / 1080p Hoehe
STANDARD_QUALITAET = 80     # entspricht max. ~20 % Qualitaetsverlust
UNTERSTUETZTE_FORMATE = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")

ECKEN = {
    "Oben links": "oben_links",
    "Oben rechts": "oben_rechts",
    "Unten links": "unten_links",
    "Unten rechts": "unten_rechts",
}


def ressourcen_pfad(dateiname):
    """Pfad zu einer mitgelieferten Datei (z. B. icon.ico) - funktioniert im
    Quellcode-Betrieb und in der portablen PyInstaller-EXE (sys._MEIPASS)."""
    basis = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(basis, dateiname)


# ----------------------------------------------------------------------------
# Bildverarbeitung
# ----------------------------------------------------------------------------
def aufnahmedatum_lesen(bild):
    """Liest das Aufnahmedatum aus den EXIF-Daten. Gibt einen formatierten
    String (TT.MM.JJJJ) zurueck oder None, wenn kein Datum vorhanden ist."""
    try:
        exif = bild.getexif()
        if not exif:
            return None
        # 36867 = DateTimeOriginal - liegt im Exif-Sub-IFD (0x8769),
        # nicht im Haupt-IFD. 306 = DateTime (Aenderungsdatum, Fallback).
        wert = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if not wert:
            return None
        # Format aus EXIF: "JJJJ:MM:TT HH:MM:SS"
        datum_teil = str(wert).split(" ")[0]
        jahr, monat, tag = datum_teil.split(":")
        return f"{tag}.{monat}.{jahr}"
    except Exception:
        return None


def datum_einblenden(bild, text, ecke, farbe):
    """Zeichnet den Datumstext mit Schatten in die gewuenschte Ecke."""
    zeichner = ImageDraw.Draw(bild)
    breite, hoehe = bild.size

    # Schriftgroesse proportional zur Bildbreite
    schrift_groesse = max(int(breite / 38), 16)
    schrift = None
    for schrift_datei in ("arial.ttf", "segoeui.ttf"):
        try:
            schrift = ImageFont.truetype(schrift_datei, schrift_groesse)
            break
        except Exception:
            pass
    if schrift is None:
        try:
            schrift = ImageFont.load_default(size=schrift_groesse)  # Pillow >= 10.1
        except TypeError:
            schrift = ImageFont.load_default()

    # Textgroesse ermitteln
    box = zeichner.textbbox((0, 0), text, font=schrift)
    text_breite = box[2] - box[0]
    text_hoehe = box[3] - box[1]

    rand = max(int(breite / 60), 12)

    if ecke == "oben_links":
        x, y = rand, rand
    elif ecke == "oben_rechts":
        x, y = breite - text_breite - rand, rand
    elif ecke == "unten_links":
        x, y = rand, hoehe - text_hoehe - rand * 2
    else:  # unten_rechts
        x, y = breite - text_breite - rand, hoehe - text_hoehe - rand * 2

    # Schatten fuer bessere Lesbarkeit
    versatz = max(int(schrift_groesse / 18), 1)
    zeichner.text((x + versatz, y + versatz), text, font=schrift, fill="black")
    zeichner.text((x, y), text, font=schrift, fill=farbe)
    return bild


def ausgabe_pfad_bestimmen(pfad, ausgabe_ordner, vergebene_namen):
    """Baut den Ausgabedateinamen und haengt bei Namenskollisionen innerhalb
    eines Durchlaufs (_2, _3, ...) an, damit nichts ueberschrieben wird."""
    name = os.path.splitext(os.path.basename(pfad))[0]
    kandidat = f"{name}_HD.jpg"
    zaehler = 2
    while kandidat.lower() in vergebene_namen:
        kandidat = f"{name}_HD_{zaehler}.jpg"
        zaehler += 1
    vergebene_namen.add(kandidat.lower())
    return os.path.join(ausgabe_ordner, kandidat)


def bild_verarbeiten(pfad, ausgabe_ordner, datum_aktiv, ecke, farbe, qualitaet,
                     vergebene_namen):
    """Verarbeitet ein einzelnes Bild: Drehung korrigieren, verkleinern,
    Datum einblenden, als JPEG speichern. Gibt den Ausgabepfad zurueck."""
    with Image.open(pfad) as bild:
        # Datum vor evtl. Konvertierung auslesen
        datum_text = aufnahmedatum_lesen(bild) if datum_aktiv else None

        # EXIF-Orientierung beruecksichtigen (Hochformat korrekt drehen)
        bild = ImageOps.exif_transpose(bild)

        # In RGB konvertieren (JPEG kann kein Alpha/Palette).
        # Transparente Bereiche landen auf weissem Hintergrund statt schwarz.
        if bild.mode != "RGB":
            if "A" in bild.getbands() or "transparency" in bild.info:
                bild = bild.convert("RGBA")
                hintergrund = Image.new("RGB", bild.size, "white")
                hintergrund.paste(bild, mask=bild.getchannel("A"))
                bild = hintergrund
            else:
                bild = bild.convert("RGB")

        # Verkleinern auf max. 1920 x 1080, Seitenverhaeltnis bleibt erhalten
        bild.thumbnail((ZIEL_BREITE, ZIEL_HOEHE), Image.LANCZOS)

        # Datum einblenden
        if datum_aktiv and datum_text:
            bild = datum_einblenden(bild, datum_text, ecke, farbe)

        ausgabe_pfad = ausgabe_pfad_bestimmen(pfad, ausgabe_ordner, vergebene_namen)
        bild.save(ausgabe_pfad, "JPEG", quality=qualitaet, optimize=True)
    return ausgabe_pfad


# ----------------------------------------------------------------------------
# Benutzeroberflaeche
# ----------------------------------------------------------------------------
class MagicPicturesApp:
    def __init__(self, wurzel):
        self.wurzel = wurzel
        wurzel.title(f"Magic Pictures {__version__} - Bilder verkleinern")
        wurzel.geometry("680x720")
        wurzel.minsize(620, 680)
        try:
            wurzel.iconbitmap(ressourcen_pfad("icon.ico"))
        except Exception:
            pass  # ohne Icon weiterlaufen (z. B. Datei fehlt)

        self.bilder = []                       # Liste der Eingabepfade
        self.farbe = "#FFFFFF"                  # Standard-Textfarbe (weiss)
        self.ausgabe_ordner = tk.StringVar()
        self.datum_aktiv = tk.BooleanVar(value=False)
        self.ecke_auswahl = tk.StringVar(value="Unten rechts")
        self.manuelle_qualitaet = tk.BooleanVar(value=False)
        self.qualitaet = tk.IntVar(value=STANDARD_QUALITAET)

        self._oberflaeche_aufbauen()

    # --- GUI-Aufbau -------------------------------------------------------
    def _oberflaeche_aufbauen(self):
        haupt = ttk.Frame(self.wurzel, padding=12)
        haupt.pack(fill="both", expand=True)

        # 1) Bilder auswaehlen
        rahmen_bilder = ttk.LabelFrame(haupt, text="1. Bilder auswaehlen", padding=10)
        rahmen_bilder.pack(fill="both", expand=True)

        liste_rahmen = ttk.Frame(rahmen_bilder)
        liste_rahmen.pack(fill="both", expand=True)

        scroll = ttk.Scrollbar(liste_rahmen)
        scroll.pack(side="right", fill="y")
        self.liste = tk.Listbox(liste_rahmen, height=7, yscrollcommand=scroll.set)
        self.liste.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.liste.yview)

        if DND_VERFUEGBAR:
            self.liste.drop_target_register(DND_FILES)
            self.liste.dnd_bind("<<Drop>>", self._ablage_verarbeiten)
            ttk.Label(rahmen_bilder,
                      text="Tipp: Bilder oder Ordner einfach in die Liste ziehen."
                      ).pack(anchor="w", pady=(4, 0))

        knoepfe = ttk.Frame(rahmen_bilder)
        knoepfe.pack(fill="x", pady=(8, 0))
        ttk.Button(knoepfe, text="Bilder hinzufuegen...",
                   command=self.bilder_hinzufuegen).pack(side="left")
        ttk.Button(knoepfe, text="Auswahl entfernen",
                   command=self.auswahl_entfernen).pack(side="left", padx=6)
        ttk.Button(knoepfe, text="Liste leeren",
                   command=self.liste_leeren).pack(side="left")

        # 2) Aufnahmedatum
        rahmen_datum = ttk.LabelFrame(haupt, text="2. Aufnahmedatum einblenden", padding=10)
        rahmen_datum.pack(fill="x", pady=(10, 0))

        ttk.Checkbutton(rahmen_datum, text="Aufnahmedatum ins Bild einblenden",
                        variable=self.datum_aktiv,
                        command=self._datum_status).pack(anchor="w")

        self.datum_optionen = ttk.Frame(rahmen_datum)
        self.datum_optionen.pack(fill="x", pady=(8, 0))

        ttk.Label(self.datum_optionen, text="Ecke:").grid(row=0, column=0, sticky="w")
        self.ecke_box = ttk.Combobox(self.datum_optionen, state="readonly",
                                     width=15, values=list(ECKEN.keys()),
                                     textvariable=self.ecke_auswahl)
        self.ecke_box.grid(row=0, column=1, sticky="w", padx=(6, 20))

        ttk.Label(self.datum_optionen, text="Farbe:").grid(row=0, column=2, sticky="w")
        self.farb_knopf = tk.Button(self.datum_optionen, text="   ", width=4,
                                    bg=self.farbe, command=self.farbe_waehlen)
        self.farb_knopf.grid(row=0, column=3, sticky="w", padx=(6, 0))
        self._datum_status()

        # 3) Ausgabeordner
        rahmen_ausgabe = ttk.LabelFrame(haupt, text="3. Ausgabeordner", padding=10)
        rahmen_ausgabe.pack(fill="x", pady=(10, 0))
        ttk.Entry(rahmen_ausgabe, textvariable=self.ausgabe_ordner).pack(
            side="left", fill="x", expand=True)
        ttk.Button(rahmen_ausgabe, text="Durchsuchen...",
                   command=self.ausgabe_waehlen).pack(side="left", padx=(6, 0))

        # 4) Qualitaet
        rahmen_qual = ttk.LabelFrame(haupt, text="4. Qualitaet & Groesse", padding=10)
        rahmen_qual.pack(fill="x", pady=(10, 0))
        ttk.Label(rahmen_qual,
                  text="Ausgabe: HD / 1080p (max. 1920 x 1080, Seitenverhaeltnis bleibt erhalten)"
                  ).pack(anchor="w")

        ttk.Checkbutton(rahmen_qual,
                        text="Qualitaet manuell einstellen (Standard: 80 = max. ~20 % Verlust)",
                        variable=self.manuelle_qualitaet,
                        command=self._qualitaet_status).pack(anchor="w", pady=(6, 0))

        self.qual_zeile = ttk.Frame(rahmen_qual)
        self.qual_zeile.pack(fill="x", pady=(6, 0))
        self.qual_slider = ttk.Scale(self.qual_zeile, from_=1, to=100,
                                     orient="horizontal", variable=self.qualitaet,
                                     command=self._qual_anzeige_aktualisieren)
        self.qual_slider.pack(side="left", fill="x", expand=True)
        self.qual_label = ttk.Label(self.qual_zeile, text=str(STANDARD_QUALITAET), width=4)
        self.qual_label.pack(side="left", padx=(8, 0))
        self._qualitaet_status()

        # 5) Verarbeiten
        rahmen_start = ttk.Frame(haupt)
        rahmen_start.pack(fill="x", pady=(14, 0))
        self.start_knopf = ttk.Button(rahmen_start, text="Bilder verkleinern",
                                      command=self.verarbeitung_starten)
        self.start_knopf.pack(side="left", fill="x", expand=True)
        self.ordner_knopf = ttk.Button(rahmen_start, text="Ausgabeordner oeffnen",
                                       command=self.ausgabe_oeffnen,
                                       state="disabled")
        self.ordner_knopf.pack(side="left", padx=(6, 0))

        self.fortschritt = ttk.Progressbar(haupt, mode="determinate")
        self.fortschritt.pack(fill="x", pady=(10, 0))
        self.status = ttk.Label(haupt, text="Bereit.")
        self.status.pack(anchor="w", pady=(4, 0))

    # --- Status-Helfer ----------------------------------------------------
    def _datum_status(self):
        zustand = "normal" if self.datum_aktiv.get() else "disabled"
        self.ecke_box.config(state="readonly" if self.datum_aktiv.get() else "disabled")
        self.farb_knopf.config(state=zustand)

    def _qualitaet_status(self):
        if self.manuelle_qualitaet.get():
            self.qual_slider.config(state="normal")
        else:
            self.qualitaet.set(STANDARD_QUALITAET)
            self.qual_slider.config(state="disabled")
            self.qual_label.config(text=str(STANDARD_QUALITAET))

    def _qual_anzeige_aktualisieren(self, _=None):
        self.qual_label.config(text=str(int(float(self.qualitaet.get()))))

    # --- Aktionen ---------------------------------------------------------
    def bilder_hinzufuegen(self):
        dateien = filedialog.askopenfilenames(
            title="Bilder auswaehlen",
            filetypes=[("Bilder", " ".join(f"*{e}" for e in UNTERSTUETZTE_FORMATE)),
                       ("Alle Dateien", "*.*")])
        self._bilder_aufnehmen(dateien)

    def _bilder_aufnehmen(self, dateien):
        """Nimmt Dateipfade in die Liste auf (ohne Duplikate) und schlaegt,
        falls noch keiner gesetzt ist, einen Ausgabeordner vor."""
        for d in dateien:
            if d not in self.bilder:
                self.bilder.append(d)
                self.liste.insert("end", os.path.basename(d))
        if self.bilder and not self.ausgabe_ordner.get().strip():
            self.ausgabe_ordner.set(
                os.path.join(os.path.dirname(self.bilder[0]), "HD"))
        self.status.config(text=f"{len(self.bilder)} Bild(er) ausgewaehlt.")

    def _ablage_verarbeiten(self, ereignis):
        """Drag & Drop: nimmt fallengelassene Bilddateien auf; bei Ordnern
        werden die direkt enthaltenen Bilder uebernommen."""
        dateien = []
        for pfad in self.wurzel.tk.splitlist(ereignis.data):
            if os.path.isdir(pfad):
                for eintrag in sorted(os.listdir(pfad)):
                    voll = os.path.join(pfad, eintrag)
                    if (os.path.isfile(voll)
                            and eintrag.lower().endswith(UNTERSTUETZTE_FORMATE)):
                        dateien.append(voll)
            elif pfad.lower().endswith(UNTERSTUETZTE_FORMATE):
                dateien.append(pfad)
        self._bilder_aufnehmen(dateien)

    def auswahl_entfernen(self):
        for index in reversed(self.liste.curselection()):
            self.liste.delete(index)
            del self.bilder[index]
        self.status.config(text=f"{len(self.bilder)} Bild(er) ausgewaehlt.")

    def liste_leeren(self):
        self.liste.delete(0, "end")
        self.bilder.clear()
        self.status.config(text="Bereit.")

    def farbe_waehlen(self):
        ergebnis = colorchooser.askcolor(color=self.farbe, title="Textfarbe waehlen")
        if ergebnis and ergebnis[1]:
            self.farbe = ergebnis[1]
            self.farb_knopf.config(bg=self.farbe)

    def ausgabe_waehlen(self):
        ordner = filedialog.askdirectory(title="Ausgabeordner waehlen")
        if ordner:
            self.ausgabe_ordner.set(ordner)

    def ausgabe_oeffnen(self):
        ordner = self.ausgabe_ordner.get().strip()
        if ordner and os.path.isdir(ordner):
            os.startfile(ordner)

    def verarbeitung_starten(self):
        if not self.bilder:
            messagebox.showwarning("Keine Bilder", "Bitte zuerst Bilder auswaehlen.")
            return
        ordner = self.ausgabe_ordner.get().strip()
        if not ordner:
            messagebox.showwarning("Kein Ausgabeordner", "Bitte einen Ausgabeordner waehlen.")
            return
        if not os.path.isdir(ordner):
            try:
                os.makedirs(ordner, exist_ok=True)
            except Exception as fehler:
                messagebox.showerror("Fehler", f"Ausgabeordner konnte nicht erstellt werden:\n{fehler}")
                return

        # In separatem Thread, damit die Oberflaeche nicht einfriert
        self.start_knopf.config(state="disabled")
        threading.Thread(target=self._verarbeiten_thread, daemon=True).start()

    def _verarbeiten_thread(self):
        ordner = self.ausgabe_ordner.get().strip()
        datum_aktiv = self.datum_aktiv.get()
        ecke = ECKEN[self.ecke_auswahl.get()]
        farbe = self.farbe
        qualitaet = int(float(self.qualitaet.get()))
        gesamt = len(self.bilder)

        self.wurzel.after(0, lambda: self.fortschritt.config(maximum=gesamt, value=0))

        fehler_liste = []
        vergebene_namen = set()
        for i, pfad in enumerate(list(self.bilder), start=1):
            name = os.path.basename(pfad)
            self.wurzel.after(0, lambda n=name, i=i: self.status.config(
                text=f"Verarbeite {i}/{gesamt}: {n}"))
            try:
                bild_verarbeiten(pfad, ordner, datum_aktiv, ecke, farbe,
                                 qualitaet, vergebene_namen)
            except Exception as fehler:
                fehler_liste.append(f"{name}: {fehler}")
            self.wurzel.after(0, lambda i=i: self.fortschritt.config(value=i))

        def fertig():
            self.start_knopf.config(state="normal")
            self.ordner_knopf.config(state="normal")
            if fehler_liste:
                self.status.config(text=f"Fertig mit {len(fehler_liste)} Fehler(n).")
                messagebox.showerror("Fehler bei einigen Bildern",
                                     "\n".join(fehler_liste))
            else:
                self.status.config(text=f"Fertig! {gesamt} Bild(er) gespeichert in: {ordner}")
                messagebox.showinfo("Fertig",
                                    f"{gesamt} Bild(er) erfolgreich verkleinert und gespeichert.")
        self.wurzel.after(0, fertig)


def main():
    wurzel = TkinterDnD.Tk() if DND_VERFUEGBAR else tk.Tk()
    MagicPicturesApp(wurzel)
    wurzel.mainloop()


if __name__ == "__main__":
    main()
