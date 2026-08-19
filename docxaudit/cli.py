"""Command line interface."""

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


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="docxaudit",
        description="Find what a converter silently dropped from a .docx.")
    ap.add_argument("files", nargs="+", metavar="FILE",
                    help="one .docx to audit, or two to compare")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true",
                    help="findings only, no suggested fixes")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on warnings as well as errors")
    a = ap.parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
