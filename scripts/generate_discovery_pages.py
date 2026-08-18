#!/usr/bin/env python3
"""Generate search metadata, crawl files, and art archive pagination.

The source of truth for paginated art records is art.html. The generator keeps
the handmade pages intact while adding a consistent discovery layer around
them. Run from anywhere; paths are resolved relative to this file.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import re
import subprocess
import urllib.parse
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = "https://strauh.al"
TODAY = dt.date.today().isoformat()
PAGE_SIZE = 400
PAGE_SLOTS = 100
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic", ".tif", ".tiff")
EXCLUDED_PUBLIC_PAGES = {"cors_test.html", "museum/mockup.html"}
GENERATOR_MARKER = "<!-- discovery-layer: generated -->"

SPECIAL_TITLES = {
    "index.html": "strauh.al — a hand-built art archive and knowledge graph",
    "art.html": "Art archive — strauh.al",
    "about.html": "About the strauh.al art archive",
    "brain.html": "Brain — the strauh.al knowledge graph",
    "knowledge_base.html": "Knowledge base — strauh.al",
    "artists.html": "Artist indexes — strauh.al",
    "photography.html": "Photography archive — strauh.al",
    "museum.html": "Interactive museum — strauh.al",
    "2026_updates.html": "2026 archive updates — strauh.al",
    "disclaimer.html": "Archive scope, corrections, and rights — strauh.al",
    "donate_support.html": "Support the strauh.al archive",
}

SPECIAL_DESCRIPTIONS = {
    "index.html": "strauh.al is Ernest Strauhal's hand-built art archive, digital scrapbook, and experimental knowledge graph, maintained since 2015.",
    "art.html": "Browse the strauh.al visual art archive: thousands of collected paintings, drawings, photographs, digital works, and visual references arranged by period.",
    "about.html": "The history and purpose of strauh.al, Ernest Strauhal's personal art archive, digital scrapbook, and attempt to capture a consciousness in HTML.",
    "brain.html": "Explore an interactive knowledge graph connecting the art, ideas, artists, media, and references collected across strauh.al.",
    "knowledge_base.html": "An annotated gateway to the art, music, philosophy, technology, psychology, and web culture references collected by strauh.al.",
    "artists.html": "Browse artist-focused collections within strauh.al, including Degas, Escher, Gio Swaby, Kawase Hasui, Moebius, and others.",
    "photography.html": "A personal photography archive within strauh.al, collecting photographers, historical images, visual references, and found photographs.",
    "museum.html": "Enter the experimental three-dimensional strauh.al museum, a spatial interface for exploring works from the archive.",
    "disclaimer.html": "Read how strauh.al handles archive scope, machine-assisted descriptions, corrections, attribution, provenance, and rights questions.",
}

MEDIUM_KEYWORDS = (
    ("photograph", "Photograph"), ("photo", "Photograph"),
    ("oil painting", "Oil painting"), ("painting", "Painting"),
    ("watercolor", "Watercolor"), ("watercolour", "Watercolor"),
    ("woodblock", "Woodblock print"), ("etching", "Etching"),
    ("engraving", "Engraving"), ("print", "Print"),
    ("charcoal", "Charcoal drawing"), ("graphite", "Graphite drawing"),
    ("pencil", "Pencil drawing"), ("ink", "Ink drawing"),
    ("drawing", "Drawing"), ("sketch", "Sketch"),
    ("digital", "Digital artwork"), ("pixel", "Pixel art"),
    ("sculpture", "Sculpture"), ("ceramic", "Ceramic"),
    ("collage", "Collage"), ("textile", "Textile"),
    ("installation", "Installation"), ("manuscript", "Manuscript"),
)


def slug_words(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def canonical_path(relative: str) -> str:
    path = relative.replace("\\", "/")
    if path == "index.html":
        return "/"
    if path.endswith(".html"):
        path = path[:-5]
    return "/" + path.lstrip("/")


def absolute_url(url: str, relative_page: str = "index.html") -> str:
    if url.startswith(("https://", "http://")):
        return url.replace("http://strauh.al", SITE)
    base = SITE + canonical_path(relative_page)
    joined = urllib.parse.urljoin(base, url)
    return urllib.parse.quote(joined, safe=":/%?=&+#")


def is_image_url(url: str) -> bool:
    return urllib.parse.urlparse(html.unescape(url)).path.lower().endswith(IMAGE_EXTENSIONS)


def lastmod_for(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        return TODAY
    committed = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", relative],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return committed or TODAY


def display_name(relative: str) -> str:
    if relative == "index.html":
        return "Home"
    parts = Path(relative).with_suffix("").parts
    return " — ".join(slug_words(part).title() for part in parts)


def title_for(relative: str) -> str:
    path = canonical_path(relative)
    return "strauh.al" if path == "/" else "strauh.al" + path


def description_for(relative: str) -> str:
    if relative in SPECIAL_DESCRIPTIONS:
        return SPECIAL_DESCRIPTIONS[relative]
    name = display_name(relative)
    if relative.startswith("artists/"):
        return f"A focused strauh.al archive page collecting work and references related to {name.split(' — ')[-1]}."
    if relative.startswith("knowledge_base/"):
        return f"A curated strauh.al knowledge-base index of references, links, and notes concerning {name.split(' — ')[-1].lower()}."
    if relative.startswith("photography/"):
        return f"A focused photography collection within strauh.al dedicated to {name.split(' — ')[-1]}."
    return f"Explore {name}, a distinct section of strauh.al's hand-built art archive, digital scrapbook, and experimental knowledge graph."


def breadcrumb_markup(relative: str) -> str:
    parts = list(Path(relative).with_suffix("").parts)
    if relative == "index.html":
        return '<nav class="breadcrumbs" aria-label="Breadcrumb"><span aria-current="page">strauh.al</span></nav>'
    crumbs = ['<a href="https://strauh.al/">strauh.al</a>']
    for index, part in enumerate(parts):
        label = slug_words(part)
        if index == len(parts) - 1:
            crumbs.append(f'<span aria-current="page">{html.escape(label)}</span>')
        else:
            target = "/" + "/".join(parts[: index + 1])
            crumbs.append(f'<a href="{SITE}{target}">{html.escape(label)}</a>')
    return '<nav class="breadcrumbs" aria-label="Breadcrumb">' + " / ".join(crumbs) + "</nav>"


def context_markup(relative: str) -> str:
    candidates = [
        ("/art", "strauh.al/art"),
        ("/pagination/page-001", "strauh.al/pagination/page-001"),
        ("/knowledge_base", "strauh.al/knowledge_base"),
        ("/brain", "strauh.al/brain"),
        ("/about", "strauh.al/about"),
    ]
    current = canonical_path(relative)
    links = [f'<a href="{SITE}{path}">{label}</a>' for path, label in candidates if path != current]
    return '<nav class="contextual-links" aria-label="Explore related sections">' + " / ".join(links) + "</nav>"


def make_preview_svg(relative: str) -> str:
    preview_dir = ROOT / "assets" / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", Path(relative).with_suffix("").as_posix().lower()).strip("-") or "home"
    target = preview_dir / f"{slug}.svg"
    label = html.escape(display_name(relative))
    digest = hashlib.sha1(relative.encode()).hexdigest()
    x1 = 100 + int(digest[:2], 16) * 4
    x2 = 400 + int(digest[2:4], 16) * 4
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="#0000ff"/>
<path d="M0 {x1} C300 {x2}, 700 {630-x1}, 1200 {630-x2}" fill="none" stroke="#ffffff" stroke-width="3"/>
<circle cx="980" cy="155" r="92" fill="none" stroke="#ffffff" stroke-width="3"/>
<text x="70" y="300" fill="#ffffff" font-family="Times New Roman,serif" font-size="62">strauh.al</text>
<text x="70" y="380" fill="#ffffff" font-family="Times New Roman,serif" font-size="38">{label[:62]}</text>
</svg>'''
    target.write_text(svg, encoding="utf-8")
    return f"{SITE}/assets/previews/{target.name}"


def representative_image(source: str, relative: str) -> str:
    body = source.split("<body", 1)[-1]
    candidates = [match.group(2) for match in re.finditer(r'(?:src|href)=(["\'])(.*?)\1', body, re.I | re.S)]
    for candidate in candidates:
        bare = urllib.parse.urlparse(candidate).path.lower()
        if bare.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif")) and "banner.gif" not in bare:
            return absolute_url(candidate, relative)
    return make_preview_svg(relative)


def replace_or_add_meta(source: str, relative: str) -> str:
    title = title_for(relative)
    description = description_for(relative)
    canonical = SITE + canonical_path(relative)
    preview = representative_image(source, relative)

    if re.search(r"<title\b[^>]*>.*?</title>", source, re.I | re.S):
        source = re.sub(r"<title\b[^>]*>.*?</title>", f"<title>{html.escape(title)}</title>", source, count=1, flags=re.I | re.S)
    else:
        source = source.replace("</head>", f"  <title>{html.escape(title)}</title>\n</head>", 1)

    # Remove legacy discovery tags so reruns are idempotent.
    source = re.sub(r"\s*<meta\s+(?:name|property)=[\"'](?:description|og:title|og:description|og:image|og:url|og:type|twitter:card)[\"'][^>]*>", "", source, flags=re.I)
    source = re.sub(r"\s*<link\s+rel=[\"']canonical[\"'][^>]*>", "", source, flags=re.I)
    metadata = f'''
    <meta name="description" content="{html.escape(description, quote=True)}">
    <link rel="canonical" href="{canonical}">
    <meta property="og:title" content="{html.escape(title, quote=True)}">
    <meta property="og:description" content="{html.escape(description, quote=True)}">
    <meta property="og:image" content="{html.escape(preview, quote=True)}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">'''
    source = source.replace("</head>", metadata + "\n  </head>", 1)
    return source


def repair_heading_closures(source: str) -> str:
    pattern = re.compile(r"(<h([1-6])\b[^>]*>)(.*?)(</h([1-6])\s*>)", re.I | re.S)

    def fix(match: re.Match[str]) -> str:
        inner = match.group(3)
        if re.search(r"<h[1-6]\b", inner, re.I):
            return match.group(0)
        return match.group(1) + inner + f"</h{match.group(2)}>"

    return pattern.sub(fix, source)


def add_semantic_navigation(source: str, relative: str) -> str:
    source = re.sub(r"\s*<!-- discovery-footer: generated -->.*?<!-- /discovery-footer -->\s*", "\n", source, count=1, flags=re.S)
    if GENERATOR_MARKER in source:
        source = re.sub(
            r"\s*" + re.escape(GENERATOR_MARKER) + r".*?<!-- /discovery-layer -->\s*",
            "\n",
            source,
            count=1,
            flags=re.S,
        )
        source = re.sub(r"\s*<main id=\"main-content\">\s*", "\n", source, count=1)
        source = re.sub(r"\s*</main><!-- /main-content -->\s*", "\n", source, count=1)
    footer = f'''\n  <!-- discovery-footer: generated -->
  {context_markup(relative)}
  <!-- /discovery-footer -->'''
    source = re.sub(r"</body>", footer + "\n</body>", source, count=1, flags=re.I)
    return source


def normalize_semantic_headings(source: str, relative: str) -> str:
    comments: list[str] = []

    def mask_comment(match: re.Match[str]) -> str:
        comments.append(match.group(0))
        return f"__STRAUHAL_COMMENT_{len(comments) - 1:04d}__"

    source = re.sub(r"<!--.*?-->", mask_comment, source, flags=re.S)

    if relative == "visuals.html":
        source = re.sub(
            r'<h1 class="text-xs font-bold tracking-\[0\.4em\] uppercase text-cyan-400">(.*?)</h1>',
            r'<h2 class="text-xs font-bold tracking-[0.4em] uppercase text-cyan-400">\1</h2>',
            source,
            flags=re.I | re.S,
        )

    # Some early handmade pages used an h1 as a wrapper around later sections.
    # Close that document heading before the first h2, then discard its old
    # trailing close tag if it became orphaned.
    if relative in {"epk.html", "nyce/banquet.html", "nyce/banquet/new_mexico.html"}:
        source = re.sub(r"(<h1\b[^>]*>(?:(?!</h1>).)*?)(<h2\b)", r"\1</h1>\n\2", source, count=1, flags=re.I | re.S)
        while len(re.findall(r"<h1\b", source, re.I)) < len(re.findall(r"</h1>", source, re.I)):
            position = source.rfind("</h1>")
            source = source[:position] + source[position + len("</h1>"):]

    # Recover the primary handmade heading if an earlier generator run saw an
    # h1 example inside a comment and accidentally demoted the visible one.
    originally_headingless = {"museum.html", "cors_test.html", "visuals.html", "flap/flap.html"}
    if not re.search(r"<h1\b", source, re.I) and relative not in originally_headingless:
        source = re.sub(r"<h2\b([^>]*)>(.*?)</h2>", r"<h1\1>\2</h1>", source, count=1, flags=re.I | re.S)

    # A document gets one primary heading. Preserve the first handmade h1 and
    # demote subsequent complete h1 blocks to h2 sections.
    matches = list(re.finditer(r"<h1\b[^>]*>.*?</h1>", source, re.I | re.S))
    for match in reversed(matches[1:]):
        block = match.group(0)
        block = re.sub(r"^<h1\b", "<h2", block, count=1, flags=re.I)
        block = re.sub(r"</h1>$", "</h2>", block, count=1, flags=re.I)
        source = source[:match.start()] + block + source[match.end():]

    needs_hidden_h1 = relative in originally_headingless and 'class="visually-hidden"' not in source
    if needs_hidden_h1 or not re.search(r"<h1\b", source, re.I):
        hidden = f'<h1 class="visually-hidden">{html.escape(title_for(relative).replace(" — strauh.al", ""))}</h1>\n'
        if '<main id="main-content">' in source:
            source = source.replace('<main id="main-content">', '<main id="main-content">\n  ' + hidden, 1)
        else:
            source = re.sub(r"(<body\b[^>]*>)", r"\1\n  " + hidden, source, count=1, flags=re.I)

    if relative == "brain.html" and not re.search(r"<h2\b", source, re.I):
        source = re.sub(r"(<h3\b)", '<h2 class="visually-hidden">Knowledge graph controls</h2>\n  \\1', source, count=1, flags=re.I)

    if relative in {"nyce.html", "nyce/banquet.html", "nyce/banquet/california.html", "nyce/banquet/new_mexico.html"}:
        missing_closes = len(re.findall(r"<h2\b", source, re.I)) - len(re.findall(r"</h2>", source, re.I))
        if missing_closes > 0:
            closings = "</h2>\n" * missing_closes
            if "</main><!-- /main-content -->" in source:
                source = source.replace("</main><!-- /main-content -->", closings + "  </main><!-- /main-content -->", 1)
            else:
                source = source.replace("</body>", closings + "</body>", 1)

    for index, comment in enumerate(comments):
        source = source.replace(f"__STRAUHAL_COMMENT_{index:04d}__", comment)
    return source


def clean_existing_pages() -> list[Path]:
    pages = sorted(p for p in ROOT.rglob("*.html") if ".git" not in p.parts and "pagination" not in p.parts)
    changed = []
    for page in pages:
        relative = page.relative_to(ROOT).as_posix()
        source = page.read_text(encoding="utf-8", errors="replace")
        source = clean_failed_archive_anchors(source)
        forced_headings = {
            "nyce.html": '<h1><a href="https://strauh.al">strauh.al</a>/nyce</h1>',
            "nyce/banquet/california.html": '<h1><a href="https://strauh.al">strauh.al</a>/<a href="https://strauh.al/nyce">nyce</a>/<a href="https://strauh.al/nyce/banquet">banquet</a>/california</h1>',
        }
        if relative in forced_headings:
            source = re.sub(r"(?<!<!-- )<h1\b[^>]*>.*?<h2\b", forced_headings[relative] + "\n<h2", source, count=1, flags=re.I | re.S)
        source = source.replace("http://strauh.al", SITE)
        source = source.replace(f'{SITE}/donate"', f'{SITE}/donate_support"')
        source = source.replace(f'{SITE}/flap"', f'{SITE}/flap/flap"')
        source = repair_heading_closures(source)
        source = replace_or_add_meta(source, relative)
        source = add_semantic_navigation(source, relative)
        source = normalize_semantic_headings(source, relative)
        page.write_text(source, encoding="utf-8")
        changed.append(page)
    return changed


def clean_failed_archive_anchors(source: str) -> str:
    anchor_pattern = re.compile(r"(<br\s*/?>\s*)?<a\s+href=([\"'])(.*?)\2[^>]*>(.*?)</a>", re.I | re.S)
    record_number = 0

    def clean_anchor(match: re.Match[str]) -> str:
        nonlocal record_number
        url, raw_label = match.group(3), match.group(4)
        if not is_image_url(url):
            return match.group(0)
        label = clean_text(raw_label)
        if re.search(r"^(?:error|failed to fetch|could not retrieve)", label, re.I):
            return ""
        record_number += 1
        fixed = normalized_label(label, url, record_number)
        return f'{match.group(1) or ""}<a href="{html.escape(html.unescape(url), quote=True)}">{html.escape(fixed)}</a>'

    return anchor_pattern.sub(clean_anchor, source)


def blame_dates(path: Path) -> dict[int, str]:
    result = subprocess.run(
        ["git", "blame", "--line-porcelain", "--", path.name],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    dates: dict[int, str] = {}
    line_no = None
    timestamp = None
    for line in result:
        header = re.match(r"^[0-9a-f^]{7,40}\s+\d+\s+(\d+)(?:\s+\d+)?$", line)
        if header:
            line_no = int(header.group(1))
            timestamp = None
        elif line.startswith("author-time "):
            timestamp = dt.datetime.fromtimestamp(int(line.split()[1]), tz=dt.timezone.utc).date().isoformat()
        elif line.startswith("\t") and line_no is not None:
            dates[line_no] = timestamp or TODAY
            line_no += 1
    return dates


def normalized_label(label: str, url: str, record_number: int) -> str:
    label = clean_text(label)
    placeholder = bool(
        re.fullmatch(r"(?:img|image|photo|dsc|pxl|scan)[-_ ]?\d+\.(?:jpe?g|png|gif|webp|heic)", label, re.I)
        or re.fullmatch(r"\d+\.(?:jpe?g|png|gif|webp|heic)", label, re.I)
        or re.fullmatch(r"[a-zA-Z0-9_-]{18,}\.(?:jpe?g|png|gif|webp|heic)", label)
        or re.search(r"\.(?:jpe?g|png|gif|webp|heic|avif|tiff?)$", label, re.I)
    )
    if placeholder:
        filename = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
        candidate = slug_words(re.sub(r"\.(?:jpe?g|png|gif|webp|heic|avif|tiff?)$", "", filename, flags=re.I))
        if len(candidate) >= 12 and not re.fullmatch(r"(?:img|image|photo|dsc|pxl|scan)[-_ ]?\d+", candidate, re.I):
            label = candidate
        else:
            label = f"Untitled archive image (record {record_number})"
    return label or f"Untitled archive image (record {record_number})"


def parse_art_label(label: str) -> tuple[str, str, str]:
    date_match = re.search(r"\(([^()]*(?:\d{3,4}|BCE|CE)[^()]*)\)\s*$", label, re.I)
    date = date_match.group(1).strip() if date_match else "Unknown"
    without_date = label[: date_match.start()].strip() if date_match else label
    by_match = re.match(r"(.+?)\s+by\s+(.+)$", without_date, re.I)
    if by_match:
        return by_match.group(1).strip(), by_match.group(2).strip(), date
    return without_date, "Unknown", date


def infer_medium(label: str) -> str:
    lowered = label.lower()
    for keyword, medium in MEDIUM_KEYWORDS:
        if keyword in lowered:
            return medium
    return "Unknown or unspecified"


def infer_tags(label: str, section: str, medium: str, artist: str) -> list[str]:
    tags = [section, medium.lower()]
    if artist != "Unknown":
        tags.append(artist.lower())
    lowered = label.lower()
    for keyword in ("abstract", "figurative", "geometric", "landscape", "portrait", "architecture", "digital", "religious", "comic", "surreal", "installation"):
        if keyword in lowered:
            tags.append(keyword)
    return list(dict.fromkeys(tag for tag in tags if tag and tag != "unknown or unspecified"))[:7]


def clean_art_source() -> None:
    page = ROOT / "art.html"
    source = page.read_text(encoding="utf-8", errors="replace")
    anchor_pattern = re.compile(r"(<br\s*/?>\s*)?<a\s+href=([\"'])(.*?)\2[^>]*>(.*?)</a>", re.I | re.S)
    record_number = 0

    def clean_anchor(match: re.Match[str]) -> str:
        nonlocal record_number
        url, raw_label = match.group(3), match.group(4)
        if not is_image_url(url):
            return match.group(0)
        label = clean_text(raw_label)
        if re.search(r"^(?:error|failed to fetch|could not retrieve)", label, re.I):
            return ""
        record_number += 1
        fixed = normalized_label(label, url, record_number)
        prefix = match.group(1) or ""
        return f'{prefix}<a href="{html.escape(url, quote=True)}">{html.escape(fixed)}</a>'

    source = anchor_pattern.sub(clean_anchor, source)
    page.write_text(source, encoding="utf-8")


def extract_art_records() -> list[dict[str, object]]:
    page = ROOT / "art.html"
    source = page.read_text(encoding="utf-8", errors="replace")
    dates = blame_dates(page)
    heading_matches = list(re.finditer(r"<h2\b[^>]*id=[\"']([^\"']+)[\"']", source, re.I))
    sections = []
    for index, match in enumerate(heading_matches):
        end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(source)
        sections.append((match.start(), end, clean_text(match.group(1))))

    records = []
    seen = set()
    anchor_pattern = re.compile(r"<a\s+href=([\"'])(.*?)\1[^>]*>(.*?)</a>", re.I | re.S)
    for match in anchor_pattern.finditer(source):
        url = html.unescape(match.group(2))
        if not is_image_url(url) or url in seen:
            continue
        seen.add(url)
        label = normalized_label(match.group(3), url, len(records) + 1)
        title, artist, date = parse_art_label(label)
        medium = infer_medium(label)
        section = "unsorted"
        for start, end, candidate in sections:
            if start <= match.start() < end:
                section = candidate
                break
        line = source.count("\n", 0, match.start()) + 1
        record_id = "work-" + hashlib.sha1(url.encode()).hexdigest()[:12]
        records.append({
            "id": record_id,
            "url": url,
            "label": label,
            "title": title,
            "artist": artist,
            "date": date,
            "medium": medium,
            "section": section,
            "tags": infer_tags(label, section, medium, artist),
            "added": dates.get(line, TODAY),
        })
    return records


def record_url(record: dict[str, object], index: int) -> str:
    page_number = index // PAGE_SIZE + 1
    return f"{SITE}/pagination/page-{page_number:03d}#{record['id']}"


def related_records(records: list[dict[str, object]]) -> dict[str, list[int]]:
    by_artist: dict[str, list[int]] = defaultdict(list)
    by_section: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        artist = str(record["artist"])
        if artist != "Unknown":
            by_artist[artist.lower()].append(index)
        by_section[str(record["section"])].append(index)
    related: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        candidates = by_artist.get(str(record["artist"]).lower(), []) if record["artist"] != "Unknown" else []
        candidates = [item for item in candidates if item != index]
        if len(candidates) < 3:
            nearby = by_section[str(record["section"])]
            position = nearby.index(index)
            candidates.extend(item for item in nearby[max(0, position - 2): position + 3] if item != index)
        related[str(record["id"])] = list(dict.fromkeys(candidates))[:3]
    return related


def pagination_document(page_number: int, records: list[dict[str, object]], relations: dict[str, list[int]], all_records: list[dict[str, object]], archive_lastmod: str) -> str:
    canonical = f"{SITE}/pagination/page-{page_number:03d}"
    start = (page_number - 1) * PAGE_SIZE + 1
    end = start + len(records) - 1
    if records:
        title = f"strauh.al/pagination/page-{page_number:03d}"
        heading = f"Art archive catalog records {start}–{end}"
        description = f"Catalog page {page_number} of the strauh.al art archive, documenting records {start} through {end} with images, captions, dates, media, sources, tags, and archive notes."
        preview = absolute_url(str(records[0]["url"]))
        robots = "index,follow,max-image-preview:large"
        canonical_tag = canonical
    else:
        title = f"strauh.al/pagination/page-{page_number:03d}"
        heading = f"Reserved art archive catalog page {page_number}"
        description = f"Reserved pagination slot {page_number} for future additions to the strauh.al art archive."
        preview = make_preview_svg(f"pagination/page-{page_number:03d}.html")
        robots = "noindex,follow"
        canonical_tag = f"{SITE}/art"

    cards = []
    base_index = (page_number - 1) * PAGE_SIZE
    for offset, record in enumerate(records):
        index = base_index + offset
        source = html.escape(str(record["url"]), quote=True)
        alt = html.escape(str(record["label"]), quote=True)
        tags = ", ".join(str(tag) for tag in record["tags"])
        relation_links = []
        for related_index in relations[str(record["id"])]:
            related = all_records[related_index]
            relation_links.append(f'<a href="{record_url(related, related_index)}">{html.escape(str(related["title"]))}</a>')
        related_html = " / ".join(relation_links) or "No related record assigned"
        archive_note = f"Filed in the {record['section']} section of strauh.al; relationships are based on shared artist or neighboring archive context."
        cards.append(f'''    <article class="art-record" id="{record['id']}">
      <h2>{html.escape(str(record['title']))}</h2>
      <figure>
        <a href="{source}"><img src="{source}" loading="lazy" decoding="async" alt="{alt}"></a>
        <figcaption>{html.escape(str(record['label']))}</figcaption>
      </figure>
      <dl>
        <dt>Artist</dt><dd>{html.escape(str(record['artist']))}</dd>
        <dt>Title</dt><dd>{html.escape(str(record['title']))}</dd>
        <dt>Date</dt><dd>{html.escape(str(record['date']))}</dd>
        <dt>Medium</dt><dd>{html.escape(str(record['medium']))}</dd>
        <dt>Source asset</dt><dd><a href="{source}">{source}</a></dd>
        <dt>Provenance</dt><dd>Collected in the strauh.al archive; original provenance has not yet been independently verified.</dd>
        <dt>Rights status</dt><dd>Unknown unless stated at the linked source; inclusion does not imply that the work is in the public domain.</dd>
        <dt>Archive annotation</dt><dd>{html.escape(archive_note)}</dd>
        <dt>Tags</dt><dd>{html.escape(tags)}</dd>
        <dt>Related works</dt><dd>{related_html}</dd>
        <dt>Date added</dt><dd><time datetime="{record['added']}">{record['added']}</time></dd>
        <dt>Date updated</dt><dd><time datetime="{archive_lastmod}">{archive_lastmod}</time></dd>
        <dt>Stable record URL</dt><dd><a href="{record_url(record, index)}">{record_url(record, index)}</a></dd>
      </dl>
    </article>''')

    previous_link = f'<a rel="prev" href="{SITE}/pagination/page-{page_number - 1:03d}">previous catalog page</a>' if page_number > 1 and page_number - 1 <= (len(all_records) + PAGE_SIZE - 1) // PAGE_SIZE else ""
    next_link = f'<a rel="next" href="{SITE}/pagination/page-{page_number + 1:03d}">next catalog page</a>' if page_number * PAGE_SIZE < len(all_records) else ""
    page_links = " / ".join(item for item in (previous_link, '<a href="https://strauh.al/art">interactive art index</a>', next_link) if item)
    content = "\n".join(cards) if cards else '<section class="reserved"><h2>Reserved for future archive records</h2><p>This file is intentionally excluded from search indexes until the archive contains records for this slot.</p></section>'
    count_text = f"This page contains {len(records)} distinct archive records." if records else "This pagination slot is not yet populated."
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{canonical_tag}">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:image" content="{html.escape(preview, quote=True)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="../style.css">
  <link rel="stylesheet" href="pagination.css">
</head>
<body>
  <a class="skip-link" href="#main-content">skip to content</a>
  <main id="main-content">
    <h1><a href="{SITE}/">strauh.al</a>/pagination/page-{page_number:03d}</h1>
    <h2>{html.escape(heading)}</h2>
    <p>{html.escape(count_text)} Records are generated from the handmade art index; unknown metadata is labeled rather than invented.</p>
{content}
    <nav class="contextual-links" aria-label="Catalog pagination">{page_links}</nav>
  </main>
</body>
</html>
'''


def generate_pagination(records: list[dict[str, object]]) -> list[Path]:
    directory = ROOT / "pagination"
    directory.mkdir(exist_ok=True)
    style = '''.art-record{border-top:1px solid #fff;padding:1.5rem 0;content-visibility:auto;contain-intrinsic-size:900px}.art-record figure{margin:1rem 0}.art-record img{display:block;max-width:min(900px,100%);max-height:75vh;width:auto;height:auto;background:#fff}.art-record figcaption{max-width:70ch;margin-top:.5rem}.art-record dl{display:grid;grid-template-columns:minmax(8rem,12rem) minmax(0,1fr);gap:.45rem 1rem;max-width:1000px}.art-record dt{font-weight:bold}.art-record dd{margin:0;overflow-wrap:anywhere}.reserved{border:1px solid #fff;padding:1rem}@media(max-width:650px){.art-record dl{display:block}.art-record dt{margin-top:.75rem}}\n'''
    (directory / "pagination.css").write_text(style, encoding="utf-8")
    relations = related_records(records)
    archive_lastmod = lastmod_for(ROOT / "art.html")
    pages = []
    for page_number in range(1, PAGE_SLOTS + 1):
        subset = records[(page_number - 1) * PAGE_SIZE: page_number * PAGE_SIZE]
        target = directory / f"page-{page_number:03d}.html"
        target.write_text(pagination_document(page_number, subset, relations, records, archive_lastmod), encoding="utf-8")
        pages.append(target)
    return pages


def write_crawl_files(existing_pages: list[Path], populated_page_count: int) -> None:
    public = []
    for page in existing_pages:
        relative = page.relative_to(ROOT).as_posix()
        if relative not in EXCLUDED_PUBLIC_PAGES:
            public.append((SITE + canonical_path(relative), lastmod_for(page)))
    for page_number in range(1, populated_page_count + 1):
        page = ROOT / "pagination" / f"page-{page_number:03d}.html"
        public.append((f"{SITE}/pagination/page-{page_number:03d}", lastmod_for(page)))
    public = sorted(set(public))
    entries = "\n".join(f"  <url><loc>{html.escape(url)}</loc><lastmod>{lastmod}</lastmod></url>" for url, lastmod in public)
    sitemap = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>
'''
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    robots = f'''User-agent: *
Allow: /

# Search/citation crawlers are welcome. Training access can be managed separately.
User-agent: OAI-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: Claude-User
Allow: /

Sitemap: {SITE}/sitemap.xml
'''
    (ROOT / "robots.txt").write_text(robots, encoding="utf-8")


def add_shared_styles() -> None:
    path = ROOT / "style.css"
    source = path.read_text(encoding="utf-8")
    marker = "/* discovery navigation */"
    if marker in source:
        source = source.split(marker, 1)[0].rstrip() + "\n"
    source += '''

/* discovery navigation */
.skip-link{position:absolute;left:-9999px;top:0;z-index:9999;background:#fff;color:#00f;padding:.5rem}.skip-link:focus{left:.5rem}.visually-hidden{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}.breadcrumbs,.contextual-links{position:relative;z-index:20;width:fit-content;max-width:calc(100% - 2rem);margin:.5rem 0;padding:.25rem .4rem;background:#00f;color:#fff;line-height:1.35}.breadcrumbs a,.contextual-links a{color:#fff}main{display:block}
'''
    path.write_text(source, encoding="utf-8")


def main() -> None:
    clean_art_source()
    records = extract_art_records()
    existing_pages = clean_existing_pages()
    generate_pagination(records)
    populated = (len(records) + PAGE_SIZE - 1) // PAGE_SIZE
    write_crawl_files(existing_pages, populated)
    add_shared_styles()
    print(f"Generated {len(records)} distinct art records across {populated} populated pages and {PAGE_SLOTS - populated} reserved page slots.")


if __name__ == "__main__":
    main()
