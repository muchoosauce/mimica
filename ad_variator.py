#!/usr/bin/env python3
"""CLI: generate N ad variations from a single reference image."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from providers import IMAGE_MODELS, PROVIDERS, get_provider
from providers.prompts import generate_prompts as _gen_prompts


load_dotenv()


C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_RESET = "\033[0m"
C_DIM = "\033[2m"


def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {"INFO": C_CYAN, "OK": C_GREEN, "WARN": C_YELLOW, "ERR": C_RED}
    color = colors.get(level, C_RESET)
    print(f"{C_DIM}[{ts}]{C_RESET} {color}{level:<4}{C_RESET} {msg}", flush=True)


def _generate_image(provider, image_model: str, idx: int, prompt: str, ref_url: str,
                    resolution: str, aspect: str, output_dir: Path) -> dict:
    label = f"var_{idx:02d}"
    log("INFO", f"[{label}] Generating image...")
    try:
        img_url = provider.call_image(
            model=image_model, prompt=prompt, image_urls=[ref_url],
            resolution=resolution, aspect_ratio=aspect, label=label,
        )
        dest = output_dir / f"variation_{idx:02d}.png"
        provider.download(img_url, dest)
        log("OK", f"[{label}] Saved {dest.name}")
        return {"index": idx, "status": "ok", "prompt": prompt,
                "image_url": img_url, "file": dest.name}
    except Exception as e:
        log("ERR", f"[{label}] {e}")
        return {"index": idx, "status": "error", "prompt": prompt, "error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate N ad variations from 1 reference image."
    )
    parser.add_argument("-i", "--image", required=True, help="Path to reference ad image")
    parser.add_argument("-n", "--iterations", type=int, required=True, help="Number of variations (1-15)")
    parser.add_argument("-r", "--resolution", choices=["1k", "2k", "4k"], default="1k")
    parser.add_argument("-a", "--aspect", default="1:1", help="Aspect ratio (e.g. 1:1, 4:5, 9:16, 16:9)")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers for image gen")
    parser.add_argument("--provider", choices=PROVIDERS, default="muapi",
                        help="API provider (default: muapi)")
    parser.add_argument("--model", choices=IMAGE_MODELS, default="nano_banana_2",
                        help="Image model (default: nano_banana_2)")
    args = parser.parse_args()

    if not (1 <= args.iterations <= 15):
        log("ERR", "iterations must be between 1 and 15")
        sys.exit(1)

    provider = get_provider(args.provider, on_log=log)
    if not provider.is_configured():
        env_key = "MUAPI_KEY" if args.provider == "muapi" else "KIE_API_KEY"
        log("ERR", f"{env_key} not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    ref_path = Path(args.image).expanduser().resolve()
    if not ref_path.exists():
        log("ERR", f"Reference image not found: {ref_path}")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    log("INFO", f"Output directory: {out_dir}")
    log("INFO", f"Provider: {provider.display_name} · Model: {args.model}")

    try:
        ref_url = provider.upload_image(ref_path)
    except Exception as e:
        log("ERR", f"Upload failed: {e}")
        sys.exit(1)

    try:
        prompts = _gen_prompts(provider, ref_url, args.iterations)
    except Exception as e:
        log("ERR", f"Prompt generation failed: {e}")
        sys.exit(1)

    prompts_file = out_dir / "prompts.txt"
    with open(prompts_file, "w") as f:
        for i, p in enumerate(prompts, 1):
            f.write(f"=== Variation {i:02d} ===\n{p}\n\n")
    log("OK", f"Wrote {prompts_file.name}")

    log("INFO", f"Generating {len(prompts)} images with {args.workers} workers...")
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_generate_image, provider, args.model,
                        i + 1, p, ref_url, args.resolution, args.aspect, out_dir): i
            for i, p in enumerate(prompts)
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r["index"])

    report = {
        "timestamp": ts,
        "reference": str(ref_path),
        "reference_url": ref_url,
        "params": {
            "iterations": args.iterations,
            "resolution": args.resolution,
            "aspect_ratio": args.aspect,
            "workers": args.workers,
            "provider": provider.name,
            "image_model": args.model,
            "llm_model": "claude-sonnet-4-6",
        },
        "results": results,
    }
    report_file = out_dir / "report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = len(results) - ok_count
    log("OK", f"Done: {ok_count} succeeded, {err_count} failed → {out_dir}")
    if err_count:
        sys.exit(2)


if __name__ == "__main__":
    main()
