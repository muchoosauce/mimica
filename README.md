# Mimica

Desktop dashboard for AI ad production. MuAPI (or Kie) under the hood — NanoBanana 2 / Pro / GPT Image 2 for stills, Kling 3 for videos, Claude Sonnet 4.6 for prompt engineering.

Six workflows:
- **Funnel Ads** — TOF / MOF / BOF static ads from a Brand DNA, picked segment-by-segment
- **Generate** — N variations from one reference ad
- **Adapt** — recreate a folder / batch of ads for another brand (product swap + copy/DA/language)
- **Fix** — surgical edits on a single output (size, position, copy, color drift)
- **B-Roll** — UGC-style still B-rolls + Kling 3 animation
- **Brands** — reusable Brand DNA presets (name + DNA text + product images)
- **History** — gallery of past runs

Multi-format (1:1, 4:5, 9:16, …) and multi-language output in a single run.

## Install (Mac) — one-click

Double-click `install.command`. It auto-installs Xcode CLI Tools → Homebrew → Python 3.12 → clones the repo → sets up the venv → launches the app. 5-10 min on a fresh Mac, idempotent (safe to re-run).

Or manually if you already have Python 3.10+ and Git:
```bash
git clone https://github.com/muchoosauce/mimica.git
cd mimica
./launch.command
```

If macOS refuses to open `launch.command`: right-click → **Open** → **Open** once.

## Install (Windows 10/11) — one-click

Double-click `install.bat`. It uses winget to auto-install Python 3.12 + Git if missing, clones the repo, sets up the venv, launches the app. Same idempotent behavior as the Mac installer. Needs Windows 10 1809+ for winget (or Windows 11).

Or manually if you already have Python 3.10+ and Git:
```cmd
git clone https://github.com/muchoosauce/mimica.git
cd mimica
launch.bat
```

## Updates

When the maintainer pushes a new version, run:

```bash
./update.command   # macOS — double-clickable
```

It runs `git pull` (refusing if you have local changes), refreshes Python deps if `requirements.txt` changed, and relaunches the app. **Your `.env`, `brands/` and `outputs/` are gitignored — they survive every update.**

Manual flow if you prefer the terminal:
```bash
git pull
./launch.command
```

## API keys

Stored locally in `.env` (gitignored, never pushed). You can add them via the in-app *Settings* page — no terminal needed.

- **MuAPI** — image gen + LLM. Get one at [muapi.ai](https://muapi.ai).
- **Kie.ai** — alternative provider, same models. Get one at [kie.ai](https://kie.ai).
- **Anthropic** — required only for the Brand DNA Generator.

## Cost (rough)

| Model | Resolution | Price / image |
| --- | --- | --- |
| NanoBanana 2 (MuAPI) | 1k / 2k / 4k | $0.06 / $0.09 / $0.12 |
| NanoBanana Pro (MuAPI) | 1k / 2k / 4k | $0.10 / $0.13 / $0.18 |
| GPT Image 2 (MuAPI) | any | $0.09 |
| Kling 3 Standard (5s) | — | ~$0.30 |
| Kling 3 Pro (5s) | — | ~$0.90 |

Plus one Claude Sonnet call per LLM step — a few cents each.

## Output layout

```
outputs/
├── 20260507_135546_funnel_mof_mona/
│   ├── funnel_mof_01.png
│   ├── …
│   ├── prompts.txt          # full LLM output (metadata + prompts)
│   └── report.json
├── 20260424_142305_adapt_otae/
│   └── …
└── 20260507_011038_broll_videos_mona/
    └── broll_01_ecu.mp4
```

Output folder is picked per run from each workflow page.

## CLI (optional)

The original CLI still works for basic Generate runs:

```bash
python ad_variator.py -i ./ref.jpg -n 5 -r 1k -a 1:1
```
