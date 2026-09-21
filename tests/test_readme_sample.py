"""The console block in the README is held to the audit it claims to be.

The page shows `docxaudit examples/sample.docx` and says the output is real. It
is, trimmed: the INFO line and the fix text under the warnings are left out to
keep the block short. Until now nothing checked the part that is shown -- the
header counts and the four findings -- so the file could be rebuilt, or a check
renamed, and the page would go on quoting an audit that no longer happens.
"""
import re
from pathlib import Path

import pytest

from docxaudit import audit

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "sample.docx"


def _readme_block():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"```console\n\$ docxaudit examples/sample\.docx\n(.*?)```", text, re.S)
    assert m, "the README no longer shows the sample audit"
    return m.group(1)


@pytest.mark.skipif(not SAMPLE.exists(), reason="examples/sample.docx not present")
def test_readme_sample_block_matches_the_audit():
    block = _readme_block()
    r = audit(str(SAMPLE)).as_dict()
    s = r["stats"]

    header = re.search(r"(\d+) paragraphs · (\d+) tables · (\d+) images \((\d+) referenced\) · "
                       r"(\d+) equations \((\d+) display\) · (\d+) page breaks", block)
    assert header, "the header line is missing from the README block"
    shown = tuple(int(x) for x in header.groups())
    real = (s["paragraphs"], s["tables"], s["images"], s["drawings"],
            s["equations"], s["display_equations"], s["page_breaks"])
    assert shown == real, f"README header {shown} vs audit {real}"

    shown_findings = re.findall(r"^\s+(ERROR|WARN)\s+\[([A-Z_]+)\]", block, re.M)
    real_findings = [(f["level"].upper().replace("WARNING", "WARN"), f["code"])
                     for f in r["findings"] if f["level"] in ("error", "warn", "warning")]
    assert shown_findings == real_findings, (
        f"README shows {shown_findings}, the audit produces {real_findings}")

    # what the page leaves out must be said, not silently dropped
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "trimmed" in readme.split("That output is real")[1][:200], (
        "the README calls the block real without saying it is trimmed")
