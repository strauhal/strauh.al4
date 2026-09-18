"""Rebuild the timeline metadata from the canonical art archive (no image downloads)."""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

class Archive(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.href = None
        self.label = []
        self.items = []
        self.seen = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'gallery-content':
            self.active = True
        if self.active and tag == 'a':
            self.href = attrs.get('href', '')
            self.label = []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == 'div' and self.active:
            self.active = False
        if tag != 'a' or self.href is None:
            return
        url, title = self.href, ''.join(self.label).strip()
        self.href = None
        if not re.search(r'\.(?:jpe?g|png|webp|gif|avif)(?:\?|$)', url, re.I) or url in self.seen:
            return
        self.seen.add(url)
        clean = title.replace('_', ' ')
        # Prefer the final dated parenthesis: earlier numbers may describe the subject.
        parentheses = re.findall(r'\(([^()]*)\)', clean)
        years = []
        for part in reversed(parentheses):
            years = re.findall(r'(?<!\d)(1\d{3}|20[0-2]\d)(?!\d)', part)
            if years:
                break
        if not years:
            years = re.findall(r'(?<!\d)(1\d{3}|20[0-2]\d)(?!\d)', clean)
            years = years[-1:]
        folder = re.search(r'/(\d{1,4})s/', unquote(url))
        century = re.search(r'(\d{1,2})(?:st|nd|rd|th)[ -]+century', clean, re.I)
        year = int(years[0]) if years else None
        precision = 'year'
        if year is None and century:
            year = (int(century[1]) - 1) * 100
            precision = 'century'
        if year is None and folder:
            year = int(folder[1])
            precision = 'century'
        self.items.append(dict(title=clean, url=url, year=year, precision=precision))

archive = Archive()
archive.feed((ROOT / 'art.html').read_text())
archive.items.sort(key=lambda item: item['year'] if item['year'] is not None else 99999)
output = ROOT / 'assets/timeline/artworks.json'
output.write_text(json.dumps(archive.items, ensure_ascii=False, separators=(',', ':')))
print(f'{len(archive.items)} unique artworks; {sum(x["year"] is None for x in archive.items)} undated → {output}')
