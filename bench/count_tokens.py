#!/usr/bin/env python3
"""Compare AI token cost: A4 PDF vs lean PDF vs plain text.
Usage: ANTHROPIC_API_KEY=... [OPENAI_API_KEY=...] python3 bench/count_tokens.py doc.md"""
import base64, json, os, sys, tempfile, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pdf_for_ai import PdfForAI, markdown_to_blocks, find_fonts

def post(url, headers, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {**headers, 'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)

def claude(content, model):
    return post('https://api.anthropic.com/v1/messages/count_tokens',
                {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01'},
                {'model': model, 'messages': [{'role': 'user', 'content': content}]})['input_tokens']

def openai(content, model):
    return post('https://api.openai.com/v1/responses', {'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']},
                {'model': model, 'max_output_tokens': 16, 'input': [{'role': 'user', 'content': content}]})['usage']['input_tokens']

md = open(sys.argv[1], encoding='utf-8').read()
blocks = markdown_to_blocks(md)
text = '\n'.join(t for _, t in blocks)
text_hi = text + '\nhi'
tmp = tempfile.mkdtemp()
pdfs = {}
for layout in ('a4', 'lean'):
    path = os.path.join(tmp, layout + '.pdf')
    n = PdfForAI(*find_fonts(), layout=layout).build(blocks, path)
    pdfs[layout] = (n, base64.b64encode(open(path, 'rb').read()).decode())

if os.environ.get('ANTHROPIC_API_KEY'):
    m = os.environ.get('CLAUDE_MODEL', 'claude-opus-5-5')
    doc = lambda b: [{'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': b}}, {'type': 'text', 'text': 'hi'}]
    print(m)
    for k, (n, b) in pdfs.items():
        print(f'  {k:5} PDF ({n} pages): {claude(doc(b), m):>8,}')
    print(f'  plain text      : {claude(text_hi, m):>8,}')
if os.environ.get('OPENAI_API_KEY'):
    m = os.environ.get('OPENAI_MODEL', 'gpt-5.5')
    doc = lambda b: [{'type': 'input_file', 'filename': 'd.pdf', 'file_data': 'data:application/pdf;base64,' + b}, {'type': 'input_text', 'text': 'hi'}]
    print(m)
    for k, (n, b) in pdfs.items():
        print(f'  {k:5} PDF ({n} pages): {openai(doc(b), m):>8,}')
    plain = [{'type': 'input_text', 'text': text_hi}]
    print(f'  plain text      : {openai(plain, m):>8,}')
