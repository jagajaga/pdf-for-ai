#!/usr/bin/env python3
"""pdf-for-ai: Markdown -> a normal PDF that AI models read at almost plain-text cost.

Why: AI APIs (Claude, Gemini, OpenAI) read a PDF as the extracted text of each page
PLUS one image of each page, and the image is billed per page whatever the page size
(Claude: ~1,600 tokens/page). So pdf-for-ai keeps A4 width but puts the text on a few
very tall pages (up to 14,400 pt, the Acrobat limit). Page 1 stays A4-sized so
viewers open a normal window. Real embedded text, nothing hidden.

Standard library only. Needs one TrueType (.ttf) font pair on disk; found
automatically on Linux, macOS and Windows, or pass --font/--bold.

  python3 pdf_for_ai.py input.md output.pdf          # lean (default)
  python3 pdf_for_ai.py input.md output.pdf --a4     # classic A4, for print

Images: put ![caption](chart.png) on its own line (PNG or JPEG). A small copy stays
in the text; the full-size figure goes on a normal-size page at the end, so the AI
sees it at full resolution and the text stays in one cheap piece.
Headings are numbered (1, 1.1) unless the source already numbers them: the AI gets
headings as plain lines, and numbers keep the levels visible.

License: MIT. https://github.com/jagajaga/pdf-for-ai
"""
import argparse, os, re, struct, sys, zlib

__version__ = "0.3.0"

FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf",
     "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"),
]

A4_W, A4_H = 595.28, 841.89
LEAN_PAGE_H = 14400  # largest page side Acrobat and most viewers accept (200 in)


def parse_ttf(path):
    """Parse the minimum TTF tables needed for PDF embedding: cmap (Unicode -> glyph
    id), hmtx (glyph advance widths), head/hhea/maxp (units-per-em, counts).
    Returns a dict consumed by FullPDF. No external font library needed - this reads
    the TrueType binary format directly via struct."""
    with open(path, 'rb') as f:
        data = f.read()
    num_tables = struct.unpack('>H', data[4:6])[0]
    tables = {}
    offset = 12
    for i in range(num_tables):
        tag = data[offset:offset+4].decode('ascii')
        tbl_offset = struct.unpack('>I', data[offset+8:offset+12])[0]
        tables[tag] = tbl_offset
        offset += 16
    head_off = tables['head']
    units_per_em = struct.unpack('>H', data[head_off+18:head_off+20])[0]
    hhea_off = tables['hhea']
    num_h_metrics = struct.unpack('>H', data[hhea_off+34:hhea_off+36])[0]
    maxp_off = tables['maxp']
    num_glyphs = struct.unpack('>H', data[maxp_off+4:maxp_off+6])[0]
    hmtx_off = tables['hmtx']
    widths = []
    for i in range(num_h_metrics):
        aw = struct.unpack('>H', data[hmtx_off+i*4:hmtx_off+i*4+2])[0]
        widths.append(aw)
    last_width = widths[-1] if widths else 0
    while len(widths) < num_glyphs:
        widths.append(last_width)

    # cmap: prefer format 12 (full Unicode) over format 4 (BMP only)
    cmap_off = tables['cmap']
    n_subtables = struct.unpack('>H', data[cmap_off+2:cmap_off+4])[0]
    best_subtable_off = None
    best_format = None
    for i in range(n_subtables):
        rec_off = cmap_off + 4 + i*8
        plat_id, enc_id = struct.unpack('>HH', data[rec_off:rec_off+4])
        sub_off = struct.unpack('>I', data[rec_off+4:rec_off+8])[0]
        fmt = struct.unpack('>H', data[cmap_off+sub_off:cmap_off+sub_off+2])[0]
        if (plat_id == 3 and enc_id == 10) or (plat_id == 0 and enc_id >= 4):
            if fmt == 12:
                best_subtable_off = cmap_off + sub_off; best_format = 12
        if best_format != 12 and ((plat_id == 3 and enc_id == 1) or (plat_id == 0)):
            if fmt == 4:
                best_subtable_off = cmap_off + sub_off; best_format = 4

    unicode_to_gid = {}
    if best_format == 4:
        off = best_subtable_off
        seg_count_x2 = struct.unpack('>H', data[off+6:off+8])[0]
        seg_count = seg_count_x2 // 2
        end_codes_off = off + 14
        start_codes_off = end_codes_off + seg_count_x2 + 2
        id_delta_off = start_codes_off + seg_count_x2
        id_range_off = id_delta_off + seg_count_x2
        for s in range(seg_count):
            end_code = struct.unpack('>H', data[end_codes_off+s*2:end_codes_off+s*2+2])[0]
            start_code = struct.unpack('>H', data[start_codes_off+s*2:start_codes_off+s*2+2])[0]
            id_delta = struct.unpack('>h', data[id_delta_off+s*2:id_delta_off+s*2+2])[0]
            id_range_offset = struct.unpack('>H', data[id_range_off+s*2:id_range_off+s*2+2])[0]
            if start_code == 0xFFFF:
                continue
            for c in range(start_code, min(end_code, 0xFFFE)+1):
                if id_range_offset == 0:
                    gid = (c + id_delta) & 0xFFFF
                else:
                    addr = id_range_off + s*2 + id_range_offset + (c - start_code)*2
                    gid = struct.unpack('>H', data[addr:addr+2])[0]
                    if gid != 0:
                        gid = (gid + id_delta) & 0xFFFF
                if gid != 0:
                    unicode_to_gid[c] = gid
    elif best_format == 12:
        off = best_subtable_off
        n_groups = struct.unpack('>I', data[off+12:off+16])[0]
        for g in range(n_groups):
            grp_off = off + 16 + g*12
            start_char, end_char, start_gid = struct.unpack('>III', data[grp_off:grp_off+12])
            for c in range(start_char, end_char+1):
                unicode_to_gid[c] = start_gid + (c - start_char)

    ascender, descender = struct.unpack('>hh', data[hhea_off+4:hhea_off+8])
    return {'data': data, 'ascender': ascender, 'descender': descender, 'units_per_em': units_per_em, 'num_glyphs': num_glyphs,
            'widths': widths, 'unicode_to_gid': unicode_to_gid}



def _tounicode_cmap(font):
    """glyph id -> Unicode, so copy/paste, search and AI text extraction work."""
    g2u = {}
    for cp, gid in sorted(font['unicode_to_gid'].items()):
        if gid and gid not in g2u:
            g2u[gid] = cp
    entries = []
    for gid, cp in sorted(g2u.items()):
        if cp > 0xFFFF:
            c = cp - 0x10000
            u = '%04X%04X' % (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF))
        else:
            u = '%04X' % cp
        entries.append('<%04X> <%s>' % (gid, u))
    parts = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
             "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange"]
    for i in range(0, len(entries), 100):
        chunk = entries[i:i+100]
        parts.append(f"{len(chunk)} beginbfchar")
        parts.extend(chunk)
        parts.append("endbfchar")
    parts += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(parts).encode('ascii')


def _pdf_string(s):
    """UTF-16BE text string for metadata."""
    return '<FEFF' + s.encode('utf-16-be').hex().upper() + '>'


def _png_unfilter(raw, w, h, bpp):
    stride = w * bpp
    out = bytearray(stride * h)
    prev = bytearray(stride)
    pos = 0
    for row in range(h):
        ft = raw[pos]; line = bytearray(raw[pos + 1:pos + 1 + stride]); pos += 1 + stride
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            line = bytearray((x + y) & 255 for x, y in zip(line, prev))
        elif ft == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[row * stride:(row + 1) * stride] = line
        prev = line
    return out


def load_image(path):
    """PNG (8-bit, non-interlaced; transparency is flattened onto white) or JPEG.
    Returns dict(w, h, dict=<PDF stream dict entries>, data=<bytes>)."""
    data = open(path, 'rb').read()
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        pos, idat, plte, trns = 8, bytearray(), None, None
        while pos < len(data):
            ln, typ = struct.unpack('>I4s', data[pos:pos + 8]); body = data[pos + 8:pos + 8 + ln]; pos += 12 + ln
            if typ == b'IHDR':
                w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
            elif typ == b'PLTE':
                plte = body
            elif typ == b'tRNS':
                trns = body
            elif typ == b'IDAT':
                idat += body
        if bd != 8 or il:
            raise ValueError(f"{path}: only 8-bit non-interlaced PNG is supported (re-save it)")
        ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
        if ct in (0, 2) or (ct == 3 and not trns):  # pass the compressed data straight through
            cs = {0: '/DeviceGray', 2: '/DeviceRGB'}.get(ct) or f"[/Indexed /DeviceRGB {len(plte) // 3 - 1} <{plte.hex()}>]"
            return dict(w=w, h=h, data=bytes(idat), dict=f"/ColorSpace {cs} /BitsPerComponent 8 /Filter /FlateDecode "
                        f"/DecodeParms << /Predictor 15 /Colors {ch} /BitsPerComponent 8 /Columns {w} >>")
        px = _png_unfilter(zlib.decompress(bytes(idat)), w, h, ch)
        if ct == 3:  # palette with transparency -> RGB on white
            alpha = list(trns) + [255] * 256
            rgb = bytearray()
            for i in px:
                a = alpha[i]; r, g, b = plte[3 * i:3 * i + 3]
                rgb += bytes(((r * a + 255 * (255 - a)) // 255, (g * a + 255 * (255 - a)) // 255, (b * a + 255 * (255 - a)) // 255))
            out, cs = rgb, '/DeviceRGB'
        else:  # gray+alpha or RGBA -> flatten on white
            n = ch - 1
            out = bytearray()
            for i in range(0, len(px), ch):
                a = px[i + n]
                out += bytes((px[i + k] * a + 255 * (255 - a)) // 255 for k in range(n))
            cs = '/DeviceGray' if n == 1 else '/DeviceRGB'
        return dict(w=w, h=h, data=zlib.compress(bytes(out)), dict=f"/ColorSpace {cs} /BitsPerComponent 8 /Filter /FlateDecode")
    if data[:2] == b'\xff\xd8':
        pos = 2
        while pos < len(data):
            while data[pos] == 0xFF and data[pos + 1] == 0xFF:
                pos += 1
            marker, ln = data[pos + 1], struct.unpack('>H', data[pos + 2:pos + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack('>HH', data[pos + 5:pos + 9]); comps = data[pos + 9]
                cs = {1: '/DeviceGray', 3: '/DeviceRGB', 4: '/DeviceCMYK'}[comps]
                dec = " /Decode [1 0 1 0 1 0 1 0]" if comps == 4 else ""
                return dict(w=w, h=h, data=data, dict=f"/ColorSpace {cs} /BitsPerComponent 8 /Filter /DCTDecode{dec}")
            pos += 2 + ln
        raise ValueError(f"{path}: JPEG size not found")
    raise ValueError(f"{path}: only PNG and JPEG images are supported")


class PdfForAI:
    STYLES = {  # size, bold, gap before, gap after, indent
        'h1': (18, True, 18, 8, 0), 'h2': (14, True, 14, 6, 0), 'h3': (12, True, 10, 4, 0),
        'p': (10.5, False, 0, 6, 0), 'li': (10.5, False, 1, 2, 14), 'pre': (9.5, False, 0, 0, 10),
    }
    CAPTION = 9.5

    THIN_GLYPH_PT = 3.0      # glyphs narrower than this are what GPT's extractor drops
    THIN_GLYPHS_PER_PAGE = 35000  # GPT text got damaged above ~50k on one page; keep margin

    def __init__(self, regular_ttf, bold_ttf, layout='lean', margin=56, leading=1.38,
                 figure_pages=True, figures_per_page=1, number_headings='auto'):
        """figure_pages (lean): a small copy of each figure stays in the text and the full-size
        figure goes on a normal-size page at the end (keeps the text in one cheap piece).
        figures_per_page > 1: grid of figures on each end page (Claude reads it; GPT-5.5 at
        default detail does not). number_headings: 'auto' (number if the source has no numbers),
        True or False; numbers make heading levels visible to AI, which gets headings as plain lines."""
        self.fr, self.fb = parse_ttf(regular_ttf), parse_ttf(bold_ttf)
        self.layout, self.margin, self.leading = layout, margin, leading
        self.figure_pages, self.figures_per_page = figure_pages, max(1, int(figures_per_page))
        self.number_headings = number_headings
        self.width = A4_W

    def page_height(self, i):
        if self.layout == 'a4' or i == 0:
            return A4_H
        return LEAN_PAGE_H

    def text_width(self, text, font, size):
        u2g, w = font['unicode_to_gid'], font['widths']
        total = 0
        for ch in text:
            gid = u2g.get(ord(ch), 0)
            total += w[gid] if gid < len(w) else w[0]
        return total / font['units_per_em'] * size

    def thin_glyphs(self, text, font, size):
        u2g, w, upm = font['unicode_to_gid'], font['widths'], font['units_per_em']
        lim = self.THIN_GLYPH_PT * upm / size
        n = 0
        for ch in text:
            gid = u2g.get(ord(ch), 0)
            if (w[gid] if gid < len(w) else w[0]) < lim:
                n += 1
        return n + 1  # the line break

    def wrap(self, text, font, size, max_w):
        lines, cur = [], ''
        for word in text.split(' '):
            trial = (cur + ' ' + word) if cur else word
            if not cur or self.text_width(trial, font, size) <= max_w:
                cur = trial
            else:
                lines.append(cur); cur = word
        lines.append(cur)
        return lines

    def numbered(self, blocks):
        heads = [(i, k, v) for i, (k, v) in enumerate(blocks) if k in ('h1', 'h2', 'h3')]
        if not heads or self.number_headings is False:
            return blocks
        if self.number_headings == 'auto' and any(re.match(r'^\d+(\.\d+)*[.)]?\s', v) for _, _, v in heads):
            return blocks
        levels = sorted({k for _, k, _ in heads})
        if levels[0] == 'h1' and sum(1 for _, k, _ in heads if k == 'h1') == 1 and heads[0][1] == 'h1':
            levels = levels[1:]  # a single h1 at the top is the title: leave it unnumbered
        if not levels:
            return blocks
        out, counters = list(blocks), [0, 0, 0]
        for i, k, v in heads:
            if k not in levels:
                continue
            d = levels.index(k)
            counters[d] += 1
            for j in range(d + 1, 3):
                counters[j] = 0
            num = '.'.join(str(c) for c in counters[:d + 1])
            out[i] = (k, f"{num}{'.' if d == 0 else ''} {v}")
        return out

    def fit(self, img, max_w, max_h):
        s = min(max_w / img['w'], max_h / img['h'])
        return img['w'] * s, img['h'] * s

    def figure_page(self, figs):
        """One normal-size page with 1..n figures (grid of 2 columns when n > 1)."""
        content_w = self.width - 2 * self.margin
        cols = 1 if len(figs) == 1 else 2
        rows = [figs[i:i + cols] for i in range(0, len(figs), cols)]
        gap = 18
        cell_w = (content_w - gap * (cols - 1)) / cols
        cs = self.CAPTION if cols == 1 else 8
        layout = []
        for row in rows:
            caps = [self.wrap(f['label'], self.fr, cs, cell_w) for f in row]
            cap_h = max(len(c) for c in caps) * cs * self.leading + 8
            max_h = (A4_H - 2 * self.margin) / len(rows) - cap_h - (gap if len(rows) > 1 else 0)
            sizes = [self.fit(f['image'], cell_w, max_h) for f in row]
            layout.append((row, caps, sizes, max(h for _, h in sizes), cap_h))
        ph = round(2 * self.margin + sum(r[3] + r[4] for r in layout) + gap * (len(layout) - 1), 2)
        items, y = [], ph - self.margin
        for row, caps, sizes, row_h, cap_h in layout:
            for c, (f, cap, (w, h)) in enumerate(zip(row, caps, sizes)):
                x0 = self.margin + c * (cell_w + gap)
                items.append(('i', f['image'], x0 + (cell_w - w) / 2, y - h, w, h))
                cy = y - row_h - 8
                for ln in cap:
                    cy -= cs * self.leading
                    items.append(('t', ln, False, cs, x0, cy))
            y -= row_h + cap_h + gap
        return {'h': ph, 'items': items, 'fixed': True, 'thin': 0}

    def layout_blocks(self, blocks):
        """Returns pages: dicts {h, items, fixed}; items are
        ('t', text, bold, size, x, y) and ('i', image, x, y, w, h)."""
        blocks = self.numbered(blocks)
        pages, deferred = [], []
        content_w = self.width - 2 * self.margin
        lean = self.layout == 'lean'
        page = {'h': self.page_height(0), 'items': [], 'fixed': False, 'thin': 0}
        y = page['h'] - self.margin

        def new_page():
            nonlocal y, page
            if page['items']:
                pages.append(page)
            page = {'h': self.page_height(len(pages)), 'items': [], 'fixed': False, 'thin': 0}
            y = page['h'] - self.margin

        def put_lines(lines, bold, size, x, lh):
            nonlocal y
            font = self.fb if bold else self.fr
            for ln in lines:
                thin = self.thin_glyphs(ln, font, size) if lean else 0
                if y - lh < self.margin or (lean and page['thin'] + thin > self.THIN_GLYPHS_PER_PAGE):
                    new_page()
                y -= lh
                page['thin'] += thin
                page['items'].append(('t', ln, bold, size, x, y))

        def put_image(img, w, h, cap_lines):
            nonlocal y
            cap_h = (len(cap_lines) * self.CAPTION * self.leading + 8) if cap_lines else 0
            if y - (h + cap_h + 12) < self.margin and page['items']:
                new_page()
            y -= 6 + h
            page['items'].append(('i', img, self.margin + (content_w - w) / 2, y, w, h))
            y -= 8
            put_lines(cap_lines, False, self.CAPTION, self.margin, self.CAPTION * self.leading)
            y -= 6

        nfig = 0
        for kind, val in blocks:
            if kind == 'img':
                img, nfig = val['image'], nfig + 1
                label = val['alt'] or f"Figure {nfig}"
                if lean and self.figure_pages:
                    deferred.append({'image': img, 'label': label})
                    w, h = self.fit(img, content_w * 0.6, 260)  # small copy for people reading along
                    put_image(img, w, h, self.wrap(f"{label} (full size at the end of the document)",
                                                   self.fr, self.CAPTION, content_w))
                else:
                    cap = self.wrap(label, self.fr, self.CAPTION, content_w) if val['alt'] else []
                    cap_h = (len(cap) * self.CAPTION * self.leading + 8) if cap else 0
                    w, h = self.fit(img, content_w, A4_H - 2 * self.margin - cap_h)
                    put_image(img, w, h, cap)
                continue
            size, bold, gap_b, gap_a, indent = self.STYLES.get(kind, self.STYLES['p'])
            font = self.fb if bold else self.fr
            if kind == 'pre':
                lines = [val] if val else ['']
            else:
                lines = self.wrap(('\u2022 ' if kind == 'li' else '') + val, font, size, content_w - indent)
            lh = size * self.leading
            if y - (gap_b + len(lines) * lh + gap_a) < self.margin and page['items'] and (kind.startswith('h') or len(lines) < 8):
                new_page()  # keep headings and short blocks together
            y -= gap_b
            put_lines(lines, bold, size, self.margin + indent, lh)
            y -= gap_a
        if page['items']:
            pages.append(page)
        n = self.figures_per_page
        for i in range(0, len(deferred), n):
            pages.append(self.figure_page(deferred[i:i + n]))
        return pages

    def build(self, blocks, out_path, title=None):
        pages = self.layout_blocks(blocks)
        objs = [None, None]  # 1 catalog, 2 pages

        def add(o):
            objs.append(o); return len(objs)

        def embed(font, name):
            scale = 1000.0 / font['units_per_em']
            ff = add(('RAW', font['data']))
            tu = add(('Z', zlib.compress(_tounicode_cmap(font))))
            u2g, w = font['unicode_to_gid'], font['widths']
            pairs = sorted(set((g, w[g] if g < len(w) else w[0]) for g in u2g.values()))
            warr = "[" + " ".join(f"{g} [{round(x * scale)}]" for g, x in pairs) + "]"
            asc, desc = round(font['ascender'] * scale), round(font['descender'] * scale)
            fd = add(('D', f"<< /Type /FontDescriptor /FontName /{name} /Flags 32 /FontBBox [-600 {desc} 2000 {asc}] "
                           f"/ItalicAngle 0 /Ascent {asc} /Descent {desc} /CapHeight {asc} /StemV 80 /FontFile2 {ff} 0 R >>"))
            cid = add(('D', f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{name} "
                            f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                            f"/FontDescriptor {fd} 0 R /DW 600 /W {warr} /CIDToGIDMap /Identity >>"))
            return add(('D', f"<< /Type /Font /Subtype /Type0 /BaseFont /{name} /Encoding /Identity-H "
                             f"/DescendantFonts [{cid} 0 R] /ToUnicode {tu} 0 R >>"))

        f1, f2 = embed(self.fr, 'PdfForAIRegular'), embed(self.fb, 'PdfForAIBold')
        img_objs = {}
        kids = []
        for pg in pages:
            top, items = pg['h'], pg['items']
            bottom = 0
            if top > A4_H and not pg['fixed']:  # trim unused space, keep at least an A4-tall page
                low = min(it[5] if it[0] == 't' else it[3] for it in items)
                bottom = min(max(0, int(low - self.margin)), int(top - A4_H))
            ops, xobj = [], []
            for it in items:
                if it[0] == 'i':
                    img, x, y, w, h = it[1:]
                    key = id(img)
                    if key not in img_objs:
                        img_objs[key] = add(('S', f"/Type /XObject /Subtype /Image /Width {img['w']} /Height {img['h']} {img['dict']}", img['data']))
                    name = f"Im{img_objs[key]}"
                    xobj.append(f"/{name} {img_objs[key]} 0 R")
                    ops.append(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /{name} Do Q")
            ops.append("BT")
            for it in items:
                if it[0] == 't':
                    _, text, bold, size, x, y = it
                    font = self.fb if bold else self.fr
                    hexs = ''.join('%04x' % font['unicode_to_gid'].get(ord(c), 0) for c in text)
                    ops += [f"/{'F2' if bold else 'F1'} {size} Tf", f"1 0 0 1 {x:.2f} {y:.2f} Tm", f"<{hexs}> Tj"]
            ops.append("ET")
            content = add(('Z', zlib.compress("\n".join(ops).encode())))
            xres = f" /XObject << {' '.join(sorted(set(xobj)))} >>" if xobj else ""
            kids.append(add(('D', f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >>{xres} >> "
                                  f"/MediaBox [0 {bottom} {self.width} {top}] /Contents {content} 0 R >>")))
        objs[1] = ('D', f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
        objs[0] = ('D', f"<< /Type /Catalog /Pages 2 0 R /OpenAction [{kids[0]} 0 R /FitH null] "
                        f"/PageLayout /OneColumn /PageMode /UseNone >>")
        info = add(('D', f"<< /Producer (pdf-for-ai {__version__})" + (f" /Title {_pdf_string(title)}" if title else "") + " >>"))

        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for n, obj in enumerate(objs, 1):
            offsets.append(len(out))
            kind = obj[0]
            if kind == 'D':
                out += f"{n} 0 obj\n{obj[1]}\nendobj\n".encode()
            elif kind == 'S':
                out += f"{n} 0 obj\n<< /Length {len(obj[2])} {obj[1]} >>\nstream\n".encode() + obj[2] + b"\nendstream\nendobj\n"
            else:
                filt = " /Filter /FlateDecode" if kind == 'Z' else ""
                out += f"{n} 0 obj\n<< /Length {len(obj[1])}{filt} >>\nstream\n".encode() + obj[1] + b"\nendstream\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
        out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        with open(out_path, 'wb') as f:
            f.write(out)
        return len(pages)


def _inline(s):
    s = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'[image: \1]', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', s)
    s = re.sub(r'(\*\*|__)(.+?)\1', r'\2', s)
    s = re.sub(r'(?<![\w*])[*_](?!\s)(.+?)(?<!\s)[*_](?![\w*])', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    return s.replace('\t', '    ')


def blocks_text(blocks):
    """Plain text of the blocks (image captions included), e.g. for token comparisons."""
    return '\n'.join(v['alt'] if k == 'img' else v for k, v in blocks)


def markdown_to_blocks(md, base_dir='.'):
    """Small Markdown reader: headings, paragraphs (soft-wrapped lines are joined),
    bullet and numbered lists, block quotes, code blocks, tables (as text rows), and
    images on their own line: ![caption](chart.png) (PNG or JPEG, path relative to the file)."""
    blocks, para = [], []

    def flush():
        if para:
            blocks.append(('p', _inline(' '.join(para)))); para.clear()

    in_code = False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.lstrip().startswith('```'):
            flush(); in_code = not in_code; continue
        if in_code:
            blocks.append(('pre', line)); continue
        s = line.strip()
        if not s or re.fullmatch(r'<!--.*-->', s):
            flush(); continue
        if re.fullmatch(r'[-*_]{3,}', s):
            flush(); continue
        m = re.fullmatch(r'!\[([^\]]*)\]\(\s*<?([^)>]+?)>?(?:\s+"[^"]*")?\s*\)', s)
        if m:
            flush()
            alt, p = _inline(m.group(1)), m.group(2)
            path = p if os.path.isabs(p) else os.path.join(base_dir, p)
            try:
                blocks.append(('img', {'alt': alt, 'path': path, 'image': load_image(path)}))
            except (OSError, ValueError, KeyError) as e:
                print(f"warning: image skipped: {e}", file=sys.stderr)
                blocks.append(('p', f"[image: {alt}]"))
            continue
        m = re.match(r'^(#{1,6})\s+(.*?)\s*#*$', s)
        if m:
            flush(); blocks.append((('h1', 'h2', 'h3')[min(len(m.group(1)), 3) - 1], _inline(m.group(2)))); continue
        m = re.match(r'^[-*+]\s+(?:\[[ xX]\]\s+)?(.*)', s)
        if m:
            flush(); blocks.append(('li', _inline(m.group(1)))); continue
        m = re.match(r'^(\d+[.)])\s+(.*)', s)
        if m:
            flush(); blocks.append(('p', m.group(1) + ' ' + _inline(m.group(2)))); continue
        if s.startswith('|'):
            flush()
            if re.fullmatch(r'\|?[\s:|-]+\|?', s):
                continue
            blocks.append(('p', '  |  '.join(_inline(c.strip()) for c in s.strip('|').split('|')))); continue
        if s.startswith('>'):
            s = s.lstrip('> ').strip()
        para.append(s)
    flush()
    return blocks


def find_fonts():
    for reg, bold in FONT_CANDIDATES:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold
    return None, None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Markdown -> AI-cheap PDF (few tall pages).")
    ap.add_argument('input', help="Markdown or text file ('-' for stdin)")
    ap.add_argument('output', help="PDF to write")
    ap.add_argument('--a4', action='store_true', help="classic A4 pages (for printing)")
    ap.add_argument('--font', help="regular .ttf font (needs --bold too)")
    ap.add_argument('--bold', help="bold .ttf font")
    ap.add_argument('--title', help="document title (default: first heading)")
    ap.add_argument('--figures-per-page', type=int, default=1, metavar='N',
                    help="figures per end page (grid). >1 is read well by Claude, not by GPT at default detail")
    ap.add_argument('--no-numbers', action='store_true', help="don't number headings")
    a = ap.parse_args(argv)
    md = sys.stdin.read() if a.input == '-' else open(a.input, encoding='utf-8').read()
    reg, bold = (a.font, a.bold or a.font) if a.font else find_fonts()
    if not reg:
        sys.exit("No TrueType font found. Pass --font Regular.ttf --bold Bold.ttf (.ttc collections are not supported).")
    blocks = markdown_to_blocks(md, base_dir='.' if a.input == '-' else os.path.dirname(os.path.abspath(a.input)))
    title = a.title or next((t for k, t in blocks if k == 'h1'), None)
    n = PdfForAI(reg, bold, layout='a4' if a.a4 else 'lean', figures_per_page=a.figures_per_page, number_headings=False if a.no_numbers else 'auto').build(blocks, a.output, title=title)
    print(f"{a.output}: {n} page(s), {'A4' if a.a4 else 'lean'} layout")


if __name__ == '__main__':
    main()
