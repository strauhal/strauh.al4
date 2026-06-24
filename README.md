# strauh.al — offline edition

These are the strauh.al HTML pages rewritten to run **completely offline**. With
the Wi-Fi turned off, every page loads, every internal link works, and every
image that you have locally is displayed. Nothing is fetched from the web.

## Where to put this folder

The pages load their images from the **`strauh.al3.1`** folder, which must sit
**right next to this folder, inside the same parent directory**. The pages point
at it with `../strauh.al3.1/…`, so the two folders have to be siblings:

```
some-parent-folder/
├── strauh.al-offline/     ← this folder (the HTML pages + lib/)
│   ├── index.html
│   ├── art.html
│   ├── nyce/ …
│   └── lib/               ← bundled JavaScript libraries (three.js, etc.)
└── strauh.al3.1/          ← the images (must be alongside, same parent)
    ├── 1500s/ 1600s/ …
    ├── 2023_downloadsfolder/ …
    └── …
```

If you move or rename `strauh.al3.1`, or put it anywhere other than directly
beside `strauh.al-offline`, the images will stop loading. Keep both folders
together and the names exactly as shown.

## How to use it

Open **`index.html`** in any web browser (double-click it, or drag it into a
browser window). From there every link navigates locally between the pages.

> Tip: a few data-heavy pages read local files with `fetch()`, which some
> browsers block when opening a file directly (`file://`). If a page looks empty,
> serve the folder with a tiny local web server instead — from inside
> `strauh.al-offline` run:
> ```
> python3 -m http.server
> ```
> then visit `http://localhost:8000`. This needs no internet; it just serves the
> local files. (Chrome is the strictest about `file://`; Firefox/Safari are
> usually fine opening the files directly.)

## What was changed

- **Images** — every image (≈14,000 references) now points to the local
  `../strauh.al3.1/…` copy instead of GitHub.
- **Navigation** — links between pages (`/art`, `/nyce/banquet`, …) were turned
  into local `.html` links that work from any folder depth.
- **Web hyperlinks removed** — every outbound link to the web (Wikipedia, news
  sites, etc.) was disabled, so nothing on these pages points to the internet.
  The only things that still point anywhere are local images. Clicking an image
  thumbnail opens the local full-size image.
- **JavaScript libraries** — the 3D / interactive pages used to load three.js,
  OrbitControls, Tween.js and Tailwind from CDNs. Local copies are bundled in
  the `lib/` folder, so those pages work with the Wi-Fi off too.
- **Icons / manifest / scripts** — favicons, `site.webmanifest`, `style.css` and
  `script.js` were switched to relative paths.

## The few things that genuinely need the internet

These depend on outside services and cannot be made to work offline; they fail
quietly (a blank box) when there's no connection, and the rest of the page is
unaffected:

- **The two Luma 3D scan embeds** on `3d_scans.html` and `grandmas_house.html`
  (hosted by lumalabs.ai).
- **Embedded YouTube/Vimeo videos** (e.g. on the video pages) — the page loads,
  but a video only plays when you're online.
- **Images that aren't present in `strauh.al3.1`.** A handful of older pages
  reference images that simply aren't in your local image folder; those spots
  stay blank. Everything that exists in `strauh.al3.1` displays.

## `lib/` folder

Bundled, self-contained copies of the libraries the pages use. Don't delete it —
the 3D and interactive pages need it. It contains nothing that calls out to the
web.
