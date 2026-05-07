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

## Install (Mac)

```bash
git clone git@github.com:<your-username>/<repo>.git mimica
cd mimica
./launch.command
```

`launch.command` creates the venv, installs deps, and starts the app. First run takes about a minute. Then add your MuAPI key in the *Settings* page.

If macOS refuses to open `launch.command`: right-click → **Open** → **Open** once. Or in Terminal: `chmod +x launch.command update.command`.

Needs Python 3.10+ (macOS ships with one, or grab it from [python.org](https://www.python.org/downloads/)) and Git (`xcode-select --install` if missing).

## Install (Windows)

```bash
git clone https://github.com/<your-username>/<repo>.git mimica
cd mimica
launch.bat
```

Needs Python 3.10+ from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install. Git from [git-scm.com](https://git-scm.com/download/win).

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
