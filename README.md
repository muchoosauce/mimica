# Ad Variator

Dashboard app for AI ad production with MuAPI (Claude Sonnet 4.6 + NanoBanana 2 Edit).

Four tools:
- **Generate** — N variations from one reference ad
- **Adapt** — recreate a folder / batch of ads for another brand (product swap + copy/DA/language adaptation)
- **Brands** — reusable Brand DNA presets (name + DNA text + product images)
- **History** — gallery of past runs

Multi-format (1:1, 4:5, 9:16, …) and multi-language output in a single run.

## Share this app

The simplest way to share with a friend:

1. **Zip the project folder**, excluding `.venv/`, `outputs/`, `brands/` and `.env`.
2. Send the zip.

### Mac
1. Unzip anywhere.
2. Double-click **`launch.command`**.
   - First run installs Python venv + deps (~1 min).
   - If macOS refuses to open it: right-click → *Open* → *Open* once. Or in Terminal: `chmod +x launch.command`.
3. Add your MuAPI key in the *Settings* page of the app.

Needs Python 3.10+ installed (macOS ships with one, or get it from [python.org](https://www.python.org/downloads/)).

### Windows
1. Unzip anywhere.
2. Double-click **`launch.bat`**.
   - First run creates the venv + installs deps (~1 min).
   - If SmartScreen warns: *More info* → *Run anyway*.
3. Add your MuAPI key in the *Settings* page of the app.

Needs Python 3.10+ from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install.

### MuAPI key
Each user needs their own — grab one at [muapi.ai](https://muapi.ai). Stored locally in `.env`, never in the zip you share.

## Cost (NanoBanana 2 Edit)

| Resolution | Price / image |
| --- | --- |
| 1k | $0.06 |
| 2k | $0.09 |
| 4k | $0.12 |

Plus one Claude Sonnet call per (ad × language) — a few cents each.

## Output

```
outputs/
└── 20260424_142305_adapt_otae/
    ├── adapt_01_en_1x1.png
    ├── adapt_01_fr_9x16.png
    ├── …
    ├── prompts.txt
    └── report.json
```

Output folder is picked per run in the *Generate* / *Adapt* pages.

## CLI (optional)

The original CLI still works for basic Generate runs:

```bash
python ad_variator.py -i ./ref.jpg -n 5 -r 1k -a 1:1
```
