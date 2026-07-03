#!/usr/bin/env python3
"""
SEEKER CLI — classify & rename an entire image folder with Gemini vision.

Same brain as seeker2.html, but headless: no browser, no folder-picker, so it
can rip through hundreds of files unattended and it's resumable.

  export GEMINI_API_KEY=AIza...
  python3 seeker_cli.py /path/to/unsorted            # DRY RUN (prints proposals + writes seeker_plan.csv)
  python3 seeker_cli.py /path/to/unsorted --apply    # actually renames, writes seeker_undo.sh

  python3 seeker_cli.py /path/to/2000s --reverse-image-search --apply
      Adds a real reverse-image-search step (Google Cloud Vision "Web Detection") before
      classification: finds actual web pages containing the same/similar image and feeds
      their titles/entities to Gemini as evidence, instead of Gemini guessing from pixels
      alone. Needs the Cloud Vision API enabled on the same GCP project as your key
      (console.cloud.google.com/apis/library/vision.googleapis.com). Falls back to plain
      classification automatically if Vision API isn't enabled or finds nothing useful.

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
       "otherwise choose the correct category and give a plain visual description. The 'description' field is "
       "REQUIRED whenever title is not confidently known, no matter the category (including 'artwork' with an "
       "unconfirmed title) -- never leave it empty. If reverse-image-search evidence is provided, it only ever "
       "contains an ACTUAL matched web page (never a vague generic guess) -- but still only use it to name an "
       "artist/title if that page's title clearly and specifically identifies THIS image. If no evidence is "
       "provided at all, that means the search found nothing -- do not invent an artist or title anyway based "
       "on subject matter, painting style, or your own suspicion; give a plain visual description instead.")
SCHEMA = {"type":"OBJECT","properties":{
    "category":{"type":"STRING","description":"artwork, photograph, screenshot, diagram, illustration, comic, document, or other"},
    "artist":{"type":"STRING","description":"Creator full name, or 'Unknown'."},
    "title":{"type":"STRING","description":"Official title if certain, else empty."},
    "year":{"type":"STRING","description":"Year/range (1879, 1599-1600, c. 1440, 1970s) or 'Unknown'."},
    "description":{"type":"STRING","description":"Short Title-Case visual description, <=10 words -- REQUIRED whenever title is empty/unknown, regardless of category."},
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

def call_gemini(path, key, model, evidence=None, tries=4):
    with open(path, "rb") as fh: raw = fh.read()
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    if not mime.startswith("image/"): raise RuntimeError("not an image (%s)" % mime)
    prompt = 'Classify and name this image. Current filename (hint, may be useless): "%s"' % os.path.basename(path)
    if evidence:
        prompt += ("\n\nReverse image search evidence (Google Cloud Vision Web Detection found these "
                    "real web pages/entities for this image). Use it ONLY if it clearly and specifically "
                    "names a real artist and/or title for THIS image -- ignore it if generic, unrelated, "
                    "or just a stock-photo/aggregator/social-media listing with no real attribution:\n" + evidence)
    payload = {"contents":[{"role":"user","parts":[
                  {"text": prompt},
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

FORCE_DESCRIBE_SYS = ("You are a precise art & image archivist. A specific-artist claim for this image "
    "could not be independently verified. Do NOT name an artist or title, and do NOT mention any "
    "specific person's name anywhere in your response, including inside the description field (not "
    "as the artist, not as a stylistic reference like 'in the style of X', not as a subject/character "
    "name) -- just classify its category and give a short, plain, Title-Case visual description of "
    "what is depicted (<=10 words), with no names of any kind.")

def classify_verified(path, key, model, evidence=None, ris_active=False):
    """Hard-requires real reverse-image-search page-match evidence before accepting ANY specific
    artist/title claim -- rather than trusting the model's self-reported confidence.

    Why not just re-sample and check for agreement? Tested it: on a genuinely unidentifiable
    generic genre painting, 10 identical temperature=0 calls split ~60/40 between two different
    fabricated (but real, genre-plausible) Dutch-painter names. At that split, requiring even 3
    identical repeats to agree still passes by pure chance ~28% of the time (0.6^3+0.4^3) -- not
    reliable enough. A hard evidence gate has no such failure rate: no real matched page, no claim,
    full stop.

    `ris_active` means reverse-image-search actually ran for this call (regardless of whether it
    found anything) -- distinct from `evidence` being falsy, which could ALSO mean "RIS is off
    entirely" (baseline mode, ungated, unchanged behaviour) or "RIS ran but found nothing" (must
    gate). Conflating those two would silently skip the gate exactly when it matters most."""
    d = call_gemini(path, key, model, evidence=evidence)
    if not ris_active or evidence or not (known(d.get("artist")) or known(d.get("title"))):
        return d  # RIS not in use this call, grounded in a real page match, or no attribution claimed anyway
    # RIS was on, found no real page match, yet the model still claimed a specific artist/title --
    # that claim is unverified. Get an honest fallback description instead of trusting it.
    payload = {"contents": [{"role": "user", "parts": [
                  {"text": 'Classify this image. Current filename (hint): "%s"' % os.path.basename(path)},
                  {"inlineData": {"mimeType": mimetypes.guess_type(path)[0] or "image/jpeg",
                                  "data": base64.b64encode(open(path, "rb").read()).decode()}}]}],
               "systemInstruction": {"parts": [{"text": FORCE_DESCRIBE_SYS}]},
               "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA, "temperature": 0}}
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90, context=_SSL_CTX) as r:
        j = json.loads(r.read())
    fallback = json.loads(re.sub(r"^```json\n?|\n?```$", "", j["candidates"][0]["content"]["parts"][0]["text"].strip()))
    fallback["artist"], fallback["title"], fallback["year"] = "Unknown", "", "Unknown"
    return fallback

class VisionAPIDisabled(Exception):
    """Raised once when Cloud Vision API isn't usable (not enabled, or no OAuth
    credentials available) -- caller disables reverse-image-search for the rest
    of the run rather than retrying (and silently failing on) every file."""

_token_cache = {"tok": None, "exp": 0}

def get_access_token():
    """Cloud Vision's images:annotate REJECTS plain API keys outright (unlike Gemini) --
    it requires an OAuth2 access token. We shell out to `gcloud auth application-default
    print-access-token`, which needs a ONE-TIME setup:
        brew install google-cloud-sdk   (or https://cloud.google.com/sdk/docs/install)
        gcloud auth application-default login
    Tokens last ~1hr; cached in-process and refreshed a bit early."""
    import subprocess
    now = time.time()
    if _token_cache["tok"] and now < _token_cache["exp"]:
        return _token_cache["tok"]
    try:
        out = subprocess.run(["gcloud", "auth", "application-default", "print-access-token"],
                              capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        raise VisionAPIDisabled(
            "gcloud CLI not found. Cloud Vision needs OAuth2 (API keys aren't accepted). One-time setup:\n"
            "  brew install google-cloud-sdk\n  gcloud auth application-default login")
    if out.returncode != 0 or not out.stdout.strip():
        raise VisionAPIDisabled(
            "gcloud couldn't produce an access token (%s). Run:\n  gcloud auth application-default login"
            % (out.stderr.strip()[:200] or "unknown error"))
    _token_cache["tok"] = out.stdout.strip()
    _token_cache["exp"] = now + 50 * 60  # refresh after 50 min (tokens last ~60)
    return _token_cache["tok"]

_quota_project_cache = {"id": None}

def get_quota_project():
    """ADC access tokens carry no project info -- Vision API needs an explicit
    X-Goog-User-Project header to know which project to bill/attribute quota to.
    `gcloud auth application-default set-quota-project` only writes this into the
    credentials file for GOOGLE'S OWN client libraries to read; since we mint the
    raw token ourselves via the CLI, we have to fetch and send it explicitly."""
    import subprocess
    if _quota_project_cache["id"] is not None:
        return _quota_project_cache["id"]
    out = subprocess.run(["gcloud", "config", "get-value", "project"],
                          capture_output=True, text=True, timeout=20)
    proj = out.stdout.strip()
    if out.returncode != 0 or not proj or proj == "(unset)":
        raise VisionAPIDisabled(
            "No gcloud project configured. Run:\n  gcloud config set project YOUR_PROJECT_ID")
    _quota_project_cache["id"] = proj
    return proj

def web_detect(path, tries=3):
    """Real reverse image search via Google Cloud Vision's Web Detection: returns
    actual web pages/entities that match this image, as opposed to Gemini's
    trained-knowledge guess from pixels alone."""
    token = get_access_token()      # raises VisionAPIDisabled if unavailable -- let it propagate
    project = get_quota_project()   # raises VisionAPIDisabled if unavailable -- let it propagate
    with open(path, "rb") as fh: raw = fh.read()
    payload = {"requests": [{"image": {"content": base64.b64encode(raw).decode()},
                              "features": [{"type": "WEB_DETECTION", "maxResults": 12}]}]}
    url = "https://vision.googleapis.com/v1/images:annotate"
    data = json.dumps(payload).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json", "Authorization": "Bearer " + token,
                "X-Goog-User-Project": project})
            with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as r:
                j = json.loads(r.read())
            resp = (j.get("responses") or [{}])[0]
            if "error" in resp:
                raise RuntimeError(resp["error"].get("message", "Vision API error"))
            return resp.get("webDetection", {})
        except urllib.error.HTTPError as e:
            body = e.read()[:400].decode("utf-8", "replace")
            if e.code in (401, 403) and ("SERVICE_DISABLED" in body or "has not been used" in body
                                          or "PERMISSION_DENIED" in body or "CREDENTIALS" in body):
                raise VisionAPIDisabled(body)
            if e.code in (429, 500, 503) and i < tries - 1: time.sleep(2**i + 0.5); continue
            raise RuntimeError("Vision HTTP %s: %s" % (e.code, body))
        except VisionAPIDisabled:
            raise
        except Exception:
            if i < tries - 1: time.sleep(2**i + 0.5); continue
            raise

def format_evidence(wd):
    """Turn a webDetection response into a short evidence block for the Gemini prompt.
    Returns None if there's nothing usable (so we don't pollute the prompt with noise).

    Deliberately requires an actual matched WEB PAGE before sending anything at all.
    Generic content labels/entities (e.g. "Painting", "Dairy cattle", best-guess
    labels like "dairy cow") are NOT identification evidence -- they're just what any
    object detector would say, and testing showed their mere presence in the prompt
    pushes the model toward fabricating a plausible-sounding artist/title instead of
    correctly reporting "nothing found". Better to send no evidence than weak evidence."""
    if not wd: return None
    pages = (wd.get("pagesWithMatchingImages") or [])[:6]
    if not pages:
        return None
    parts = ["Web pages found containing this exact or near-identical image:"]
    for p in pages:
        title = (p.get("pageTitle") or "").strip()
        url = p.get("url", "")
        parts.append('  - "%s" (%s)' % (title, url) if title else "  - %s" % url)
    entities = [e.get("description") for e in (wd.get("webEntities") or [])
                if e.get("description") and e.get("score", 0) > 0.6]
    if entities:
        parts.append("Recognised web entities: " + ", ".join(dict.fromkeys(entities))[:300])
    return "\n".join(parts)

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
    ap.add_argument("--reverse-image-search", action="store_true",
                     help="real reverse image search (Google Cloud Vision Web Detection) before classifying -- "
                          "finds actual matching web pages instead of Gemini guessing from pixels alone")
    ap.add_argument("--no-evidence-gate", action="store_true",
                     help="with --reverse-image-search: trust the model's artist/title claims even when no "
                          "real matching page was found (re-introduces the fabricated-artist-name risk -- see "
                          "classify_verified() docstring; default is to require real evidence for any claim)")
    a = ap.parse_args()
    if not a.key: sys.exit("Set --key or GEMINI_API_KEY.")
    ris_disabled = [False]  # best-effort flag: flips true after the first VisionAPIDisabled, printed once

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
        path = os.path.join(a.folder, fn)
        try:
            evidence, ris_active = None, False
            if a.reverse_image_search and not ris_disabled[0]:
                try:
                    evidence = format_evidence(web_detect(path))
                    ris_active = True
                except VisionAPIDisabled as e:
                    ris_disabled[0] = True
                    print("        ! Reverse image search unavailable, disabling it for the rest of "
                          "this run -- falling back to plain classification.\n          %s"
                          % str(e).replace("\n", "\n          "))
                except Exception:
                    pass  # this one image's search failed -- fall back to plain classification for it only (ris_active stays False)
            if a.no_evidence_gate:
                d = call_gemini(path, a.key, a.model, evidence=evidence)
            else:
                d = classify_verified(path, a.key, a.model, evidence=evidence, ris_active=ris_active)
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
