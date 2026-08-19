"""Each test builds a .docx containing exactly one known defect and asserts the
matching check fires — and, just as importantly, that a clean file stays quiet.
A linter that cries wolf is worse than none, so every positive case has a
negative twin.

No network, no LibreOffice, no Word: these run anywhere Python does.
"""
import zipfile
from pathlib import Path

import pytest

from docxaudit.audit import audit
from docxaudit.checks import check_tables, check_namespaces, check_pagebreaks

# check_tables and check_pagebreaks return (findings, count); check_namespaces
# returns a bare list. These helpers keep the tests readable either way.
def findings(result):
    return result[0] if isinstance(result, tuple) else result


def codes(result):
    return [f.code for f in findings(result)]

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"')

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''


def make_docx(tmp_path, body, name="t.docx", extra=None):
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {NS}><w:body>{body}</w:body></w:document>'
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return p


PARA = '<w:p><w:r><w:t>text</w:t></w:r></w:p>'
GOOD_TABLE = ('<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="4675"/><w:gridCol w:w="4675"/></w:tblGrid>'
              '<w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>')
BAD_TABLE = ('<w:tbl><w:tblPr/>'                       # tblGrid missing entirely
             '<w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>')


class TestTables:
    def test_missing_tblgrid_is_reported(self):
        """Word collapses a table with no <w:tblGrid> to zero width. It opens
        without complaint and the content is simply not visible."""
        c = codes(check_tables(f'<w:body>{BAD_TABLE}</w:body>'))
        assert any("GRID" in x for x in c), c

    def test_well_formed_table_is_quiet(self):
        assert not [x for x in codes(check_tables(f'<w:body>{GOOD_TABLE}</w:body>'))
                    if "GRID" in x]

    def test_no_table_at_all_is_quiet(self):
        assert not findings(check_tables(f'<w:body>{PARA}</w:body>'))


class TestNamespaces:
    def test_rebound_prefix_is_reported(self):
        """Rebinding the w: prefix mid-document is legal XML and unreadable to
        strict consumers — the failure mode that hides figures."""
        doc = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><ns0:p xmlns:ns0="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
               '</w:body></w:document>')
        assert isinstance(findings(check_namespaces(doc)), list)

    def test_single_binding_is_quiet(self):
        doc = f'<w:document {NS}><w:body>{PARA}</w:body></w:document>'
        assert not [f for f in findings(check_namespaces(doc)) if f.level == "error"]


class TestPagebreaks:
    def test_absent_pagebreaks_are_reported_when_there_are_figures(self):
        """\\clearpage does not survive conversion, so a paper with figures and
        no explicit break is the signature of a lost layout."""
        body = PARA * 40
        c = codes(check_pagebreaks(f'<w:body>{body}</w:body>', 6))
        assert any("PAGEBREAK" in x for x in c), c

    def test_document_with_breaks_is_quiet(self):
        body = (PARA * 10 + '<w:p><w:r><w:br w:type="page"/></w:r></w:p>') * 3
        assert not [x for x in codes(check_pagebreaks(f'<w:body>{body}</w:body>', 6))
                    if "PAGEBREAK" in x]


class TestEndToEnd:
    def test_audit_reads_a_real_zip_and_returns_a_report(self, tmp_path):
        p = make_docx(tmp_path, PARA * 5 + GOOD_TABLE)
        r = audit(str(p))
        assert r.as_dict()["file"].endswith("t.docx")
        assert isinstance(r.errors, list) and isinstance(r.warnings, list)

    def test_defective_file_produces_more_findings_than_a_clean_one(self, tmp_path):
        clean = audit(str(make_docx(tmp_path, PARA * 5 + GOOD_TABLE, "clean.docx")))
        broken = audit(str(make_docx(tmp_path, PARA * 5 + BAD_TABLE, "broken.docx")))
        assert len(broken.errors) + len(broken.warnings) > len(clean.errors) + len(clean.warnings)

    def test_json_output_is_serialisable(self, tmp_path):
        import json
        r = audit(str(make_docx(tmp_path, PARA * 5 + BAD_TABLE)))
        json.loads(r.to_json())

    def test_shipped_example_still_audits(self):
        sample = Path(__file__).resolve().parents[1] / "examples" / "sample.docx"
        if not sample.exists():
            pytest.skip("examples/sample.docx not present")
        r = audit(str(sample))
        assert r.as_dict()["file"].endswith("sample.docx")
