"""The try-on prompt names the garments, the user's build and the size we'd pick, and stays safe without them."""


def test_prompt_mentions_build_size_and_names():
    from app.ai import prompts

    p = prompts.tryon_prompt(["top", "shoes"], ["Relaxed Fit Tee", "Chunky Sneakers"], "slim", "M")
    assert "Image 2 shows a top (Relaxed Fit Tee)" in p
    assert "Image 3 shows a shoes (Chunky Sneakers)" in p
    assert "slim frame" in p and "size M" in p
    assert "SAME person" in p and "no text" in p


def test_prompt_without_profile_has_no_body_line():
    from app.ai import prompts

    p = prompts.tryon_prompt(["bottom"])
    assert "Image 2 shows a bottom:" in p
    assert "The person has" not in p and "as a size" not in p


def test_prompt_version_bumped_so_old_cache_misses():
    from app.ai import prompts

    assert prompts.TRYON_VERSION == "v3"
