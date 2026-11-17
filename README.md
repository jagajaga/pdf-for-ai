# pdf-for-ai

**A normal PDF that AI reads at almost plain-text cost.** No new format, no prompt, no plugin.

When you give a PDF to Claude, GPT or Gemini, the API reads the **text of each page plus one image of each page**. The image is billed **per page, whatever the page size** (Claude: about 1,560 tokens a page). So a 76-page report pays for 76 pictures of text it already has.

pdf-for-ai keeps A4 width but puts the text on **a few very tall pages** (up to 14,400 pt, the Acrobat page limit, about 16 A4 pages each). Page 1 stays A4-sized so viewers open a normal window. It is still an ordinary PDF: every viewer opens it, text is real and selectable, nothing is hidden.

## Results

A 26,000-word text document made with `pdf_for_ai.py` both ways, token counts from the providers' own APIs (`bench/count_tokens.py`), 17 Nov 2026:

| Model | A4 PDF (39 pages) | lean PDF (3 pages) | plain text |
|---|---|---|---|
| Claude Opus 5.5 | 121,167 | 61,807 | 58,631 |
| GPT-5.5 | 40,859 | 40,391 | 38,924 |

- **Claude: 2x cheaper** on this dense document, within ~5% of pasting plain text. Each A4 page removed saves about 1,560 tokens, so the less text per page, the bigger the saving: a typical PDF page is ~2,400 tokens uploaded vs ~900 as text ([FileConcat, 195 PDFs](https://fileconcat.com/blog/how-many-tokens-is-a-pdf-in-claude)), which is ~2.7x.
- **GPT-5.5**: page images are nearly free already, so lean is never worse.
- **Gemini** (from Google's docs, not measured): PDF text is free and each page costs 258-560 tokens, so fewer pages is the whole bill.
- **Same answers.** With no special prompt, Claude Opus 5.5 and GPT-5.5 answered the same content questions correctly from the lean and the A4 file.

## Use

```
python3 pdf_for_ai.py notes.md notes.pdf          # lean (default)
python3 pdf_for_ai.py notes.md notes-print.pdf --a4   # classic A4 for printing
```

Python 3.8+, standard library only. Needs a TrueType font pair; Liberation/DejaVu (Linux), Arial (macOS, Windows) are found automatically, or pass `--font Regular.ttf --bold Bold.ttf`. Any script the font covers works (Latin, Cyrillic, Greek...). Reads headings, paragraphs, bullet and numbered lists, quotes, code blocks and tables (tables become text rows).

As a library:

```python
from pdf_for_ai import PdfForAI, markdown_to_blocks, find_fonts
PdfForAI(*find_fonts()).build(markdown_to_blocks(md), "out.pdf")
```

**For AI agents:** `skills/pdf-for-ai/SKILL.md` is a ready skill (Claude Code, OpenClaw, Codex and other Agent Skills tools): the agent then makes every PDF lean.

## Measure it yourself

```
ANTHROPIC_API_KEY=... python3 bench/count_tokens.py notes.md
```
builds A4 and lean versions and prints Claude's token count for each and for the plain text (the count_tokens endpoint is free). Set `OPENAI_API_KEY` to add GPT (that one is a real request of a few cents).

## When not to use it

- **Printing or signing** (letters, contracts, forms): use `--a4`. A tall page does not fit on paper.
- **Charts and pictures the AI must see:** on a tall page the page image is shrunk to a thin strip, so the AI reads the text but not the figure. Keep figures on normal-size pages. (pdf-for-ai itself makes text documents.)
- Chat apps (ChatGPT, claude.ai, Gemini app) may process uploads differently from the APIs; the numbers above are API numbers.

## Why not hide a Markdown copy inside the PDF?

We tried: an attached `content.md` (PDF Associated Files). Claude never saw it, because the APIs read only page text and page images. Hidden text in PDFs is also a known prompt-injection trick. pdf-for-ai shows the AI exactly what a person sees.

## Prior art (as far as we found)

- Several people measured that the page image cost is flat per page, e.g. [Carlos Aragon](https://www.carlosaragon.online/blog/claude-pdf-token-cost-per-page) (Letter to Tabloid size, about 1,560 tokens each) and [FileConcat](https://fileconcat.com/blog/how-many-tokens-is-a-pdf-in-claude) (195 PDFs).
- "Combine pages into one long page" tools exist for reading on the web.
- [Optical context compression](https://www.christopherboebel.com/en/notes/optical-context-compression) packs several scanned pages into one image for vision models.
- New formats: [DocLang](https://www.linuxfoundation.org/press/lf-ai-data-foundation-launches-doclang-specification-working-group-to-advance-an-open-standard-for-ai-native-documents) (LF AI & Data), [.rec](https://recformat.com/) (needs a spec in the prompt).

We found nobody making ordinary PDFs with few tall pages to cut AI cost. If you know of one, open an issue.

## License

MIT
