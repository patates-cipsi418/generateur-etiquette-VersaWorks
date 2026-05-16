#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère un PDF d'étiquettes (format carte de crédit, coins arrondis, fond rouge)
avec une ligne de découpe en spot color "CutContour" compatible
Roland VersaWorks.

Utilisation :
    python generate_etiquettes.py textes.txt etiquettes.pdf

Le fichier .txt doit contenir une ligne par étiquette.
Le PDF résultant contient une étiquette par page, ouvrable sans erreur
dans Adobe Reader, et la couleur de découpe "CutContour" sera reconnue
automatiquement par VersaWorks.
"""

import sys
import os

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import CMYKColor, CMYKColorSep
from reportlab.graphics import renderPDF

# svglib est optionnel : nécessaire uniquement si on veut ajouter un logo SVG.
try:
    from svglib.svglib import svg2rlg
    SVGLIB_AVAILABLE = True
except ImportError:
    svg2rlg = None
    SVGLIB_AVAILABLE = False


# --- Dimensions standard d'une carte de crédit (ISO/IEC 7810 ID-1) ---
CARD_WIDTH  = 85.60 * mm   # 85,60 mm
CARD_HEIGHT = 53.98 * mm   # 53,98 mm
CORNER_RADIUS = 3.18 * mm  # rayon standard ISO
CUT_MARGIN    = 0.5 * mm     # marge autour du tracé de coupe (bleed VersaWorks)

# --- Logo ---
LOGO_PATH = "logo.svg"       # chemin du fichier SVG à incorporer
LOGO_HEIGHT = 8 * mm         # hauteur cible du logo (le logo conserve son ratio)
LOGO_MARGIN_BOTTOM = 2.5 * mm  # distance entre le bas du logo et le bord bas

# --- Couleurs ---
# Fond blanc (CMYK 0,0,0,0)
BG_FILL = CMYKColor(0, 0, 0, 0)
# Texte noir
TEXT_COLOR = CMYKColor(0, 0, 0, 1)

# Spot color "CutContour" reconnue par Roland VersaWorks.
# Convention Roland : nom EXACT "CutContour" (sensible à la casse),
# couleur d'aperçu = magenta 100 %.
# CMYKColorSep crée une vraie couleur d'accompagnement
# (PDF Separation color space) — c'est ce que VersaWorks détecte
# pour générer le tracé de coupe.
CUT_CONTOUR = CMYKColorSep(
    0, 1, 0, 0,            # valeurs CMYK d'aperçu : magenta 100 %
    spotName='CutContour',
    density=1,
)


def lire_lignes(chemin_txt):
    """
    Lit le fichier texte et retourne la liste des lignes non vides.
    Convertit la séquence littérale '\\n' (antislash + n) en vrai saut de ligne
    à l'intérieur d'une étiquette. La séquence '\\\\n' reste un antislash
    littéral suivi de la lettre n.
    """
    with open(chemin_txt, 'r', encoding='utf-8') as f:
        lignes = [ligne.rstrip('\n').rstrip('\r') for ligne in f]

    def convert(s):
        # On remplace d'abord '\\\\' (deux antislashes) par un placeholder,
        # puis '\\n' -> vrai \n, puis on restaure les antislashes.
        PH = '\x00'
        s = s.replace('\\\\', PH)
        s = s.replace('\\n', '\n')
        s = s.replace(PH, '\\')
        return s

    return [convert(l) for l in lignes if l.strip()]


def charger_logo(chemin):
    """
    Charge le logo SVG une seule fois et le met à l'échelle pour atteindre
    LOGO_HEIGHT. Retourne (drawing) ou None si le fichier n'existe pas
    ou si svglib n'est pas installé.
    """
    if not chemin or not os.path.isfile(chemin):
        return None
    if not SVGLIB_AVAILABLE:
        print("Avertissement : la librairie 'svglib' n'est pas installée. "
              "Installez-la avec :  pip install svglib\n"
              "Le logo sera ignoré.")
        return None
    drawing = svg2rlg(chemin)
    if drawing is None or drawing.height <= 0:
        return None
    # Mise à l'échelle proportionnelle pour atteindre LOGO_HEIGHT
    scale = LOGO_HEIGHT / drawing.height
    drawing.scale(scale, scale)
    # Ajuster width/height pour le bon placement après scale
    drawing.width  = drawing.width * scale
    drawing.height = LOGO_HEIGHT
    return drawing


def wrap_text(texte, c, font_name, font_size, max_width):
    """[Conservé pour compatibilité — non utilisé par le pipeline markdown]"""
    return _wrap_segments(parse_markdown(texte), c, font_size, max_width)


# ============================================================
#  Parsing Markdown -> segments stylés
# ============================================================
# Un "segment" est un dict :
#   {'text': str, 'b': bool, 'i': bool, 's': bool, 'u': bool}
# (b = gras, i = italique, s = barré, u = souligné)
# Les sauts de ligne sont représentés par un segment dont 'text' == '\n'.

import re

# Ordre important : les patterns plus longs en premier pour éviter les conflits
# (ex: *** avant **, ** avant *).
_MD_TOKEN_RE = re.compile(
    r"""
      (\\[\\*_~`\[\]])      # 1: caractère échappé (\*, \_, \~, \\, etc.)
    | (\*\*\*|___)          # 2: triple emphase = gras+italique
    | (\*\*|__(?!_))        # 3: gras  (** ou __ mais pas ___)
    | (~~)                  # 4: barré
    | (\*|_)                # 5: italique (* ou _ simple)
    | (\[([^\]]+)\]\([^)]*\))  # 6: lien markdown -> on ne garde que le texte
    | (\n)                  # 7: saut de ligne explicite
    """,
    re.VERBOSE,
)


def parse_markdown(texte):
    """
    Convertit une chaîne markdown en liste de segments stylés.
    Supporte : **gras**, *italique*, _italique_, __souligné__,
               ***gras italique***, ~~barré~~, [texte](url),
               échappement avec \\ et saut de ligne \\n.
    """
    # Normaliser les fins de ligne ; on gère aussi le "saut de ligne dur"
    # markdown (deux espaces ou plus en fin de ligne).
    texte = texte.replace('\r\n', '\n').replace('\r', '\n')
    texte = re.sub(r' {2,}\n', '\n', texte)

    # État courant des modificateurs
    state = {'b': False, 'i': False, 's': False, 'u': False}
    segments = []
    buffer = []

    def flush():
        if buffer:
            segments.append({'text': ''.join(buffer), **state})
            buffer.clear()

    pos = 0
    while pos < len(texte):
        m = _MD_TOKEN_RE.search(texte, pos)
        if not m:
            buffer.append(texte[pos:])
            break

        # Texte littéral avant le token
        if m.start() > pos:
            buffer.append(texte[pos:m.start()])

        # Identifier quel groupe a matché
        esc, triple, strong, strike, em, link, _link_txt, nl = (
            m.group(1), m.group(2), m.group(3), m.group(4),
            m.group(5), m.group(6), m.group(7), m.group(8)
        )

        if esc:
            buffer.append(esc[1])              # garde le caractère échappé tel quel
        elif triple:
            flush()
            # bascule gras ET italique en même temps
            new_b = not state['b']
            new_i = not state['i']
            state['b'], state['i'] = new_b, new_i
        elif strong:
            flush()
            if strong == '__':
                # __ = souligné (notre convention)
                state['u'] = not state['u']
            else:
                state['b'] = not state['b']
            # remarque : __toto__ pris en charge par la branche "souligné"
        elif strike:
            flush()
            state['s'] = not state['s']
        elif em:
            flush()
            state['i'] = not state['i']
        elif link:
            # Garde uniquement le texte du lien, l'URL est ignorée
            buffer.append(_link_txt)
        elif nl:
            flush()
            segments.append({'text': '\n', **state})

        pos = m.end()

    flush()
    return segments


# ============================================================
#  Wrap / mesure / rendu de segments stylés
# ============================================================

def _font_for(seg):
    """Retourne le nom de police PDF correspondant aux flags du segment."""
    b, i = seg['b'], seg['i']
    if b and i: return 'Helvetica-BoldOblique'
    if b:       return 'Helvetica-Bold'
    if i:       return 'Helvetica-Oblique'
    return 'Helvetica'


def _seg_width(c, seg, font_size):
    return c.stringWidth(seg['text'], _font_for(seg), font_size)


def _wrap_segments(segments, c, font_size, max_width):
    """
    Découpe la liste de segments en lignes (liste de listes de segments)
    pour qu'aucune ligne ne dépasse max_width.

    Algorithme :
      - sépare en mots (en gardant l'info de style)
      - on traite chaque saut de ligne explicite comme un break
      - empile les mots tant qu'on tient dans max_width
      - mot trop long isolé : coupé caractère par caractère
    """
    # Construire la liste des "tokens" : soit '\n', soit (texte_mot, style)
    # Les espaces sont des séparateurs simples (on ne les conserve pas
    # entre mots ; on les rajoute au rendu pour ajuster).
    tokens = []
    for seg in segments:
        if seg['text'] == '\n':
            tokens.append(('NL', None))
            continue
        # split en gardant les espaces comme tokens explicites
        parts = re.split(r'(\s+)', seg['text'])
        for p in parts:
            if not p:
                continue
            if p.isspace():
                tokens.append(('SP', {'text': ' ', **{k: seg[k] for k in 'bisu'}}))
            else:
                tokens.append(('W', {'text': p, **{k: seg[k] for k in 'bisu'}}))

    lines = [[]]              # chaque ligne = liste de segments
    current_width = 0.0

    def line_append(seg):
        nonlocal current_width
        lines[-1].append(seg)
        current_width += _seg_width(c, seg, font_size)

    def new_line():
        nonlocal current_width
        lines.append([])
        current_width = 0.0

    i = 0
    while i < len(tokens):
        kind, seg = tokens[i]

        if kind == 'NL':
            new_line()
            i += 1
            continue

        if kind == 'SP':
            # On ajoute l'espace seulement si la ligne contient déjà du texte
            if lines[-1]:
                w = _seg_width(c, seg, font_size)
                if current_width + w <= max_width:
                    line_append(seg)
                else:
                    new_line()  # l'espace est consommé par le saut de ligne
            i += 1
            continue

        # kind == 'W' : un mot
        w = _seg_width(c, seg, font_size)
        if current_width + w <= max_width:
            line_append(seg)
            i += 1
        else:
            # On commence une nouvelle ligne avant de poser le mot
            if lines[-1]:
                new_line()
            # Le mot tient-il tout seul sur une ligne vide ?
            if w <= max_width:
                line_append(seg)
                i += 1
            else:
                # Découpe caractère par caractère
                fragment_chars = []
                frag_width = 0.0
                style = {k: seg[k] for k in 'bisu'}
                font = _font_for(seg)
                for ch in seg['text']:
                    cw = c.stringWidth(ch, font, font_size)
                    if frag_width + cw <= max_width:
                        fragment_chars.append(ch)
                        frag_width += cw
                    else:
                        if fragment_chars:
                            line_append({'text': ''.join(fragment_chars), **style})
                        new_line()
                        fragment_chars = [ch]
                        frag_width = cw
                if fragment_chars:
                    line_append({'text': ''.join(fragment_chars), **style})
                i += 1

    # Nettoyer les espaces de fin de ligne et lignes vides résiduelles
    cleaned = []
    for ln in lines:
        # Trim trailing SP
        while ln and ln[-1]['text'].isspace():
            ln.pop()
        cleaned.append(ln)
    if not cleaned:
        cleaned = [[]]
    return cleaned


def _line_width(c, line, font_size):
    return sum(_seg_width(c, s, font_size) for s in line)


def _draw_line(c, line, x, y, font_size):
    """Dessine une ligne (liste de segments) à la position (x, y baseline)."""
    cur_x = x
    for seg in line:
        font = _font_for(seg)
        c.setFont(font, font_size)
        c.drawString(cur_x, y, seg['text'])
        w = c.stringWidth(seg['text'], font, font_size)

        # Souligné : ligne sous la baseline
        if seg['u']:
            ul_y = y - font_size * 0.12
            c.setLineWidth(max(0.4, font_size * 0.05))
            c.setStrokeColor(TEXT_COLOR)
            c.line(cur_x, ul_y, cur_x + w, ul_y)

        # Barré : ligne au milieu du x-height
        if seg['s']:
            st_y = y + font_size * 0.30
            c.setLineWidth(max(0.4, font_size * 0.05))
            c.setStrokeColor(TEXT_COLOR)
            c.line(cur_x, st_y, cur_x + w, st_y)

        cur_x += w


def dessiner_etiquette(c, texte, logo=None):
    """Dessine une étiquette sur la page courante du canvas."""
    page_width  = CARD_WIDTH
    page_height = CARD_HEIGHT

    # Décaler tout le contenu de CUT_MARGIN pour que le tracé de coupe
    # ne soit pas à la bordure exacte de la page (non détecté par VersaWorks).
    c.saveState()
    c.translate(CUT_MARGIN, CUT_MARGIN)

    # --- 1. Fond blanc avec coins arrondis ---
    c.setFillColor(BG_FILL)
    c.setStrokeColor(BG_FILL)
    c.roundRect(
        0, 0,
        page_width, page_height,
        CORNER_RADIUS,
        stroke=0, fill=1,
    )

    # --- 2. Texte centré au milieu de toute la page (avec markdown) ---
    # Supporte : **gras**, *italique* / _italique_, ***gras italique***,
    # ~~barré~~, __souligné__, [texte](url) (texte seul), \n saut de ligne.
    c.setFillColor(TEXT_COLOR)
    max_width = page_width - 6 * mm    # marge horizontale
    max_height = page_height - 6 * mm  # marge verticale = toute la page

    segments = parse_markdown(texte)

    # Ajuster la taille de police pour que le bloc tienne verticalement
    font_size = 16
    while font_size >= 5:
        lines = _wrap_segments(segments, c, font_size, max_width)
        line_height = font_size * 1.2
        total_height = line_height * len(lines)
        if total_height <= max_height:
            break
        font_size -= 0.5

    line_height = font_size * 1.2
    total_height = line_height * len(lines)

    # Centrage vertical sur toute la page
    y_top = (page_height + total_height) / 2

    for idx, line in enumerate(lines):
        lw = _line_width(c, line, font_size)
        x_text = (page_width - lw) / 2
        y_text = y_top - (idx + 1) * line_height + (line_height - font_size) / 2
        _draw_line(c, line, x_text, y_text, font_size)

    # --- 3. Logo centré en bas ---
    if logo:
        x_logo = (page_width - logo.width) / 2
        y_logo = LOGO_MARGIN_BOTTOM
        renderPDF.draw(logo, c, x_logo, y_logo)

    # --- 4. Ligne de découpe CutContour (par-dessus, en dernier) ---
    # Important VersaWorks :
    #   - pas de remplissage (fill = 0)
    #   - trait fin (0.25 pt typique, on met 0.5 pt pour lisibilité)
    #   - en spot color CutContour
    #   - tracé sur une couche au-dessus pour qu'il soit visible/sélectionnable
    c.setStrokeColor(CUT_CONTOUR)
    c.setLineWidth(0.5)
    c.roundRect(
        0, 0,
        page_width, page_height,
        CORNER_RADIUS,
        stroke=1, fill=0,
    )

    c.restoreState()


def generer_pdf(chemin_txt, chemin_pdf, chemin_logo=LOGO_PATH):
    textes = lire_lignes(chemin_txt)
    if not textes:
        raise ValueError(f"Le fichier '{chemin_txt}' ne contient aucune ligne.")

    # Charger le logo une seule fois (réutilisé pour toutes les pages)
    logo = charger_logo(chemin_logo)
    if logo is None and chemin_logo and SVGLIB_AVAILABLE and os.path.isfile(chemin_logo):
        print(f"Avertissement : logo '{chemin_logo}' n'a pas pu être lu, "
              f"il sera ignoré.")
    elif logo is None and chemin_logo and SVGLIB_AVAILABLE:
        # Fichier inexistant — info seulement, pas un avertissement bruyant
        pass

    # Page PDF avec une marge de bleed de CUT_MARGIN sur chaque côté
    # pour que VersaWorks détecte le tracé de coupe sur tous les bords.
    c = canvas.Canvas(
        chemin_pdf,
        pagesize=(CARD_WIDTH + 2 * CUT_MARGIN, CARD_HEIGHT + 2 * CUT_MARGIN),
        pageCompression=1,
    )

    # Métadonnées propres -> évite les avertissements Adobe Reader
    c.setTitle("Etiquettes carte de credit - CutContour")
    c.setAuthor("Generateur d'etiquettes")
    c.setSubject("Etiquettes pour impression Roland VersaWorks")
    c.setCreator("ReportLab - script Python")

    for texte in textes:
        dessiner_etiquette(c, texte, logo=logo)
        c.showPage()

    c.save()
    print(f"PDF généré : {chemin_pdf}  ({len(textes)} étiquette(s))")


def main():
    if len(sys.argv) < 2:
        print("Usage : python generate_etiquettes.py <fichier.txt> "
              "[sortie.pdf] [logo.svg]")
        sys.exit(1)

    chemin_txt = sys.argv[1]
    chemin_pdf = sys.argv[2] if len(sys.argv) >= 3 else "etiquettes.pdf"
    chemin_logo = sys.argv[3] if len(sys.argv) >= 4 else LOGO_PATH

    if not os.path.isfile(chemin_txt):
        print(f"Erreur : fichier introuvable : {chemin_txt}")
        sys.exit(1)

    generer_pdf(chemin_txt, chemin_pdf, chemin_logo)


if __name__ == "__main__":
    main()