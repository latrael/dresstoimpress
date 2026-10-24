"""Run the closet tagger on a folder of clothing photos and print what it saw.

    python -m scripts.eval_tagger ~/Desktop/closet-photos

Done-when for the tagger: 10 real photos come back with sensible tags.
Uses Claude (or Gemini if no Anthropic key / out of credits). Saves nothing.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ["ALLOW_FILE_URLS"] = "1"

from app.ai import prompts  # noqa: E402
from app.ai.llm import CLAUDE_TAG_MODEL, GEMINI_TEXT_MODEL, ai_json, text_mock, text_provider  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    if text_mock():
        sys.exit("Set ANTHROPIC_API_KEY or GEMINI_API_KEY and unset MOCK_AI to run the real tagger.")
    folder = Path(sys.argv[1]).expanduser()
    photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
    if not photos:
        sys.exit(f"no images in {folder}")

    model = CLAUDE_TAG_MODEL if text_provider() == "claude" else GEMINI_TEXT_MODEL
    print(f"{text_provider()} ({model}, falls back to Gemini if Claude fails), {len(photos)} photos\n")
    print(f"{'file':<28} {'category':<10} {'color':<14} {'pattern':<8} {'form':<4} tags")
    for p in photos:
        t = time.time()
        try:
            r = ai_json(prompts.TAGGER, image_url=p.resolve().as_uri(), max_tokens=300, model=CLAUDE_TAG_MODEL)
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
