"""Reproduces the figure in this directory.

Requires sciglyph:  pip install sciglyph
Run:  python silent-losses_figure.py
docxaudit figure: show the damage, do not list it."""
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Ellipse
from sciglyph import set_canvas, RC, report
from sciglyph.arch import flow, aspect

plt.rcParams.update(RC)
fig = plt.figure(figsize=(11.6, 4.6), dpi=200)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
set_canvas(fig)

INK, MUTE, LINE = "#1a1a1a", "#6b6b6b", "#c8c8c8"
GREEN, RED, BLUE = "#2e7d4f", "#c0392b", "#3a6a9a"

def textline(x, y, w, c=LINE, lw=1.5):
    ax.plot([x, x + w], [y, y], color=c, lw=lw, solid_capstyle="round", zorder=6)

def sheet(x, y, w, h, ec, lw=1.2, z=4):
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=ec, lw=lw, zorder=z))

def circle_mark(x, y, rx=.030, ry=.075, c=RED):
    ax.add_patch(Ellipse((x, y), rx * 2, ry * 2, fc="none", ec=c, lw=1.6,
                         ls=(0, (4, 2)), zorder=12))

# ================= left: the PDF =================
X0, Y0, PW, PH = .045, .215, .255, .560
sheet(X0, Y0, PW, PH, GREEN, 1.4)
ax.text(X0 + PW / 2, Y0 + PH + .048, "PDF", fontsize=11, ha="center",
        weight="bold", color=GREEN, zorder=20)
ax.text(X0 + PW / 2, Y0 + PH + .014, "17 pages", fontsize=7.4, ha="center",
        color=MUTE, zorder=20)

yy = Y0 + PH - .055
textline(X0 + .022, yy, .150, "#8a8a8a", 2.4); yy -= .042
for _ in range(3):
    textline(X0 + .022, yy, PW - .044); yy -= .026
yy -= .020
# a table WITH a grid
tx, tw, th, rows, cols = X0 + .028, PW - .056, .105, 4, 3
for r in range(rows + 1):
    ax.plot([tx, tx + tw], [yy - r * th / rows, yy - r * th / rows],
            color="#6b6b6b", lw=.9, zorder=6)
for c in range(cols + 1):
    ax.plot([tx + c * tw / cols, tx + c * tw / cols], [yy, yy - th],
            color="#6b6b6b", lw=.9, zorder=6)
ax.text(tx + tw / 2, yy - th - .026, "Table 1", fontsize=6.6, ha="center",
        color=MUTE, zorder=20)
yy -= th + .062
# a centred figure
fw, fh = .120, .088
ax.add_patch(Rectangle((X0 + (PW - fw) / 2, yy - fh), fw, fh,
                       fc="#dbe7f3", ec="#7aa5c8", lw=.9, zorder=6))
xx = np.linspace(0, 1, 40)
ax.plot(X0 + (PW - fw) / 2 + xx * fw, yy - fh + (.25 + .5 * np.sin(xx * 7) ** 2) * fh,
        color=BLUE, lw=1.1, zorder=7)
ax.text(X0 + PW / 2, yy - fh - .026, "Figure 1", fontsize=6.6, ha="center",
        color=MUTE, zorder=20)

# ================= right: the .docx =================
X1 = .420
sheet(X1, Y0, PW, PH, "#b8860b", 1.4)
ax.text(X1 + PW / 2, Y0 + PH + .048, ".docx", fontsize=11, ha="center",
        weight="bold", color="#b8860b", zorder=20)
ax.text(X1 + PW / 2, Y0 + PH + .014, "19 pages", fontsize=7.4, ha="center",
        color=RED, weight="bold", zorder=20)

yy = Y0 + PH - .055
textline(X1 + .022, yy, .150, "#8a8a8a", 2.4); yy -= .042
for _ in range(3):
    textline(X1 + .022, yy, PW - .044); yy -= .026
yy -= .020
# the SAME table, collapsed: no grid, squeezed to a sliver
tx = X1 + .028
ax.add_patch(Rectangle((tx, yy - .016), tw * .30, .016, fc="#f2f2f2",
                       ec="#b0b0b0", lw=.8, zorder=6))
for r in range(1, 4):
    ax.plot([tx, tx + tw * .30], [yy - r * .004 - .002, yy - r * .004 - .002],
            color="#d0d0d0", lw=.5, zorder=7)
circle_mark(tx + tw * .15, yy - .008, rx=.052, ry=.028)
ax.text(tx + tw * .15, yy - .052, "columns collapsed", fontsize=6.6,
        ha="center", va="top", color=RED, zorder=20)
yy -= th + .062
# the figure: pushed off, leaving a gap
ax.add_patch(Rectangle((X1 + .028, yy - fh), fw, fh, fc="#f7f7f7",
                       ec="#cccccc", lw=.9, ls=(0, (3, 2)), zorder=6))
ax.text(X1 + .028 + fw / 2, yy - fh / 2, "?", fontsize=15, ha="center",
        va="center", color="#bbbbbb", weight="bold", zorder=7)
circle_mark(X1 + .028 + fw / 2, yy - fh / 2, rx=.048, ry=.058)
ax.text(X1 + .028 + fw / 2, yy - fh - .030, "renders in Word, not on the web",
        fontsize=6.6, ha="center", va="top", color=RED, zorder=20)

# same source, two outputs
ax.text(.3625, Y0 + PH + .048, "same source", fontsize=8, ha="center",
        color=MUTE, style="italic", zorder=20)
flow(ax, (.315, Y0 + PH * .55), (.405, Y0 + PH * .55), c=MUTE, lw=1.1, ms=9)

# ================= right panel: what the tool reports =================
BX = .715
ax.add_patch(FancyBboxPatch((BX, Y0), .258, PH, boxstyle="round,pad=0,rounding_size=.014",
                            fc="#f7fafd", ec=BLUE, lw=1.3, zorder=4))
ax.text(BX + .129, Y0 + PH + .048, "docxaudit", fontsize=11, ha="center",
        weight="bold", color=BLUE, zorder=20)
ax.text(BX + .129, Y0 + PH + .014, "reads the raw OOXML", fontsize=7.4,
        ha="center", color=MUTE, zorder=20)

codes = [("PAGE_COUNT", "17 vs 19", RED),
         ("TBL_NO_GRID", "table 1", RED),
         ("NS_PREFIX", "figures hidden", RED),
         ("NO_PAGEBREAKS", "3 figures", "#b8860b"),
         ("FONT_EA_EMPTY", "CJK headings", "#b8860b")]
yy = Y0 + PH - .080
for code, detail, col in codes:
    ax.add_patch(Rectangle((BX + .022, yy - .008), .010, .026, fc=col, ec="none", zorder=7))
    ax.text(BX + .044, yy + .005, code, fontsize=7.1, ha="left", va="center",
            weight="bold", color=INK, zorder=20)
    ax.text(BX + .044, yy - .022, detail, fontsize=6.4, ha="left", va="center",
            color=MUTE, zorder=20)
    yy -= .078
ax.text(BX + .129, Y0 + .032, "each with the fix", fontsize=6.8, ha="center",
        color=BLUE, style="italic", zorder=20)
flow(ax, (.690, Y0 + PH * .55), (.710, Y0 + PH * .55), c=BLUE, lw=1.2, ms=9)

ax.text(.5, .088, "nothing above raises an error during conversion",
        fontsize=8.4, ha="center", color=RED, weight="bold", zorder=20)
ax.text(.5, .042, "the PDF is fine, the .docx opens without complaint, and the "
                  "table is gone",
        fontsize=7.2, ha="center", color=MUTE, style="italic", zorder=20)

report(fig, ax)
fig.savefig(Path(__file__).with_name("silent-losses.png"),
            dpi=200, bbox_inches="tight", facecolor="white")
print("saved")
