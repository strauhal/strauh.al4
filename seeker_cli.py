#!/usr/bin/env python3
"""
SEEKER CLI — classify & rename an entire image folder with Gemini vision.

Same brain as seeker2.html, but headless: no browser, no folder-picker, so it
can rip through hundreds of files unattended and it's resumable.

  export GEMINI_API_KEY=AIza...
  python3 seeker_cli.py /path/to/unsorted            # DRY RUN (prints proposals + writes seeker_plan.csv)
  python3 seeker_cli.py /path/to/unsorted --apply    # actually renames, writes seeker_undo.sh

Real artworks  -> "Title by Artist (Year).ext"
Everything else-> "Type - Description.ext"   (Photograph / Screenshot / Diagram / Illustration / Comic / Document / Image)

Only stdlib is used (falls back to certifi for TLS if the interpreter's own CA
bundle is missing, as on some python.org macOS installs). Requires Python 3.8+.
"""
import argparse, base64, concurrent.futures as cf, csv, json, mimetypes, os, re, ssl, sys, time, urllib.request, urllib.error

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None  # use urllib's default (may fail with CERTIFICATE_VERIFY_FAILED on some installs)

IMG_EXT = re.compile(r"\.(jpe?g|png|gif|webp|bmp|tiff?|heic|avif)$", re.I)
SYS = ("You are a precise art & image archivist. Accuracy over specificity — NEVER guess an artist, title or year. "
       "Use category 'artwork' with a real artist/title ONLY when you positively recognise the exact piece; "
       "otherwise choose the correct category and give a plain visual description.")
SCHEMA = {"type":"OBJECT","properties":{
    "category":{"type":"STRING","description":"artwork, photograph, screenshot, diagram, illustration, comic, document, or other"},
    "artist":{"type":"STRING","description":"Creator full name, or 'Unknown'."},
    "title":{"type":"STRING","description":"Official title if certain, else empty."},
    "year":{"type":"STRING","description":"Year/range (1879, 1599-1600, c. 1440, 1970s) or 'Unknown'."},
    "description":{"type":"STRING","description":"Short Title-Case description for non-artworks, <=10 words."},
    "bucket":{"type":"STRING","description":(
        "'personal' if this is a private/personal photo or document of the archive owner, their family, "
        "friends, or personal life (selfies, casual snapshots, personal correspondence, receipts, notes) -- "
        "NOT general downloaded art, reference photography, or memes. "
        "'meme' if this is an internet meme, image macro, reaction image, or shitpost -- a joke image, often "
        "with overlaid text or absurdist humor -- NOT a genuine artwork, photograph, diagram, or informative "
        "screenshot. Otherwise leave this empty ('').")}},
    "required":["category","artist","title","year","description","bucket"],
    "propertyOrdering":["category","artist","title","year","description","bucket"]}
PREFIX = {"photograph":"Photograph","screenshot":"Screenshot","diagram":"Diagram","illustration":"Illustration",
          "comic":"Comic","document":"Document","other":"Image"}
BUCKET_DIRS = {"personal":"Personal","meme":"Memes"}

def known(v): return bool(v) and not re.match(r"^\s*(unknown|untitled|n/?a|none)\s*$", v.strip(), re.I)

def build_name(d):
    cat = (d.get("category") or "other").lower()
    # "artwork" with NO known title is not really identified -- fall through to the
    # description-based Type prefix instead of producing a bare, uninformative "Untitled".
    if cat == "artwork" and known(d.get("title")):
        s = d["title"].strip()
        if known(d.get("artist")): s += " by " + d["artist"].strip()
        if known(d.get("year")):   s += " (" + d["year"].strip() + ")"
        return s
    prefix_cat = "illustration" if cat == "artwork" else cat   # unidentified "artwork" reads as illustration
    s = PREFIX.get(prefix_cat, "Image") + " - " + (d["description"].strip() if known(d.get("description"))
                                            else (d["title"].strip() if known(d.get("title")) else "Untitled"))
    if known(d.get("artist")): s += " by " + d["artist"].strip()
    return s

def sanitize(base):
    base = re.sub(r"[/\\]", "-", base)
    base = re.sub(r"[\x00-\x1f]", "", base)
    base = re.sub(r"\s+", " ", base).strip().rstrip(". ")
    return base[:190]

def already_named(n):
    if re.match(r"^(%s) - " % "|".join(PREFIX.values()), n):
        return True
    stem = os.path.splitext(n)[0]
    if "_" in stem:                       # raw AI-generated / scraped names are always snake_case
        return False
    if stem.lower().startswith("untitled"):   # the old bare-Untitled bug -- always worth reprocessing
        return False
    if re.search(r"\bby\b", stem, re.I):      # "Title by Artist[.ext]" / "Title by Artist (Year)[.ext]"
        return True
    return bool(re.search(r"\(.+\)$", stem))  # "Title (Year)[.ext]" -- dated but artist unknown

def call_gemini(path, key, model, tries=4):
    with open(path, "rb") as fh: raw = fh.read()
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    if not mime.startswith("image/"): raise RuntimeError("not an image (%s)" % mime)
    payload = {"contents":[{"role":"user","parts":[
                  {"text":'Classify and name this image. Current filename (hint, may be useless): "%s"' % os.path.basename(path)},
                  {"inlineData":{"mimeType":mime,"data":base64.b64encode(raw).decode()}}]}],
               "systemInstruction":{"parts":[{"text":SYS}]},
               "generationConfig":{"responseMimeType":"application/json","responseSchema":SCHEMA,"temperature":0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
    data = json.dumps(payload).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=90, context=_SSL_CTX) as r:
                j = json.loads(r.read())
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(re.sub(r"^```json\n?|\n?```$", "", txt.strip()))
        except urllib.error.HTTPError as e:
            if e.code in (429,500,503) and i < tries-1: time.sleep(2**i + 0.5); continue
            raise RuntimeError("HTTP %s: %s" % (e.code, e.read()[:150].decode("utf-8","replace")))
        except Exception as e:
            if i < tries-1: time.sleep(2**i + 0.5); continue
            raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--key", default=os.environ.get("GEMINI_API_KEY",""))
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--apply", action="store_true", help="actually rename (default is dry run)")
    ap.add_argument("--skip-named", action="store_true", help="skip files already in the target format")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0, help="only process the first N matched files (smoke test)")
    ap.add_argument("--sort-buckets", action="store_true",
                     help="also move personal photos into Personal/ and memes/shitposts into Memes/ subfolders")
    ap.add_argument("--bucket-scan-named", action="store_true",
                     help="with --sort-buckets: ALSO scan already-named files for personal/meme routing "
                          "(moves them, unchanged filename, into Personal/Memes -- does not rename them)")
    a = ap.parse_args()
    if not a.key: sys.exit("Set --key or GEMINI_API_KEY.")

    all_files = sorted(f for f in os.listdir(a.folder) if IMG_EXT.search(f) and os.path.isfile(os.path.join(a.folder,f)))
    # (filename, keep_original_name) -- rename-eligible files vs. already-named files we only bucket-scan
    jobs = [(f, False) for f in all_files if not already_named(f)] if a.skip_named else [(f, False) for f in all_files]
    if a.skip_named and a.sort_buckets and a.bucket_scan_named:
        jobs += [(f, True) for f in all_files if already_named(f)]
    if a.limit: jobs = jobs[:a.limit]
    print("%d images %s in %s\n" % (len(jobs), "to process" if a.apply else "to preview", a.folder))

    def work(job):
        fn, keep_name = job
        ext = os.path.splitext(fn)[1].lower()
        try:
            d = call_gemini(os.path.join(a.folder, fn), a.key, a.model)
            bucket = (d.get("bucket") or "").strip().lower() if a.sort_buckets else ""
            if bucket not in BUCKET_DIRS: bucket = ""
            new = fn if keep_name else sanitize(build_name(d)) + ext
            return fn, new, d.get("category","?"), bucket, keep_name, None
        except Exception as e:
            return fn, None, None, "", keep_name, str(e)[:80]

    # collision tracking is per destination directory (root, Personal/, Memes/)
    used = {"": set(x.lower() for x in os.listdir(a.folder))}
    if a.sort_buckets:
        for b, sub in BUCKET_DIRS.items():
            p = os.path.join(a.folder, sub)
            used[b] = set(x.lower() for x in os.listdir(p)) if os.path.isdir(p) else set()

    results = []  # (old_name, new_name, bucket)
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, (fn, new, cat, bucket, keep_name, err) in enumerate(ex.map(work, jobs), 1):
            tag = (cat or "ERR") + (" ->" + BUCKET_DIRS[bucket] if bucket else "")
            print("[%d/%d] %-20s %s" % (i, len(jobs), tag, fn))
            if err: print("        ! %s" % err); continue
            if keep_name and not bucket:
                continue  # already-named + not personal/meme -> leave it exactly where it is
            u = used[bucket]
            stem, e = os.path.splitext(new); k = 2
            while new.lower() in u and new.lower() != fn.lower(): new = "%s (%d)%s" % (stem, k, e); k += 1
            print("        -> %s%s" % (BUCKET_DIRS[bucket] + "/" if bucket else "", new))
            u.add(new.lower())
            results.append((fn, new, bucket))

    with open(os.path.join(a.folder, "seeker_plan.csv"), "w", newline="") as fh:
        csv.writer(fh).writerows([("old","new","bucket")] + results)
    if a.apply:
        if a.sort_buckets:
            for sub in BUCKET_DIRS.values(): os.makedirs(os.path.join(a.folder, sub), exist_ok=True)
        undo = ["#!/bin/bash", "# revert SEEKER renames/moves"]
        n_moved = {"":0, "personal":0, "meme":0}
        for old, new, bucket in results:
            dest_dir = os.path.join(a.folder, BUCKET_DIRS[bucket]) if bucket else a.folder
            try:
                os.rename(os.path.join(a.folder, old), os.path.join(dest_dir, new))
                undo.append("mv -n %s %s" % (json.dumps(os.path.join(dest_dir, new)), json.dumps(os.path.join(a.folder, old))))
                n_moved[bucket] += 1
            except OSError as e:
                print("  rename failed: %s (%s)" % (old, e))
        with open(os.path.join(a.folder, "seeker_undo.sh"), "w") as fh: fh.write("\n".join(reversed(undo)) + "\n")
        total = sum(n_moved.values())
        extra = (" (%d -> Personal/, %d -> Memes/)" % (n_moved["personal"], n_moved["meme"])) if a.sort_buckets else ""
        print("\nRenamed %d files%s. Undo: bash seeker_undo.sh" % (total, extra))
    else:
        print("\nDRY RUN — wrote seeker_plan.csv. Re-run with --apply to rename.")

if __name__ == "__main__":
    main()
