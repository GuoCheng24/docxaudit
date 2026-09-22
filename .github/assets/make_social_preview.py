"""Generate the GitHub social-preview card (1200x630). Reproducible: python3 make_social_preview.py

The card is this tool's own output on the sample it ships: a short paper converted by plain
pandoc, and the four things the converter lost or broke without saying so. Run at draw time,
so the card cannot claim a finding the tool no longer makes.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from cardkit import SANS, card  # noqa: E402
from docxaudit import audit  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
R = audit(str(ROOT / "examples/sample.docx")).as_dict()
S = R["stats"]
FOUND = [(f["level"], f["code"], f["message"]) for f in R["findings"]
         if f["level"] in ("error", "warning")]
if not FOUND:
    raise SystemExit("the shipped sample no longer audits to anything; the card copy is wrong")

SHORT = {"TBL_NO_GRID": "the table has no column grid",
         "NO_PAGEBREAKS": "3 figures, no page breaks",
         "FONT_MISMATCH": "heading font is not the body font",
         "FONT_EA_EMPTY": "no East Asian font in the theme"}


def chart(ax, accent):
    """Coloured words rather than white-on-chip.

    A filled chip with a label on it needs the chip declared to the contrast check and the
    label big enough to read at 360 px; at that size the chip is a smudge anyway. Coloured
    words carry the same severity and are legible.
    """
    # the document as a strip of its own parts, sized by count: what the converter was given
    import matplotlib.pyplot as plt
    parts = [("paragraphs", S["paragraphs"], "#c7c3bc"), ("equations", S["equations"], "#9aa0a6"),
             ("figures", S["images"], "#bf8700"), ("table", S["tables"], "#cf222e")]
    total = sum(v for _, v, _ in parts)
    x = 0.80
    for label, v, col in parts:
        w = 10.40 * v / total
        ax.add_patch(plt.Rectangle((x, 3.42), w, 0.30, color=col, zorder=3))
        x += w
    ax.text(0.78, 3.06, f"{S['paragraphs']} paragraphs, {S['tables']} table, "
                        f"{S['images']} figures, {S['equations']} equations",
            fontsize=34, color="#55585c", family=SANS)
    y = 2.56
    for level, code, _ in FOUND:
        red = level == "error"
        colour = "#cf222e" if red else "#bf8700"
        ax.text(0.80, y, "ERROR" if red else "WARN", fontsize=34, fontweight="bold",
                color=colour, family=SANS, va="center")
        ax.text(2.72, y, SHORT.get(code, code), fontsize=34, color="#17181a",
                family=SANS, va="center")
        y -= 0.52



out = card(
    out=str(pathlib.Path(__file__).parent / "social-preview.png"),
    accent="#bf8700", badge="D",
    kicker="PYTHON PACKAGE  ·  pip install docxaudit",
    headline="What your converter dropped",
    evidence="pandoc reported success on this one short paper",
    chart=chart,
    footer="github.com/GuoCheng24/docxaudit",
    headline_size=46,
)
print(f"written {pathlib.Path(out).name}  {len(FOUND)} findings on the shipped sample")
