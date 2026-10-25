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

    assert prompts.TRYON_VERSION == "v5"


def test_prompt_is_an_in_place_edit_that_keeps_the_background():
    from app.ai import prompts

    p = prompts.tryon_prompt(["top"])
    assert "white studio" not in p and "remove any mirror" not in p
    assert "Every other pixel stays identical" in p and "ORIGINAL background" in p
    assert "Edit image 1 only where the top is" in p
    assert "segment the person's current top" in p


def test_multi_garment_prompt_lists_each_slot_replacement():
    from app.ai import prompts

    p = prompts.tryon_prompt(["top", "bottom", "shoes"])
    assert "only where the top and the bottom and the shoes are" in p
    assert "Image 2 shows a top: segment the person's current top" in p
    assert "Image 3 shows a bottom: segment the person's current bottom" in p
    assert "Image 4 shows a shoes: segment the person's current shoes" in p
