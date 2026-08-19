"""Structural checks for .docx files produced by a converter.

Every check here corresponds to a failure that actually shipped: a table that
vanished, figures that disappeared in Word for the web, a supplement that was
11 pages as PDF and 17 as .docx. What they have in common is that the
conversion reported success and the problem only surfaced later.

Two things make these failures hard to catch by hand:

* ``python-docx`` cannot see equations (OMML) or content the converter
  dropped, so "the text looks fine" is not evidence.
* A LibreOffice preview is misleading in *both* directions: it invents ugly
  font substitutions that real Word does not have, and it is forgiving enough
  to render documents that stricter viewers refuse.

So these checks read the raw OOXML instead.
"""

import re
import zipfile

# The namespace prefixes that strict viewers expect. If a post-processing step
# re-serialised the XML without registering these, they come out as ns2/ns3/...
# Real Word resolves by URI and renders fine; a LibreOffice preview also
# renders fine; Word for the web shows neither figures nor equations.
STANDARD_PREFIXES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


class Finding:
    """One problem, with enough context to act on it."""

    def __init__(self, level, code, message, detail="", fix=""):
        self.level = level          # "error" | "warning" | "info"
        self.code = code
        self.message = message
        self.detail = detail
        self.fix = fix

    def __repr__(self):
        return f"<{self.level.upper()} {self.code}: {self.message}>"


def _read(path, member):
    with zipfile.ZipFile(path) as z:
        try:
            return z.read(member).decode("utf-8", "replace")
        except KeyError:
            return ""


def _members(path):
    with zipfile.ZipFile(path) as z:
        return z.namelist()


# --------------------------------------------------------------------------
def check_namespaces(doc_xml):
    """Non-standard namespace prefixes silently hide figures and equations.

    Word resolves namespaces by URI so it renders correctly, which is why this
    survives desk review; strict viewers key off the conventional prefix and
    show nothing.
    """
    out = []
    declared = dict(re.findall(r'xmlns:([A-Za-z0-9_]+)="([^"]+)"', doc_xml[:4000]))
    uri_to_prefix = {v: k for k, v in declared.items()}
    for want, uri in STANDARD_PREFIXES.items():
        got = uri_to_prefix.get(uri)
        if got and got != want:
            out.append(Finding(
                "error", "NS_PREFIX",
                f"namespace {uri.rsplit('/', 1)[-1]} bound to '{got}:' instead of '{want}:'",
                detail=f"{uri}",
                fix="Re-serialise with every prefix registered: for each xmlns "
                    "declaration on the root element, call "
                    "ET.register_namespace(prefix, uri) BEFORE writing. "
                    "Registering only 'w' is the usual cause."))
    if re.search(r"<ns\d+:", doc_xml):
        out.append(Finding(
            "error", "NS_GENERATED",
            "auto-generated namespace prefixes (ns2:, ns3:, ...) present",
            detail="figures and equations will not render in strict viewers",
            fix="Same fix as NS_PREFIX - register all prefixes before serialising."))
    return out


def check_tables(doc_xml):
    """A table with no grid collapses to a sliver in Word.

    Converters that build tables from LaTeX booktabs often emit no <w:tblGrid>
    and a zero table width, which renders acceptably in a preview and badly in
    Word.
    """
    out = []
    tables = re.findall(r"<w:tbl>.*?</w:tbl>", doc_xml, re.S)
    for i, t in enumerate(tables, 1):
        if "<w:tblGrid>" not in t:
            out.append(Finding(
                "error", "TBL_NO_GRID", f"table {i} has no <w:tblGrid>",
                detail="columns collapse; the reader has to AutoFit by hand",
                fix="Inject an equal-width tblGrid plus a per-cell <w:tcW>, and "
                    'set <w:tblLayout w:type="autofit"/>.'))
        m = re.search(r'<w:tblW[^/]*w:w="(\d+)"', t)
        if m and m.group(1) == "0":
            out.append(Finding(
                "warning", "TBL_ZERO_WIDTH", f"table {i} declares width 0",
                fix='Set <w:tblW w:w="5000" w:type="pct"/> for full width.'))
    return out, len(tables)


def check_equations(doc_xml):
    """Count equations, and flag inline ones as fragile.

    Converters mangle complex inline maths - \\ast becoming a combining
    diacritic, inline products turning into an inverted question mark - and it
    ships that way if nobody looks. Display equations survive far better.
    """
    out = []
    inline = len(re.findall(r"<m:oMath[ >]", doc_xml)) - len(re.findall(r"<m:oMathPara[ >]", doc_xml))
    para = len(re.findall(r"<m:oMathPara[ >]", doc_xml))
    if inline > 0:
        out.append(Finding(
            "info", "MATH_INLINE", f"{inline} inline equation(s)",
            detail="inline maths converts least reliably; check each one visually",
            fix="Where the maths carries meaning, prefer display mode."))
    return out, inline + para, para


def check_media(path, doc_xml):
    """Compare embedded images against the drawings that reference them."""
    out = []
    media = [m for m in _members(path)
             if m.startswith("word/media/") and not m.endswith("/")]
    drawings = len(re.findall(r"<w:drawing>", doc_xml))
    if media and drawings == 0:
        out.append(Finding(
            "error", "IMG_ORPHAN",
            f"{len(media)} image file(s) embedded but no <w:drawing> references them",
            fix="The images are dead weight - the conversion dropped their anchors."))
    elif drawings < len(media):
        out.append(Finding(
            "warning", "IMG_FEWER_REFS",
            f"{len(media)} image files but only {drawings} drawing references"))
    return out, len(media), drawings


def check_pagebreaks(doc_xml, drawings):
    """One-figure-per-page does not survive conversion on its own.

    A \\clearpage in the source does not become a page break in .docx, so a
    supplement that is one figure per page in PDF can arrive at the editor
    several pages shorter or longer. Page counts have triggered desk rejections.
    """
    out = []
    breaks = len(re.findall(r'<w:br[^>]*w:type="page"', doc_xml))
    breaks += len(re.findall(r"<w:pageBreakBefore/>", doc_xml))
    if drawings >= 3 and breaks == 0:
        out.append(Finding(
            "warning", "NO_PAGEBREAKS",
            f"{drawings} figures but no page breaks at all",
            detail="if the PDF puts one figure per page, the .docx will not match, "
                   "and reviewers count the .docx",
            fix="Insert <w:pageBreakBefore/> into the pPr of each paragraph that "
                "contains a <w:drawing> (not the caption paragraph)."))
    return out, breaks


def check_fonts(styles_xml, theme_xml):
    """Theme fonts that disagree with the document defaults.

    Headings follow the theme, body text follows docDefaults; when a converter
    template leaves them inconsistent you get sans-serif blue headings above
    serif body text. With an empty East Asian theme font, CJK headings fall
    back to whatever the renderer picks and stop matching the body.
    """
    out = []
    theme_latin = re.findall(r'<a:latin typeface="([^"]*)"', theme_xml)
    major, minor = (theme_latin + ["", ""])[:2]
    m = re.search(r"<w:docDefaults>.*?<w:rFonts[^>]*w:ascii=\"([^\"]+)\"", styles_xml, re.S)
    default = m.group(1) if m else ""
    if default and major and major != default:
        out.append(Finding(
            "warning", "FONT_MISMATCH",
            f"heading font '{major}' differs from body font '{default}'",
            fix="Set <a:latin typeface> for both majorFont and minorFont in "
                "word/theme/theme1.xml to the body font."))
    ea = re.findall(r'<a:ea typeface="([^"]*)"', theme_xml)
    if ea and all(e == "" for e in ea) and re.search(r'w:eastAsia="[^"]+"', styles_xml):
        out.append(Finding(
            "warning", "FONT_EA_EMPTY",
            "theme East Asian font is empty while the body sets one",
            detail="CJK headings will fall back and stop matching the body text",
            fix="Set <a:ea typeface> in majorFont and minorFont."))
    return out


def check_heading_colour(styles_xml):
    """Coloured headings betray an untouched default template."""
    out = []
    accents = re.findall(r'<w:color w:val="(4F81BD|1F497D|365F91|17365D|4472C4|2E74B5|1F4E79|2F5496)"',
                         styles_xml)
    if accents:
        out.append(Finding(
            "info", "HEADING_COLOUR",
            f"{len(accents)} heading style(s) use the default template's blue",
            detail="a LaTeX PDF renders headings in black, so the two versions "
                   "will not look like the same paper",
            fix="Replace those <w:color w:val=...> with 000000 and drop "
                "w:themeColor."))
    return out


def check_duplicate_prefixes(doc_xml):
    """'Lemma Lemma 1' - a cross-reference prefix applied twice."""
    out = []
    text = re.sub(r"<[^>]+>", "", doc_xml)
    for word in ("Figure", "Table", "Lemma", "Theorem", "Equation", "Section"):
        hits = re.findall(rf"\b{word}\s+{word}\b", text)
        if hits:
            out.append(Finding(
                "error", "DUP_PREFIX",
                f"'{word} {word}' appears {len(hits)} time(s)",
                detail="the source wrote the prefix and the converter added its own",
                fix="Drop the literal prefix in the source, or hard-code the number."))
    return out


def check_empty_headings(doc_xml):
    """Headings whose text was dropped in conversion."""
    out = []
    paras = re.findall(r"<w:p[ >].*?</w:p>", doc_xml, re.S)
    empty = 0
    for p in paras:
        if re.search(r'w:val="Heading', p) and not re.sub(r"<[^>]+>", "", p).strip():
            empty += 1
    if empty:
        out.append(Finding(
            "warning", "EMPTY_HEADING", f"{empty} heading paragraph(s) contain no text",
            fix="Usually a construct the converter could not represent - check "
                "the corresponding place in the source."))
    return out
