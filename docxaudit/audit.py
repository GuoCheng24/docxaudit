"""Run every check against a .docx and summarise the result."""

import json
import zipfile

from . import checks
from .checks import Finding


class Report:
    """Findings plus the counts they were derived from."""

    def __init__(self, path):
        self.path = path
        self.findings = []
        self.stats = {}

    @property
    def errors(self):
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self):
        return [f for f in self.findings if f.level == "warning"]

    def as_dict(self):
        return {
            "file": self.path,
            "stats": self.stats,
            "findings": [
                {"level": f.level, "code": f.code, "message": f.message,
                 "detail": f.detail, "fix": f.fix}
                for f in self.findings
            ],
        }

    def to_json(self, indent=2):
        return json.dumps(self.as_dict(), indent=indent, ensure_ascii=False)


def audit(path):
    """Audit one .docx. Returns a :class:`Report`."""
    rep = Report(path)
    try:
        zipfile.ZipFile(path)
    except (zipfile.BadZipFile, FileNotFoundError) as e:
        rep.findings.append(Finding("error", "UNREADABLE", f"cannot open: {e}"))
        return rep

    doc = checks._read(path, "word/document.xml")
    if not doc:
        rep.findings.append(Finding(
            "error", "NO_DOCUMENT", "word/document.xml is missing or empty"))
        return rep
    styles = checks._read(path, "word/styles.xml")
    theme = checks._read(path, "word/theme/theme1.xml")

    rep.findings += checks.check_namespaces(doc)

    tbl_findings, n_tables = checks.check_tables(doc)
    rep.findings += tbl_findings

    eq_findings, n_eq, n_display = checks.check_equations(doc)
    rep.findings += eq_findings

    media_findings, n_media, n_draw = checks.check_media(path, doc)
    rep.findings += media_findings

    pb_findings, n_breaks = checks.check_pagebreaks(doc, n_draw)
    rep.findings += pb_findings

    rep.findings += checks.check_fonts(styles, theme)
    rep.findings += checks.check_heading_colour(styles)
    rep.findings += checks.check_duplicate_prefixes(doc)
    rep.findings += checks.check_empty_headings(doc)

    import re
    rep.stats = {
        "paragraphs": len(re.findall(r"<w:p[ >]", doc)),
        "tables": n_tables,
        "images": n_media,
        "drawings": n_draw,
        "equations": n_eq,
        "display_equations": n_display,
        "page_breaks": n_breaks,
        "characters": len(re.sub(r"<[^>]+>", "", doc)),
    }
    return rep


def compare(report_a, report_b):
    """Compare two audited documents and report structural drift.

    Use this on the two outputs of one source - the version you send and the
    version you proofread - or on a document before and after post-processing.
    """
    out = []
    keys = ("tables", "images", "equations", "paragraphs")
    for k in keys:
        a, b = report_a.stats.get(k, 0), report_b.stats.get(k, 0)
        if a != b:
            level = "error" if k in ("tables", "images", "equations") else "warning"
            out.append(Finding(
                level, f"DRIFT_{k.upper()}",
                f"{k}: {a} in {report_a.path} vs {b} in {report_b.path}",
                detail="content present in one output and missing from the other",
                fix="Find what the converter dropped and pre-process the source "
                    "so it survives."))
    ca = report_a.stats.get("characters", 0)
    cb = report_b.stats.get("characters", 0)
    if ca and cb:
        ratio = min(ca, cb) / max(ca, cb)
        if ratio < 0.9:
            out.append(Finding(
                "error", "DRIFT_TEXT",
                f"text length differs by {(1 - ratio) * 100:.0f}%",
                detail=f"{ca} vs {cb} characters"))
    return out
