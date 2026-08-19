"""docxaudit - find what a converter silently dropped from a .docx.

Converters report success and still lose content: a table that vanished, a
figure that renders in Word but not in Word for the web, a supplement that is
11 pages as PDF and 17 as .docx. This package reads the raw OOXML and reports
the ones that are known to ship unnoticed.

    from docxaudit import audit
    report = audit("paper.docx")
    for f in report.errors:
        print(f.code, f.message, f.fix)

Command line::

    docxaudit paper.docx
    docxaudit paper.docx supplement.docx     # compare two outputs
    docxaudit paper.docx --json --strict
"""

from .audit import audit, compare, Report
from .checks import Finding

__version__ = "0.1.2"
__all__ = ["audit", "compare", "Report", "Finding", "compare_pdf_docx",
           "__version__"]


def compare_pdf_docx(pdf_path, docx_path, keep=None):
    """Render the .docx and compare its layout against a PDF.

    Needs PyMuPDF (``pip install docxaudit[pdf]``) and LibreOffice. Returns
    ``(findings, info)``; raises RuntimeError with an actionable message if
    either is unavailable.
    """
    from .render import compare_pdf_docx as _impl
    return _impl(pdf_path, docx_path, keep=keep)
