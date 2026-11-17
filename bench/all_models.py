#!/usr/bin/env python3
"""Token counts for A4 vs tall PDF vs text on current Claude and GPT models (free counting endpoints).
Usage: ANTHROPIC_API_KEY=... OPENAI_API_KEY=... python3 bench/all_models.py doc1.md [doc2.md ...]"""
import base64, json, os, sys, tempfile, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pdf_for_ai import PdfForAI, markdown_to_blocks, find_fonts, blocks_text
def post(url, h, b):
    req=urllib.request.Request(url, json.dumps(b).encode(), {**h,'content-type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r: return json.load(r)
    except urllib.error.HTTPError as e: return {'error': e.read().decode()[:200]}
AK={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01'}
OK={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']}
def claude(m, c):
    j=post('https://api.anthropic.com/v1/messages/count_tokens',AK,{'model':m,'messages':[{'role':'user','content':c}]}); return j.get('input_tokens', j)
def oai(m, c):
    j=post('https://api.openai.com/v1/responses/input_tokens',OK,{'model':m,'input':[{'role':'user','content':c}]}); return j.get('input_tokens', j)
docs={os.path.basename(p): p for p in sys.argv[1:]}
CL=['claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5','claude-fable-5-2']
OA=['gpt-6.2-astra','gpt-6.2-sol','gpt-6.1-terra','gpt-6-luna','gpt-5.5']
out=[]
for dn, path in docs.items():
    blocks=markdown_to_blocks(open(path,encoding='utf-8').read()); text='\n'.join(t for _,t in blocks)+'\nhi'
    tmp=tempfile.mkdtemp(); p={}
    for lay in ('a4','lean'):
        f=os.path.join(tmp,lay+'.pdf'); n=PdfForAI(*find_fonts(),layout=lay).build(blocks,f); p[lay]=(n,base64.b64encode(open(f,'rb').read()).decode())
    for m in CL:
        d=lambda b:[{'type':'document','source':{'type':'base64','media_type':'application/pdf','data':b}},{'type':'text','text':'hi'}]
        out.append([dn,m,p['a4'][0],claude(m,d(p['a4'][1])),p['lean'][0],claude(m,d(p['lean'][1])),claude(m,text)])
        print(out[-1], flush=True)
    for m in OA:
        d=lambda b:[{'type':'input_file','filename':'d.pdf','file_data':'data:application/pdf;base64,'+b},{'type':'input_text','text':'hi'}]
        out.append([dn,m,p['a4'][0],oai(m,d(p['a4'][1])),p['lean'][0],oai(m,d(p['lean'][1])),oai(m,[{'type':'input_text','text':text}])])
        print(out[-1], flush=True)

