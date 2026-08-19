"""docxaudit - find what your converter silently dropped from a .docx.

Pandoc, and every LaTeX/Markdown -> Word pipeline, reports success and still
loses things: a table collapses to zero width, figures render in desktop Word
but not on the web, an 11-page PDF supplement arrives as 17 pages of .docx and
the editor counts the .docx. None of it surfaces as an error; you hear it from
a reviewer.

This reads the raw OOXML and names the specific failures, each with the fix.
Give it two files - the PDF you meant and the .docx you got - and it reports
what the conversion lost between them.
"""

import argparse
import sys

from .audit import audit, compare

_ICON = {"error": "ERROR  ", "warning": "WARN   ", "info": "INFO   "}


def _print_report(rep, show_fix=True):
    s = rep.stats
    if s:
        print(f"{rep.path}")
        print(f"  {s['paragraphs']} paragraphs · {s['tables']} tables · "
              f"{s['images']} images ({s['drawings']} referenced) · "
              f"{s['equations']} equations ({s['display_equations']} display) · "
              f"{s['page_breaks']} page breaks")
        print()
    if not rep.findings:
        print("  No problems found.")
        return
    for f in rep.findings:
        print(f"  {_ICON[f.level]} [{f.code}] {f.message}")
        if f.detail:
            print(f"          {f.detail}")
        if show_fix and f.fix:
            for i, line in enumerate(_wrap(f.fix, 72)):
                print(f"          {'fix: ' if i == 0 else '     '}{line}")
        print()


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line); line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def _pdf_docx(pdf, docx, a):
    """Render the .docx and compare it against the PDF."""
    from .render import compare_pdf_docx

    rep = audit(docx)
    try:
        drift, info = compare_pdf_docx(pdf, docx, keep=a.keep)
    except RuntimeError as e:
        print(f"  {e}")
        print("  (the structural audit below does not need either of them)")
        print()
        _print_report(rep, show_fix=not a.quiet)
        return 1

    if a.json:
        import json as _json
        print(_json.dumps({
            "structural": rep.as_dict(),
            "pdf": {k: v for k, v in info["pdf"].items() if k != "per_page"},
            "docx": {k: v for k, v in info["docx"].items() if k != "per_page"},
            "drift": [{"level": f.level, "code": f.code, "message": f.message,
                       "detail": f.detail, "fix": f.fix} for f in drift],
        }, indent=2, ensure_ascii=False))
        return 1 if any(f.level == "error" for f in drift) or rep.errors else 0

    ip, idx = info["pdf"], info["docx"]
    print(f"{pdf}")
    print(f"  {ip['pages']} pages · {ip['images']} images · {ip['chars']} chars")
    print(f"{docx}  (rendered)")
    print(f"  {idx['pages']} pages · {idx['images']} images · {idx['chars']} chars")
    print()
    _print_report(rep, show_fix=not a.quiet)
    print("layout comparison")
    if not drift:
        print("  The two outputs agree on layout.")
    for f in drift:
        print(f"  {_ICON[f.level]} [{f.code}] {f.message}")
        if f.detail:
            print(f"          {f.detail}")
        if f.fix and not a.quiet:
            for i, line in enumerate(_wrap(f.fix, 72)):
                print(f"          {'fix: ' if i == 0 else '     '}{line}")
        print()
    n_err = len(rep.errors) + sum(1 for f in drift if f.level == "error")
    n_warn = len(rep.warnings) + sum(1 for f in drift if f.level == "warning")
    return 1 if (n_err or (a.strict and n_warn)) else 0


def _main(argv=None):
    # Typing the bare command is how most people first meet a CLI; argparse's
    # default there is an error message, which is a poor greeting.
    if argv is None and len(sys.argv) == 1:
        print(__doc__.strip() if __doc__ else "docxaudit")
        print("\nTry it on a file you already have:\n"
              "  docxaudit paper.docx\n"
              "  docxaudit paper.docx --strict        # non-zero exit on warnings too\n"
              "  docxaudit paper.pdf paper.docx       # compare what the conversion lost\n"
              "\ndocxaudit --help  for every option.")
        return 0
    ap = argparse.ArgumentParser(
        prog="docxaudit",
        description="Find what a converter silently dropped from a .docx.")
    ap.add_argument("files", nargs="+", metavar="FILE",
                    help="one .docx to audit, two .docx to compare, or a .pdf "
                         "and a .docx to check them against each other")
    ap.add_argument("--keep", metavar="DIR", default=None,
                    help="keep the rendered PDF of the .docx in DIR")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true",
                    help="findings only, no suggested fixes")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on warnings as well as errors")
    a = ap.parse_args(argv)

    # pdf + docx -> render the docx and compare layout, not just structure
    pdfs = [f for f in a.files if f.lower().endswith(".pdf")]
    docxs = [f for f in a.files if f.lower().endswith(".docx")]
    if len(pdfs) == 1 and len(docxs) == 1:
        return _pdf_docx(pdfs[0], docxs[0], a)

    reports = [audit(f) for f in a.files]

    if a.json:
        import json as _json
        payload = {"reports": [r.as_dict() for r in reports]}
        if len(reports) == 2:
            payload["drift"] = [
                {"level": f.level, "code": f.code, "message": f.message}
                for f in compare(*reports)
            ]
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for r in reports:
            _print_report(r, show_fix=not a.quiet)
        if len(reports) == 2:
            drift = compare(*reports)
            print("comparison")
            if not drift:
                print("  The two documents agree on structure.")
            for f in drift:
                print(f"  {_ICON[f.level]} [{f.code}] {f.message}")
                if f.detail:
                    print(f"          {f.detail}")

    n_err = sum(len(r.errors) for r in reports)
    n_warn = sum(len(r.warnings) for r in reports)
    if len(reports) == 2:
        d = compare(*reports)
        n_err += sum(1 for f in d if f.level == "error")
        n_warn += sum(1 for f in d if f.level == "warning")
    return 1 if (n_err or (a.strict and n_warn)) else 0


def main(argv=None):
    """CLI entry point. Wraps the real one so the usage nudge cannot change
    the exit status or swallow an exception."""
    try:
        return _main(argv)
    finally:
        from ._nudge import record_run
        record_run()


if __name__ == "__main__":
    sys.exit(main())
