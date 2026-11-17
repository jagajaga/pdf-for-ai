# Post drafts

## X / Threads (short)

PDFs cost AI 3x more than the same text. Not because of the text: Claude bills an image of every page, ~1,560 tokens each, whatever the page size.

So: same PDF, A4 width, a few very tall pages.

26k-word doc on Claude Opus 5.5:
A4, 83 pages: 191k tokens
Tall, 5 pages: 62k
Plain text: 61k

Still a normal PDF. Same answers. No prompt, no plugin.
Open source, one Python file: github.com/jagajaga/lean-pdf

## LinkedIn / Telegram (longer)

Your PDF costs AI three times what its text does.

When you send a PDF to Claude, GPT or Gemini, the API reads two things: the text of each page and a picture of each page. The picture is billed per page, and its price does not depend on the page size: on Claude it is about 1,560 tokens per page. A 76-page report pays for 76 pictures of text the model already has.

So I made the pages fewer instead of the text shorter. lean-pdf keeps A4 width and puts the text on very tall pages, about 16 A4 pages each. The first page stays A4 so it opens normally. It is an ordinary PDF: real text, opens anywhere, nothing hidden.

Results on a 26,000-word document, measured with the providers' own token counters:
• Claude Opus 5.5: 191k tokens as A4, 62k as lean, 61k as plain text. 3x cheaper.
• GPT-5.5: already cheap per page, lean is never worse.
• Gemini bills per page and gives PDF text for free, so fewer pages is the whole bill.
Both Claude and GPT answered the same questions correctly from either file.

I first tried hiding a Markdown copy inside the PDF. The AI never saw it: the APIs read only page text and page images. So the fix had to be in what the AI already reads.

As far as I could find, nobody does this yet: people measured that page size does not change the price, and new AI formats are being proposed (DocLang, .rec), but those need new readers or prompts.

One Python file, no dependencies, plus a skill so your AI agent makes every PDF this way: github.com/jagajaga/lean-pdf

Not for printing (use --a4) or for charts the AI must see.
