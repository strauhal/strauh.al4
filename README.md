# strauh.al — offline edition

rewritten to run **completely offline**. 

## Where to put this folder

The pages load their images from the **`strauh.al3.1`** folder, which must sit
**right next to this folder, inside the same parent directory**. The pages point
at it with `../strauh.al3.1/…`, so the two folders have to be siblings:

```
some-parent-folder/
├── strauh.al-offline/     ← this folder (the HTML pages + lib/)
│   ├── index.html
│   ├── art.html
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

