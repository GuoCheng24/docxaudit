"""Compare a PDF against a .docx by rendering both and measuring the result.

Structural checks catch content that vanished. They cannot catch *layout*
drift: the same content laid out over a different number of pages, or figures
that ended up two-to-a-page in one output and one-to-a-page in the other.

That distinction has consequences. A supplement can be 11 pages as a
LaTeX PDF and 17 pages as the .docx built from the same source, and it is the
.docx a journal office counts.

This module needs two optional things:

* **PyMuPDF** to read PDFs - ``pip install docxaudit[pdf]``
* **LibreOffice** on PATH (or ``DOCXAUDIT_SOFFICE``) to render .docx

Both are optional; without them the structural checks still work.
"""

import os
import shutil
import subprocess
import tempfile

__all__ = ["find_soffice", "have_pymupdf", "docx_to_pdf", "pdf_stats",
           "compare_pdf_docx"]

_SOFFICE_CANDIDATES = (
    "soffice", "libreoffice",
    "/usr/bin/soffice", "/usr/local/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
)


def find_soffice():
    """Locate LibreOffice. ``DOCXAUDIT_SOFFICE`` overrides the search."""
    env = os.environ.get("DOCXAUDIT_SOFFICE")
    if env and os.path.exists(env):
        return env
    for c in _SOFFICE_CANDIDATES:
        found = shutil.which(c) if not os.path.isabs(c) else (c if os.path.exists(c) else None)
        if found:
            return found
    return None


def have_pymupdf():
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def docx_to_pdf(path, outdir=None, timeout=180):
    """Render a .docx to PDF with LibreOffice. Returns the PDF path.

    Each call gets its own user profile. Concurrent LibreOffice processes
    share one profile by default, and the second one blocks on the profile
    lock without printing anything - it simply appears to hang.
    """
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice not found. Install it, or point DOCXAUDIT_SOFFICE at "
            "the soffice binary.")
    outdir = outdir or tempfile.mkdtemp(prefix="docxaudit_")
    os.makedirs(outdir, exist_ok=True)
    profile = os.path.join(outdir, ".profile_%d" % os.getpid())
    cmd = [
        soffice,
        "-env:UserInstallation=file://%s" % profile,
        "--headless", "--norestore", "--invisible",
        "--convert-to", "pdf", "--outdir", outdir, path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=timeout)
    out = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
    if not os.path.exists(out):
        raise RuntimeError(f"LibreOffice produced no PDF for {path}")
    return out


def pdf_stats(path):
    """Per-page measurements from a rendered PDF.

    Images are counted with ``get_image_info()``, which reports what is placed
    on *this* page. ``get_images()`` returns the document's image resources and
    gives every page the same total, which looks like uniform placement and is
    not.
    """
    import fitz

    doc = fitz.open(path)
    pages = []
    for p in doc:
        text = p.get_text().strip()
        raster = len(p.get_image_info())
        # A LaTeX PDF usually carries its figures as vector drawing operators,
        # not embedded rasters, so counting images alone reports zero figures
        # for a paper that plainly has them. Treat a page dense in drawing
        # operators as holding vector artwork.
        vector = len(p.get_drawings())
        pages.append({
            "images": raster,
            "vector_ops": vector,
            "has_figure": raster > 0 or vector >= 40,
            "chars": len(text),
            "blank": len(text) == 0 and raster == 0 and vector < 5,
        })
    stats = {
        "pages": len(pages),
        "images": sum(p["images"] for p in pages),
        "figure_pages": sum(1 for p in pages if p["has_figure"]),
        "vector_heavy": sum(1 for p in pages if p["images"] == 0 and p["vector_ops"] >= 40),
        "chars": sum(p["chars"] for p in pages),
        "blank_pages": sum(1 for p in pages if p["blank"]),
        "per_page": pages,
    }
    doc.close()
    return stats


_SKIP = ("http", "www.", "doi.org", "arxiv", "@", "\\", "{", "}")


def _norm_words(path):
    """Plain prose words only.

    Two renderings of one manuscript legitimately differ in ways that are not
    content loss, and including them buries the signal:

    * **Maths.** A LaTeX PDF renders symbols as Unicode mathematical
      alphanumerics; the .docx stores OMML. Extracting text from each gives
      different strings for identical equations.
    * **References and numbers.** DOIs, URLs and table cells reformat freely
      between the two.

    So only ASCII prose is compared - if a *sentence* went missing, that shows
    up here; if an equation merely re-encoded, it does not.
    """
    import fitz

    doc = fitz.open(path)
    raw = " ".join(p.get_text() for p in doc).split()
    doc.close()

    # Rejoin words split by justified typesetting: a PDF hyphenates
    # "advantage" into "advan-" + "tage" and the .docx does not, which would
    # otherwise show up as two words missing from each side.
    merged, i = [], 0
    while i < len(raw):
        w = raw[i]
        if w.endswith("-") and i + 1 < len(raw) and raw[i + 1][:1].islower():
            merged.append(w[:-1] + raw[i + 1]); i += 2
        else:
            merged.append(w); i += 1

    out, pos = [], []
    n = len(merged) or 1
    for idx, w in enumerate(merged):
        w = w.strip(".,;:()[]{}\u2013\u2014\u2019\"'").lower()
        if len(w) <= 3 or any(k in w for k in _SKIP):
            continue
        # ASCII letters and hyphens only: drops maths, Greek, subscripted
        # variables and stray LaTeX labels in one stroke.
        if not all(("a" <= c <= "z") or c == "-" for c in w):
            continue
        out.append(w); pos.append(idx / n)
    return out, pos


def compare_pdf_docx(pdf_path, docx_path, keep=None):
    """Render the .docx and compare it against the PDF.

    Returns ``(findings, info)``. Requires PyMuPDF and LibreOffice; raises
    RuntimeError with an actionable message when either is missing.
    """
    from .checks import Finding

    if not have_pymupdf():
        raise RuntimeError(
            "PyMuPDF is required to read PDFs: pip install docxaudit[pdf]")

    rendered = docx_to_pdf(docx_path, outdir=keep)
    a = pdf_stats(pdf_path)
    b = pdf_stats(rendered)
    out = []

    if a["pages"] != b["pages"]:
        diff = abs(a["pages"] - b["pages"])
        out.append(Finding(
            "error", "PAGE_COUNT",
            f"page count differs: {a['pages']} (pdf) vs {b['pages']} (docx)",
            detail=f"{diff} page(s) apart; journals count the .docx",
            fix="Usually page breaks around figures. Check NO_PAGEBREAKS in the "
                "structural audit, and whether images are being inserted at "
                "their native size."))

    # Compare pages that carry a figure rather than raw image counts: one side
    # may hold vector artwork and the other a rasterised copy of the same thing.
    if a["images"] == 0 and a["vector_heavy"] and b["images"]:
        out.append(Finding(
            "info", "VECTOR_FIGURES",
            f"the pdf draws its figures as vectors on {a['vector_heavy']} page(s); "
            f"the docx embeds {b['images']} raster image(s)",
            detail="expected for a LaTeX PDF - image counts are not comparable, "
                   "so figure-bearing pages are compared instead"))
    elif a["images"] != b["images"]:
        out.append(Finding(
            "error", "IMAGE_COUNT",
            f"image count differs: {a['images']} (pdf) vs {b['images']} (docx)",
            fix="A figure was dropped in conversion, or one vector figure was "
                "rasterised into several pieces."))

    if a["figure_pages"] != b["figure_pages"]:
        out.append(Finding(
            "warning", "FIGURE_PAGES",
            f"pages carrying a figure: {a['figure_pages']} (pdf) vs "
            f"{b['figure_pages']} (docx)",
            fix="Usually page breaks, not missing figures - check NO_PAGEBREAKS."))

    # Figures per page: one-per-page in the PDF and several in the .docx is the
    # usual reason the page counts drift.
    fa = [p["images"] for p in a["per_page"] if p["images"]]
    fb = [p["images"] for p in b["per_page"] if p["images"]]
    if not fa:
        fa = []          # vector-drawn figures cannot be counted this way
    if fa and fb and max(fa) != max(fb):
        out.append(Finding(
            "warning", "FIGURE_PACKING",
            f"busiest page holds {max(fa)} figure(s) in the pdf vs {max(fb)} in the docx",
            fix="If the PDF is one figure per page, insert a page break before "
                "each figure paragraph in the .docx."))

    if b["blank_pages"] > a["blank_pages"]:
        out.append(Finding(
            "warning", "BLANK_PAGES",
            f"the rendered .docx has {b['blank_pages']} blank page(s), "
            f"the pdf has {a['blank_pages']}"))

    la, pa = _norm_words(pdf_path)
    lb, _ = _norm_words(rendered)
    wa, wb = set(la), set(lb)
    only_pdf, only_docx = wa - wb, wb - wa
    union = len(wa | wb) or 1

    # Where the missing words sit decides what they mean. Bunched at the end,
    # they are almost always reference-list formatting - the two outputs cite
    # the same works in different styles. Spread through the body, something
    # was actually dropped.
    where = [p for w, p in zip(la, pa) if w in only_pdf]
    tail = sum(1 for p in where if p > 0.75) / (len(where) or 1)

    if len(only_pdf) / union > 0.02:
        sample = ", ".join(sorted(only_pdf)[:8])
        if tail > 0.7:
            out.append(Finding(
                "info", "TEXT_TAIL_ONLY",
                f"{len(only_pdf)} word(s) appear only in the pdf, "
                f"{tail * 100:.0f}% of them in the final quarter",
                detail=f"e.g. {sample}",
                fix="Concentrated at the end: this is normally the reference "
                    "list rendered in a different citation style, not lost "
                    "content. Confirm the two use the same CSL/bibliography "
                    "style if you need them identical."))
        else:
            out.append(Finding(
                "error", "TEXT_ONLY_IN_PDF",
                f"{len(only_pdf)} distinct word(s) appear only in the pdf, "
                f"spread through the body",
                detail=f"e.g. {sample}",
                fix="Content the converter dropped. Tables wrapped in resizebox "
                    "or minipage are the usual suspects - they vanish silently "
                    "while the PDF renders fine."))
    if len(only_docx) / union > 0.02:
        sample = ", ".join(sorted(only_docx)[:8])
        out.append(Finding(
            "warning", "TEXT_ONLY_IN_DOCX",
            f"{len(only_docx)} distinct word(s) appear only in the docx",
            detail=f"e.g. {sample}",
            fix="Often a converter artefact: a running header pulled into the "
                "body, or a cross-reference prefix emitted twice."))

    return out, {"pdf": a, "docx": b, "rendered": rendered}
