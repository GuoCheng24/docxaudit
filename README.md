# docxaudit

**Find what your converter silently dropped from a `.docx`.** Zero dependencies.

Pandoc — or any LaTeX/Markdown → Word pipeline — reports success and still loses things. A table disappears. Figures render in desktop Word but not in Word for the web. A supplement that is 11 pages as PDF arrives as 17 pages as `.docx`, and the editor counts the `.docx`.

None of that shows up as an error. You find out from a reviewer.

```console
$ docxaudit paper.docx
paper.docx
  152 paragraphs · 3 tables · 6 images (6 referenced) · 14 equations (4 display) · 0 page breaks

  ERROR   [NS_GENERATED] auto-generated namespace prefixes (ns2:, ns3:, ...) present
          figures and equations will not render in strict viewers
          fix: Register all prefixes before serialising - registering only 'w'
               is the usual cause.

  ERROR   [TBL_NO_GRID] table 2 has no <w:tblGrid>
          columns collapse; the reader has to AutoFit by hand

  WARN    [NO_PAGEBREAKS] 6 figures but no page breaks at all
          if the PDF puts one figure per page, the .docx will not match
```

## Why the usual checks miss these

**`python-docx` cannot see them.** It reads paragraph text, so equations (OMML) and anything the converter dropped are simply absent from what you inspect. "The text looks fine" is not evidence.

**A LibreOffice preview misleads in both directions.** It invents ugly font substitutions that real Word does not have — so you waste time fixing cosmetics that were never broken — and it is forgiving enough to render documents that stricter viewers refuse. The namespace bug above renders perfectly in LibreOffice *and* in desktop Word, and shows nothing in Word for the web.

**An AI assistant reading the file cannot check this either.** These are structural properties of the OOXML, not something visible in extracted text.

`docxaudit` reads the raw XML and checks the specific things that ship unnoticed.

## Install

```bash
pip install docxaudit
```

Standard library only. Nothing to break, nothing to audit.

## What it checks

Every check corresponds to a failure that actually reached a submission.

| code | what goes wrong |
|---|---|
| `NS_PREFIX` / `NS_GENERATED` | Post-processing re-serialised the XML and rebound namespaces to `ns2:`/`ns3:`. Word resolves by URI so it looks fine; **strict viewers show neither figures nor equations.** |
| `TBL_NO_GRID` | Table has no `<w:tblGrid>` — columns collapse to a sliver in Word. Common when tables come from LaTeX booktabs. |
| `TBL_ZERO_WIDTH` | Table declares width 0. |
| `IMG_ORPHAN` | Images embedded in the archive with no `<w:drawing>` referencing them — the anchors were dropped. |
| `NO_PAGEBREAKS` | `\clearpage` does not survive conversion, so one-figure-per-page silently becomes a different page count. |
| `MATH_INLINE` | Inline maths converts least reliably; complex expressions arrive mangled. |
| `FONT_MISMATCH` | Theme heading font disagrees with the body default — sans-serif headings over serif text. |
| `FONT_EA_EMPTY` | Theme East Asian font is empty, so CJK headings fall back and stop matching the body. |
| `HEADING_COLOUR` | Headings still carry the default template's blue, while the PDF renders them black. |
| `DUP_PREFIX` | `Figure Figure 1` — the source wrote a prefix and the converter added its own. |
| `EMPTY_HEADING` | A heading whose text did not survive. |

## Compare two outputs

Give it two files and it reports structural drift — useful for the PDF-side and Word-side versions of one manuscript, or for before/after a post-processing step:

```console
$ docxaudit before.docx after.docx
comparison
  WARN    [DRIFT_PARAGRAPHS] paragraphs: 42 in before.docx vs 36 in after.docx
  ERROR   [DRIFT_TEXT] text length differs by 11%
```

## In CI

Exit code is 1 when there are errors, or with `--strict` when there are warnings too:

```yaml
- run: pip install docxaudit
- run: docxaudit build/paper.docx --strict
```

## As a library

```python
from docxaudit import audit

report = audit("paper.docx")
print(report.stats)                      # counts you can assert on
for f in report.errors:
    print(f.code, f.message, f.fix)
```

`--json` gives the same structure on the command line.

## Scope

It checks **structure**, not typography. It will not tell you a figure is ugly or a caption reads badly — for that, render the document and look at it. What it does is catch the class of problem that renders fine everywhere you happen to look, and breaks somewhere you do not.

## License

MIT © Guo Cheng
