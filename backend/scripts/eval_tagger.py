"""Run the closet tagger on a folder of clothing photos and print what it saw.

    python -m scripts.eval_tagger ~/Desktop/closet-photos

Done-when for the tagger: 10 real photos come back with sensible tags.
Uses the real Claude model (needs ANTHROPIC_API_KEY, MOCK_AI unset). Saves nothing.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ["ALLOW_FILE_URLS"] = "1"

from app.ai import prompts  # noqa: E402
from app.ai.llm import CLAUDE_MODEL, claude_json, mock_mode  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if mock_mode("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY and unset MOCK_AI to run the real tagger.")
    folder = Path(sys.argv[1]).expanduser()
    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
    if not photos:
        sys.exit(f"no images in {folder}")

    print(f"model {CLAUDE_MODEL}, {len(photos)} photos\n")
    print(f"{'file':<28} {'category':<10} {'color':<14} {'pattern':<8} {'form':<4} tags")
    for p in photos:
        t = time.time()
        try:
            r = claude_json(prompts.TAGGER, image_url=p.resolve().as_uri(), max_tokens=300)
        except Exception as e:  # noqa: BLE001
            print(f"{p.name[:27]:<28} ERROR {e}")
            continue
        if r.get("error"):
            print(f"{p.name[:27]:<28} {r['error']}")
            continue
        print(f"{p.name[:27]:<28} {r.get('category', '?'):<10} {str(r.get('color', '?'))[:13]:<14} "
              f"{r.get('pattern', '?'):<8} {r.get('formality', '?')!s:<4} "
              f"{', '.join(r.get('style_tags', []))}  ({time.time() - t:.1f}s)")


if __name__ == "__main__":
    main()
