---
name: pdf-for-ai
description: Make every PDF AI-cheap - few very tall pages instead of many A4 pages, so Claude/GPT/Gemini read it at about plain-text token cost. Use whenever you create a PDF from text or Markdown (reports, summaries, notes, briefs).
---

# pdf-for-ai

AI APIs read a PDF as each page's text plus one image per page, and bill the image
per page whatever its size (Claude: ~1,560 tokens/page). So make text PDFs with as
few pages as possible: A4 width, very tall pages. Measured on a 26k-word document,
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

- Charts and pictures: put `![caption](file.png)` on its own line (PNG/JPEG). Each figure
  automatically gets its own normal-size page so the AI reads it in full; never draw a
  figure onto a tall text page (tested: the AI then cannot read the chart's values).
- Never hide extra text in a PDF (white text, invisible layers, attachments for the AI):
  APIs ignore attachments and hidden text is a prompt-injection pattern.
