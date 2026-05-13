# Générateur d'étiquettes PDF — CutContour / Roland VersaWorks

Petit outil Python qui transforme un fichier texte en PDF d'étiquettes prêtes à imprimer et découper sur une imprimante/plotter **Roland VersaWorks**.

Chaque étiquette :

- Format **carte de crédit** (ISO/IEC 7810 ID-1, 85,60 × 53,98 mm)
- **Coins arrondis** (rayon 3,18 mm, conforme à la norme)
- **Fond blanc**, **texte noir**, supporte le **Markdown inline**
- **Logo SVG** centré en bas (optionnel)
- **Ligne de découpe** en spot color `CutContour` (magenta 100 %), automatiquement reconnue par VersaWorks pour piloter le plotter de coupe

Le PDF généré est conforme à la spec PDF et s'ouvre sans avertissement dans Adobe Reader.

---

## Sommaire

- [Installation](#installation)
- [Utilisation](#utilisation)
- [Format du fichier `.txt`](#format-du-fichier-txt)
- [Syntaxe Markdown supportée](#syntaxe-markdown-supportée)
- [Logo](#logo)
- [Configuration](#configuration)
- [Détails techniques — VersaWorks](#détails-techniques--versaworks)
- [Dépannage](#dépannage)

---

## Installation

Prérequis : **Python 3.8 ou plus récent**.

```bash
pip install reportlab svglib
```

| Dépendance    | Rôle                                               | Obligatoire ?                                     |
| ------------- | -------------------------------------------------- | ------------------------------------------------- |
| **reportlab** | Génération du PDF et de la spot color `CutContour` | ✅ Oui                                            |
| **svglib**    | Conversion du logo SVG en objet PDF                | ❌ Non — requis uniquement si tu utilises un logo |

> Si `svglib` n'est pas installé, le script fonctionne quand même : il génère les étiquettes sans logo et affiche un avertissement.

---

## Utilisation

```bash
# Forme minimale
python generate_etiquettes.py textes.txt

# Avec nom de sortie personnalisé
python generate_etiquettes.py textes.txt sortie.pdf

# Avec logo personnalisé
python generate_etiquettes.py textes.txt sortie.pdf mon_logo.svg
```

Par défaut :

- Sortie : `etiquettes.pdf`
- Logo : `logo.svg` (dans le dossier courant, s'il existe)

---

## Format du fichier `.txt`

Une ligne du fichier = une étiquette = une page PDF.

Les lignes vides sont ignorées.

```text
Étiquette simple
Produit A — 250 g
Lot #2025-001
```

Pour avoir **plusieurs lignes à l'intérieur d'une même étiquette**, utilise la séquence `\n` (antislash + n) :

```text
**Produit A**\n250 g — édition limitée
~~25,00 $~~\n**19,99 $**
```

Pour insérer un `\n` **littéral** dans l'étiquette (pas de saut), double l'antislash : `\\n`.

---

## Syntaxe Markdown supportée

### Mise en forme inline

| Syntaxe             | Effet                          | Exemple                              |
| ------------------- | ------------------------------ | ------------------------------------ |
| `**texte**`         | **Gras**                       | `**Promo**` → **Promo**              |
| `*texte*`           | _Italique_                     | `*nouveau*` → _nouveau_              |
| `_texte_`           | _Italique_ (variante)          | `_nouveau_` → _nouveau_              |
| `***texte***`       | **_Gras italique_**            | `***Top***` → **_Top_**              |
| `~~texte~~`         | ~~Barré~~                      | `~~25 $~~` → ~~25 $~~                |
| `__texte__`         | <u>Souligné</u>                | `__Important__` → <u>Important</u>   |
| `[texte](url)`      | Affiche le texte, ignore l'URL | `[Site web](https://...)` → Site web |
| `\*` `\_` `\~` `\\` | Caractère littéral             | `prix \*spécial\*` → prix _spécial_  |

> ⚠️ **Différence avec le Markdown standard** : `__texte__` est utilisé ici pour le **souligné** (et non du gras). Le gras est uniquement `**texte**`.

Les styles **peuvent se combiner et s'imbriquer** :

```text
**Gras avec *italique* à l'intérieur**
__Souligné et **gras**__
```

### Saut de ligne

| Syntaxe | Effet                                      |
| ------- | ------------------------------------------ |
| `\n`    | Saut de ligne à l'intérieur de l'étiquette |
| `\\n`   | Antislash + n littéraux (pas de saut)      |

### Non supporté volontairement

Pas adapté à des étiquettes au format carte de crédit :

- Titres (`#`, `##`, ...)
- Listes (`-`, `*`, `1.`)
- Citations (`>`)
- Code (`` `code` `` et blocs)
- Images
- Tableaux

---

## Logo

- Le logo doit être au format **SVG** (vectoriel, donc net à toutes les résolutions d'impression).
- Il est **centré en bas** de l'étiquette, avec une marge de 2,5 mm depuis le bord.
- Hauteur cible par défaut : **8 mm** (la largeur s'ajuste pour conserver le ratio).
- Si le fichier n'existe pas, le script continue sans logo et affiche un avertissement.

```bash
python generate_etiquettes.py textes.txt sortie.pdf mon_logo.svg
```

---

## Configuration

Les constantes en haut du script `generate_etiquettes.py` sont éditables :

```python
# Dimensions
CARD_WIDTH         = 85.60 * mm   # largeur
CARD_HEIGHT        = 53.98 * mm   # hauteur
CORNER_RADIUS      = 3.18 * mm    # rayon des coins arrondis

# Logo
LOGO_PATH          = "logo.svg"
LOGO_HEIGHT        = 8 * mm       # hauteur cible du logo
LOGO_MARGIN_BOTTOM = 2.5 * mm     # marge depuis le bord bas

# Couleurs
BG_FILL    = CMYKColor(0, 0, 0, 0)   # fond (blanc)
TEXT_COLOR = CMYKColor(0, 0, 0, 1)   # texte (noir)
```

La taille de police s'ajuste **automatiquement** entre 5 pt et 16 pt pour que tout le texte tienne dans l'étiquette, peu importe sa longueur. Le retour à la ligne se fait d'abord aux espaces, puis caractère par caractère pour les mots très longs.

---

## Détails techniques — VersaWorks

Pour que VersaWorks détecte automatiquement la ligne de découpe, le PDF doit contenir une **vraie spot color** (séparation PDF) nommée **exactement** `CutContour`.

Le script utilise `CMYKColorSep` de ReportLab, ce qui produit dans le PDF :

```
/Separation /CutContour /DeviceCMYK
```

C'est exactement ce que VersaWorks recherche. La couleur d'aperçu est **magenta 100 %** (convention Roland), pour qu'elle soit bien visible dans Adobe Reader sans interférer avec l'impression.

Caractéristiques de la ligne de découpe :

- Trait fin (0,5 pt)
- Sans remplissage
- Tracée **par-dessus** tout le reste, donc toujours sélectionnable
- Suit exactement les coins arrondis ISO

**Note Adobe Reader** : la ligne apparaît en magenta — c'est normal. À l'impression CMYK ou en spot color, elle est traitée comme un canal de séparation et ne sera pas imprimée mais utilisée pour la découpe par le plotter.

---

## Dépannage

**« Avertissement : la librairie 'svglib' n'est pas installée »**
→ Installe-la avec `pip install svglib`, ou retire l'argument logo si tu n'en as pas besoin.

**Le texte dépasse de l'étiquette**
→ Tu as un mot extrêmement long sans aucun espace. Le script descend jusqu'à 5 pt et coupe ensuite caractère par caractère, mais avec un texte vraiment trop volumineux, il y aura quand même débordement. Raccourcis le texte ou divise-le avec `\n`.

**VersaWorks n'imprime pas la ligne de découpe ou la considère comme une couleur normale**
→ Vérifie dans VersaWorks que le swatch s'appelle `CutContour` (sensible à la casse) et qu'il est configuré comme un trait de coupe dans le profil d'impression. Le PDF contient bien la spot color, mais c'est VersaWorks qui décide comment l'interpréter.

**Caractères accentués mal affichés**
→ Assure-toi que ton fichier `.txt` est encodé en **UTF-8** (la plupart des éditeurs modernes le font par défaut).

---

## Licence

[MIT](LICENSE) — libre d'utilisation, modification et distribution.
