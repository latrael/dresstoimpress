"""Shop the fit: fixes for the mismatches Nabil saw on real Fit Check photos (Sat 2:45).
Imports stay inside the tests (like the rest of the suite) so test_ai can point DATA_DIR first."""


def _p(pid, name, category="top", colors=("black",)):
    return {"id": pid, "name": name, "category": category, "colors": list(colors), "retailer": "hm"}


def test_collared_shirt_gets_shirts_not_graphic_tees():
    from app.ai.finder import MIN_SCORE, best_matches, match_score  # noqa: F401

    tag = {"label": "striped collared shirt", "category": "top", "color": "blue"}
    tee = _p("t", "Oversized Printed T-shirt", colors=["blue"])
    shirt = _p("s", "Regular Fit Striped Oxford Shirt", colors=["blue/striped"])
    assert match_score(tag, tee) == 0
    assert best_matches(tag, [tee, shirt]) == [shirt]


def test_tees_still_match_tees_and_baby_tees_stay_cropped_friendly():
    from app.ai.finder import MIN_SCORE, best_matches, match_score  # noqa: F401

    tag = {"label": "white baby tee", "category": "top", "color": "white"}
    assert match_score(tag, _p("c", "Cropped baby tee", colors=["white"])) >= MIN_SCORE
    assert match_score({"label": "black t-shirt", "category": "top", "color": "black"},
                       _p("t", "Regular Fit T-shirt")) >= MIN_SCORE


def test_v_neck_sweater_prefers_a_plain_sweater_over_an_off_shoulder_one():
    from app.ai.finder import MIN_SCORE, best_matches, match_score  # noqa: F401

    tag = {"label": "burgundy v-neck sweater", "category": "top", "color": "burgundy"}
    off = _p("o", "Off-the-shoulder Rib-knit Sweater", colors=["burgundy"])
    plain = _p("p", "Fine-knit V-neck Sweater", colors=["burgundy"])
    assert match_score(tag, plain) > match_score(tag, off)
    assert best_matches(tag, [off, plain])[0] == plain
    # but a post that IS off-shoulder still finds it
    assert best_matches({"label": "off-shoulder sweater", "category": "top", "color": "burgundy"}, [off, plain])[0] == off


def test_watch_and_bracelet_never_get_necklaces():
    from app.ai.finder import MIN_SCORE, best_matches, match_score  # noqa: F401

    necklace = _p("n", "Pendant Necklace", category="accessory", colors=["gold"])
    bracelet = _p("b", "Chunky Bracelet", category="accessory", colors=["gold"])
    watch = {"label": "silver wristwatch", "category": "accessory", "color": "silver"}
    assert best_matches(watch, [necklace, bracelet]) == []
    assert best_matches({"label": "gold bracelet", "category": "accessory", "color": "gold"},
                        [necklace, bracelet]) == [bracelet]
