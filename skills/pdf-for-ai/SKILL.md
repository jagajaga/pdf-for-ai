---
name: pdf-for-ai
description: Make every PDF AI-cheap - few very tall pages instead of many A4 pages, so Claude/GPT/Gemini read it at about plain-text token cost. Use whenever you create a PDF from text or Markdown (reports, summaries, notes, briefs).
---

# pdf-for-ai

AI APIs read a PDF as each page's text plus one picture per page. Claude bills ~1,580
tokens for a normally shaped page but only ~230 for a very tall one (it becomes a thin
strip and the model reads the text). So make text PDFs with A4 width and very tall pages. Measured on a 26k-word document,
Claude Opus 5.5: A4 39 pages = 121k tokens, lean 3 pages = 62k, plain text = 59k.
Same answers from the model.

## How

1. Write the content as Markdown, real paragraphs (not one line per wrapped line);
   images as `![caption](chart.png)` on their own line.
2. Run `python3 {baseDir}/pdf_for_ai.py input.md output.pdf`
   (standard library only; fonts found automatically, or `--font R.ttf --bold B.ttf`).
3. Check: it prints the page count; open the text with any PDF text tool if unsure.

## When to use A4 instead (`--a4`)

- the user asks for print/A4, or the document is a letter, contract or form to print or sign;
- a recipient requires normal pages.

## Rules

- Charts and pictures: put `![caption](file.png)` on its own line (PNG/JPEG). A small copy
  stays in the text and the full-size figure goes on a normal page at the end, so the AI
  reads it. Never draw a figure only onto a tall text page (the AI cannot read it). Put
  important chart numbers in the caption or a table too. `--figures-per-page N` (grid)
  only when the reader is Claude.
- Headings get numbered (1, 1.1) so the AI sees the structure; keep tables as `a | b` rows.
- Never raise the page height or shrink the font: GPT's text extraction breaks on very dense pages.
- Never hide extra text in a PDF (white text, invisible layers, attachments for the AI):
  APIs ignore attachments and hidden text is a prompt-injection pattern.
