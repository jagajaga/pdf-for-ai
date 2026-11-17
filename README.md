# pdf-for-ai

**A normal PDF that AI reads at almost plain-text cost.** No new format, no prompt, no plugin.

When you give a PDF to Claude, GPT or Gemini, the API reads the **text of each page plus one picture of each page**. On Claude that picture costs about **1,580 tokens for any normally shaped page**, so a 76-page report pays for 76 pictures of text it already has.

pdf-for-ai keeps A4 width but puts the text on **a few very tall pages** (up to 14,400 pt, the Acrobat page limit, about 16 A4 pages each). A very tall page is shrunk to a thin strip before the model sees it, and Claude bills that strip at only ~200 tokens; the model reads the text instead. Page 1 stays A4-sized so viewers open a normal window. It is still an ordinary PDF: every viewer opens it, text is real and selectable, nothing is hidden.

### What a page picture costs (Claude Opus 5.5, measured)

| Page shape (pt) | tokens |
|---|---|
| anything up to about 2:1 (A4, square, Letter...) | ~1,580 |
| 595 x 4,000 | ~566 |
| 595 x 14,400 (a pdf-for-ai page) | ~230 |

Only the ratio matters, not the size: about 3,280 x (short side / long side) once a page is taller than ~2:1. All current Claude models (Opus, Sonnet, Haiku 5.5, Fable 5.2) count the same.

## Results

Two text documents, each made with `pdf_for_ai.py` as A4 and as tall pages; input tokens from the providers' own counters (Anthropic `count_tokens`, OpenAI `responses/input_tokens`), 17 Nov 2026.

**26,000 words** (A4: 39 pages, tall: 3 pages)

| Model | A4 PDF | tall PDF | plain text |
|---|---|---|---|
| Claude Opus 5.5, Sonnet 5.5, Haiku 5.5, Fable 5.2 | 121,167 | 61,807 | 58,631 |
| GPT-6.2 Astra, 6.2 Sol, 6.1, 6, 5.6, 5.5 | 40,859 | 40,391 | 38,924 |

**6,500 words** (A4: 6 pages, tall: 2 pages)

| Model | A4 PDF | tall PDF | plain text |
|---|---|---|---|
| Claude (all four above) | 19,730 | 12,395 | 10,012 |
| GPT (all four above) | 7,027 | 6,975 | 6,633 |

- **Claude: 1.6-2x cheaper.** Almost all of what's left over plain text is the A4 first page (~1,580) and line breaks (~0.8 token per printed line).
- **GPT: about the same either way.** GPT makes no picture of a text-only page (about 16 tokens per page); only pages with a bitmap get one (GPT-5.5: ~335 tokens at the default `detail`; GPT-5.6 and GPT-6 use high detail by default, ~1,000 per figure page). GPT's tokenizer also needs ~35% fewer tokens for the same text.
- **Gemini** (from Google's docs, not measured): each page costs 280, 560 (default) or 1,120 tokens by `media_resolution`, plus the text.
- **Same answers.** With no special prompt, Claude Opus 5.5 and GPT-5.5 answered the same content questions correctly from the tall and the A4 file.
- The less text per page, the bigger the saving: a typical PDF page is ~2,400 tokens uploaded vs ~900 as text ([FileConcat, 195 PDFs](https://fileconcat.com/blog/how-many-tokens-is-a-pdf-in-claude)).

## One scale for every model

Tokens are not comparable between providers (GPT's tokenizer packs ~4.3 English characters into a token, Claude's ~2.8), so here is the same 200,000-character document on two common scales. English: the "Attention" paper repeated; Russian: the Wikipedia article "История России". Counted 17 Nov 2026; a real paid Claude Opus 5.5 call billed exactly the counted tokens (79,512 + 21 for the question).

**Cost relative to sending the plain text (1.00 = same as text)**

| Provider | Language | A4 PDF | pdf-for-ai |
|---|---|---|---|
| Claude (all 4 models) | English | 2.23 | **1.05** |
| Claude | Russian | 2.10 | **1.06** |
| GPT (GPT-6.2 Astra/Sol, 6.1, 6, 5.6, 5.5: all count identically) | English | 1.05 | 1.04 |
| GPT | Russian | 1.08 | 1.07 |

**Dollars per document (input only, list prices on 17 Nov 2026)**

| Model | $/M input | A4 PDF | pdf-for-ai | plain text |
|---|---|---|---|---|
| Claude Fable 5.2 | 8 | $1.27 | $0.60 | $0.57 |
| Claude Opus 5.5 | 4 | $0.64 | $0.30 | $0.29 |
| Claude Sonnet 5.5 | 2 | $0.32 | $0.15 | $0.14 |
| Claude Haiku 5.5 | 0.10 / 0.50 over 100k | $0.080 | $0.007 | $0.007 |
| GPT-6.2 Astra | 8 | $0.39 | $0.39 | $0.37 |
| GPT-6.2 Sol | 2 | $0.098 | $0.096 | $0.093 |
| GPT-6.1 Terra | 1 | $0.049 | $0.048 | $0.046 |
| GPT-6 Luna | 0.10 | $0.0049 | $0.0048 | $0.0046 |

(English shown; Russian is within ~10%.) On Claude Haiku 5.5 the A4 PDF crosses the 100k-token price step, so it costs 11x the pdf-for-ai file. On GPT the layout barely matters for text: GPT makes no picture of text-only pages (GPT-6 included).

## Use

```
python3 pdf_for_ai.py notes.md notes.pdf          # lean (default)
python3 pdf_for_ai.py notes.md notes-print.pdf --a4   # classic A4 for printing
```

Python 3.8+, standard library only. Needs a TrueType font pair; Liberation/DejaVu (Linux), Arial (macOS, Windows) are found automatically, or pass `--font Regular.ttf --bold Bold.ttf`. Any script the font covers works (Latin, Cyrillic, Greek...). Reads headings, paragraphs, bullet and numbered lists, quotes, code blocks, tables (as text rows) and images (see below). PNG transparency is flattened onto white.

As a library:

```python
from pdf_for_ai import PdfForAI, markdown_to_blocks, find_fonts
PdfForAI(*find_fonts()).build(markdown_to_blocks(md), "out.pdf")
```

**For AI agents:** `skills/pdf-for-ai/SKILL.md` is a ready skill (Claude Code, OpenClaw, Codex and other Agent Skills tools): the agent then makes every PDF lean.

## Charts and pictures

Put an image on its own line: `![Figure 1: Revenue by month](chart.png)` (PNG or JPEG, path relative to the Markdown file). pdf-for-ai puts the **full-size figure on a normal-size page at the end** with its caption, and leaves a visible line in the text: `[Figure 1: Revenue by month: full-size figure at the end of the document]`. The AI reads the figure at full resolution and the text stays in one piece. `--inline-copies` also draws a small copy in the text for people.

6,500 words with 3 bar charts whose values exist only in the pictures (input tokens; "correct" = all six values of Figure 2 right, real calls):

| Layout | Claude Opus 5.5 | GPT-5.5 | GPT-6.2 Astra |
|---|---|---|---|
| **default (v0.3.1): figures at the end** | 17,211, correct | 8,058, correct | 10,009 |
| `--inline-copies` | 17,083, correct | 8,954, correct | 12,626 |
| `--figures-per-page 3` | 13,951, correct | 8,290 | |
| v0.2: figure pages where they occur | 21,701 | 7,997 | |
| A4 | | | 13,603 |
| chart drawn on a tall text page | "can't read it" | wrong numbers | |

- Small copies in the text cost GPT-6 26% more (a tall page holding bitmaps gets a high-detail page image), so they are off by default.
- GPT-6 answers were not tested: this API key can count GPT-6 tokens but not run GPT-6.
- **Grids are for Claude only.** Claude read 18 of 18 values from 8 charts on one page; GPT-5.5 at default detail misread a 3-chart grid.
- **Put the numbers in text too** if they matter: a short data line or pipe table under the caption reaches every model and every text-only pipeline.

## Headings, tables and dense pages

- **Headings are numbered (1, 1.1, 1.1.1)** unless your source already numbers them (`--no-numbers` turns it off; a single top heading counts as the title). Models get headings as plain lines with no font size or bold, so "Hiring" and a sub-section "Hiring" look the same. Listing the level-2 headings of a test document: bold only 1 of 4 models right, numbered 4 of 4 (Claude Opus 5.5, Haiku 5.5, GPT-5.5, GPT-5.4 mini). About 1 token per heading.
- **Tables stay as `a | b | c` rows.** With aligned columns instead, Claude Opus 5.5 refused ("the extracted text drops their positions") and Haiku 5.5 answered wrong; with pipes 3 of 4 models got 5 of 5.
- **Density guard.** On very text-dense pages GPT's text extraction starts dropping thin letters ("A en on V sua za ons" for "Attention Visualizations"); with normal prose this began after ~18,000 pt of 10.5 pt text, and sooner with small type. pdf-for-ai counts narrow glyphs and starts a new page at 35,000 (normal prose fills ~30,000 per page, so it rarely triggers). **Don't raise the page limit or shrink the font.**
- **Only visible text reaches the models.** Tags, bookmarks, Title/XMP metadata, alt text, link targets, notes and attachments added 0 tokens on both Claude and GPT.

## Measure it yourself

```
ANTHROPIC_API_KEY=... python3 bench/count_tokens.py notes.md
```
builds A4 and lean versions and prints Claude's token count for each and for the plain text. Set `OPENAI_API_KEY` to add GPT. Both use the providers' free token counters, which match the billed tokens. `bench/all_models.py doc.md` does the same for all current Claude and GPT models.

## When not to use it

- **Printing or signing** (letters, contracts, forms): use `--a4`. A tall page does not fit on paper.
- Chat apps (ChatGPT, claude.ai, Gemini app) may process uploads differently from the APIs; the numbers above are API numbers.

## Why not hide a Markdown copy inside the PDF?

We tried: an attached `content.md` (PDF Associated Files). Claude never saw it, because the APIs read only page text and page images. Hidden text in PDFs is also a known prompt-injection trick. pdf-for-ai shows the AI exactly what a person sees.

## Prior art (as far as we found)

- Several people measured that the page image cost does not grow with page size, e.g. [Carlos Aragon](https://www.carlosaragon.online/blog/claude-pdf-token-cost-per-page) (Letter to Tabloid size, about 1,560 tokens each) and [FileConcat](https://fileconcat.com/blog/how-many-tokens-is-a-pdf-in-claude) (195 PDFs).
- "Combine pages into one long page" tools exist for reading on the web.
- [Optical context compression](https://www.christopherboebel.com/en/notes/optical-context-compression) packs several scanned pages into one image for vision models.
- New formats: [DocLang](https://www.linuxfoundation.org/press/lf-ai-data-foundation-launches-doclang-specification-working-group-to-advance-an-open-standard-for-ai-native-documents) (LF AI & Data), [.rec](https://recformat.com/) (needs a spec in the prompt).

We found nobody making ordinary PDFs with few tall pages to cut AI cost. If you know of one, open an issue.

## License

MIT
