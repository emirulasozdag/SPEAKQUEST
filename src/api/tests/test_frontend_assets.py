"""Every place and character in the content files has its pictures and its map entry, so new
content never shows a broken image or a place the player cannot click on."""

import re

import pytest

from app.content.schema import CONTENT_DIR, load_content

FRONTEND = CONTENT_DIR.parents[2] / "frontend"
CONTENT = load_content()
LOCATIONS = [location.slug for location in CONTENT.locations]
NPCS = [npc.slug for npc in CONTENT.npcs]


def test_the_frontend_folder_is_where_the_test_expects_it():
    assert (FRONTEND / "pages" / "map.html").is_file()


@pytest.mark.parametrize("slug", LOCATIONS)
def test_each_place_has_a_dialogue_scene(slug):
    scene = FRONTEND / "assets" / "scenes" / f"{slug}.svg"

    assert scene.is_file()
    assert scene.read_text(encoding="utf-8").lstrip().startswith("<svg")


@pytest.mark.parametrize("slug", NPCS)
def test_each_character_has_a_portrait_with_a_text_alternative(slug):
    portrait = FRONTEND / "assets" / "portraits" / f"{slug}.svg"
    npc = next(npc for npc in CONTENT.npcs if npc.slug == slug)

    svg = portrait.read_text(encoding="utf-8")
    assert f"<title>{npc.name}," in svg
    assert 'role="img"' in svg


@pytest.mark.parametrize("slug", LOCATIONS)
def test_each_place_is_on_the_map_with_its_name(slug):
    location = next(location for location in CONTENT.locations if location.slug == slug)
    map_html = (FRONTEND / "pages" / "map.html").read_text(encoding="utf-8")

    entry = re.search(rf'<a class="sq-place sq-{slug}"[^>]*data-location="{slug}"[^>]*>', map_html)
    assert entry, f"no map entry for {slug}"
    assert f'aria-label="{location.name}"' in entry.group(0)
    assert f">{location.name}</text>" in map_html


def test_the_map_has_no_place_the_content_does_not_know():
    map_html = (FRONTEND / "pages" / "map.html").read_text(encoding="utf-8")

    assert set(re.findall(r'data-location="([a-z_]+)"', map_html)) == set(LOCATIONS)


@pytest.mark.parametrize("slug", LOCATIONS)
def test_each_place_has_a_colour_theme(slug):
    css = (FRONTEND / "css" / "main.css").read_text(encoding="utf-8")

    assert re.search(rf"--sq-{slug}:\s*#[0-9a-f]{{6}};", css)
    assert re.search(rf"--sq-{slug}-tint:\s*#[0-9a-f]{{6}};", css)
    assert f".sq-{slug} {{ --sq-line-color: var(--sq-{slug});" in css
