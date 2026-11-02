"""Browser smoke tests for the main game flow (#63): the real frontend against the real API.

Only the AI is faked. Each test starts from an empty database; what a test does not check itself
(an account, a finished quest) is prepared through the API first. Selectors use labels and roles.
"""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.browser.game import FIRST_MESSAGE, FIRST_REPLY, PASSWORD, SECOND_MESSAGE, SECOND_REPLY, log_in

pytestmark = pytest.mark.browser

EMAIL = "player@example.com"


def finish_first_quest(game_api, use_ai) -> None:
    """Meet Your Neighbor done through the API: one present simple mistake, Alex helped."""
    use_ai(FIRST_REPLY, SECOND_REPLY)
    game_api.register_with_character()
    game_api.start("meet_your_neighbor")
    game_api.say(FIRST_MESSAGE)
    game_api.say(SECOND_MESSAGE)
    game_api.decide("meet_your_neighbor", "help_alex_move", "help")
    game_api.complete("meet_your_neighbor")


def test_register_log_in_create_a_character_and_see_the_dashboard(page: Page, console):
    page.goto("/pages/register.html")
    page.get_by_label("Email").fill(EMAIL)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_label("Repeat password").fill(PASSWORD)
    page.get_by_role("button", name="Create account").click()
    # A new account goes straight to character creation
    expect(page).to_have_url(re.compile(r"/pages/character\.html$"))

    # Log in again by hand: a player without a character is sent to character creation
    log_in(page, EMAIL)
    expect(page).to_have_url(re.compile(r"/pages/character\.html$"))
    page.get_by_label("Character name").fill("Deniz")
    page.get_by_label("Your English level").select_option("A2")
    page.get_by_role("button", name="Move to the city").click()

    expect(page).to_have_url(re.compile(r"/pages/dashboard\.html$"))
    expect(page.get_by_role("heading", name="Good to see you, Deniz")).to_be_visible()
    expect(page.get_by_text("Level 1 · A2")).to_be_visible()
    expect(page.get_by_text("0 / 50 XP to level 2")).to_be_visible()
    # No active quest yet: the Adaptive Quest Engine suggests the first one
    active = page.locator("section", has=page.get_by_role("heading", name="Active quest"))
    expect(active.get_by_text("Suggested next quest")).to_be_visible()
    expect(active.get_by_role("heading", name="Meet Your Neighbor · Linden House")).to_be_visible()
    expect(page.get_by_text("Server online")).to_be_visible()
    assert console.errors == []


def test_pick_a_place_on_the_map_and_start_a_quest(page: Page, console, game_api):
    game_api.register_with_character()
    log_in(page, EMAIL)
    expect(page).to_have_url(re.compile(r"/pages/dashboard\.html$"))

    page.get_by_role("link", name="Continue adventure").click()
    expect(page).to_have_url(re.compile(r"/pages/map\.html$"))
    page.get_by_role("button", name=re.compile(r"^Linden House")).click()
    place = page.locator("#place-detail")
    expect(place.get_by_role("heading", name="Linden House")).to_be_visible()
    expect(place.get_by_text("Alex", exact=True)).to_be_visible()
    expect(place.get_by_role("heading", name="Meet Your Neighbor")).to_be_visible()
    place.get_by_role("button", name="Start quest").click()

    # The dialogue page opens with the NPC's first line and the quest's goals
    expect(page).to_have_url(re.compile(r"/pages/dialogue\.html\?quest=\d+$"))
    expect(page.get_by_role("heading", name="Meet Your Neighbor")).to_be_visible()
    expect(page.get_by_role("log").get_by_text("You must be the new neighbour")).to_be_visible()
    expect(page.get_by_text("0 of 3 goals done")).to_be_visible()

    # The dashboard now shows the quest in progress
    page.get_by_role("link", name="Dashboard").click()
    active = page.locator("section", has=page.get_by_role("heading", name="Active quest"))
    expect(active.get_by_role("heading", name="Meet Your Neighbor")).to_be_visible()
    expect(active.get_by_text("Goals: 0 of 3 done · Reward: 50 XP")).to_be_visible()
    expect(active.get_by_role("link", name="Open conversation")).to_be_visible()
    assert console.errors == []


def test_talk_to_the_npc_make_a_choice_and_complete_the_quest(page: Page, console, game_api, use_ai):
    game_api.register_with_character()
    quest = game_api.start("meet_your_neighbor")
    use_ai(FIRST_REPLY, SECOND_REPLY)
    log_in(page, EMAIL)
    expect(page).to_have_url(re.compile(r"/pages/dashboard\.html$"))
    page.get_by_role("link", name="Open conversation").click()
    expect(page).to_have_url(re.compile(rf"/pages/dialogue\.html\?quest={quest['id']}$"))

    conversation = page.get_by_role("log")
    reply = page.get_by_label("Your reply")
    reply.fill(FIRST_MESSAGE)
    reply.press("Enter")
    expect(conversation.get_by_text("Nice to meet you, Deniz!")).to_be_visible()
    expect(conversation.get_by_text("✓ Alex understood you.")).to_be_visible()
    expect(reply).to_have_value("")

    # The correction is closed until the player opens it
    badge = conversation.get_by_role("button", name="1 correction")
    expect(badge).to_have_attribute("aria-expanded", "false")
    corrections = conversation.get_by_role("list", name="1 correction")
    expect(corrections).to_be_hidden()
    badge.click()
    expect(badge).to_have_attribute("aria-expanded", "true")
    expect(corrections).to_be_visible()
    expect(corrections.get_by_text("my name is Deniz")).to_be_visible()
    expect(page.get_by_text("2 of 3 goals done")).to_be_visible()

    reply.fill(SECOND_MESSAGE)
    reply.press("Enter")
    expect(conversation.get_by_text("That sounds healthy!")).to_be_visible()
    expect(page.get_by_text("3 of 3 goals done")).to_be_visible()

    # All goals are done, but the story decision comes before "Complete quest"
    complete = page.get_by_role("button", name="Complete quest")
    expect(page.get_by_text('Make your choice in "Your choice"')).to_be_visible()
    expect(complete).to_be_hidden()
    choice = page.get_by_role("group", name="Do you offer to help?")
    choice.get_by_role("button", name="Help Alex carry the boxes upstairs.").click()
    expect(choice.get_by_text("You chose: Help Alex carry the boxes upstairs.")).to_be_visible()

    complete.click()
    expect(page.get_by_text("Quest complete! +50 XP")).to_be_visible()
    expect(page.get_by_text("Level up! You are now level 2 with 50 XP.")).to_be_visible()
    summary = page.locator("section", has=page.get_by_role("heading", name="Quest summary"))
    expect(summary.get_by_text("Alex understood 2 of your 2 messages.")).to_be_visible()
    expect(summary.get_by_text("Most common mistake: Present simple (1 in total).")).to_be_visible()
    expect(summary.get_by_text("my name are Deniz")).to_be_visible()
    expect(reply).to_be_disabled()
    assert console.errors == []


def test_quest_journal_tabs_and_the_recommended_quest(page: Page, console, game_api, use_ai):
    finish_first_quest(game_api, use_ai)
    recommended = next(quest for quest in game_api.call("GET", "/quests").json() if quest["recommended"])
    log_in(page, EMAIL)
    expect(page).to_have_url(re.compile(r"/pages/dashboard\.html$"))
    page.get_by_role("link", name="Quest journal").click()

    active_tab = page.get_by_role("tab", name=re.compile(r"^Active"))
    done_tab = page.get_by_role("tab", name=re.compile(r"^Completed"))
    locked_tab = page.get_by_role("tab", name=re.compile(r"^Locked"))
    expect(active_tab).to_have_text("Active 3")
    expect(done_tab).to_have_text("Completed 1")
    expect(locked_tab).to_have_text("Locked 1")

    # The recommended quest comes first, with the reason the Adaptive Quest Engine gives
    expect(active_tab).to_have_attribute("aria-selected", "true")
    active = page.get_by_role("tabpanel", name=re.compile(r"^Active"))
    first = active.get_by_role("article").first
    expect(first.get_by_role("heading", name=recommended["title"])).to_be_visible()
    expect(first.get_by_text("Why this quest was suggested for you")).to_be_visible()
    expect(first.get_by_text(recommended["recommendation_reason"])).to_be_visible()
    expect(active.get_by_role("article")).to_have_count(3)

    done_tab.click()
    expect(done_tab).to_have_attribute("aria-selected", "true")
    done = page.get_by_role("tabpanel", name=re.compile(r"^Completed"))
    expect(done.get_by_role("heading", name="Meet Your Neighbor")).to_be_visible()
    expect(done.get_by_role("link", name="Read the conversation")).to_be_visible()

    locked_tab.click()
    expect(locked_tab).to_have_attribute("aria-selected", "true")
    locked = page.get_by_role("tabpanel", name=re.compile(r"^Locked"))
    expect(locked.get_by_role("heading", name="The Missing Backpack")).to_be_visible()
    expect(locked.get_by_text("What opens it:")).to_be_visible()
    expect(active).to_be_hidden()
    assert console.errors == []


def test_learning_progress_shows_what_the_player_practised(page: Page, console, game_api, use_ai):
    finish_first_quest(game_api, use_ai)
    log_in(page, EMAIL)
    expect(page).to_have_url(re.compile(r"/pages/dashboard\.html$"))
    page.get_by_role("link", name="Progress").click()
    expect(page).to_have_url(re.compile(r"/pages/progress\.html$"))

    skills = page.locator("section", has=page.get_by_role("heading", name="Skills"))
    present = skills.get_by_role("listitem").filter(has_text="Present simple")
    expect(present.get_by_text("1 correct, 1 mistake")).to_be_visible()
    expect(present.get_by_role("progressbar", name="Present simple score")).to_be_visible()

    mistakes = page.locator("section", has=page.get_by_role("heading", name="Mistakes you make most"))
    expect(mistakes.get_by_text("Present simple · 1 time")).to_be_visible()
    expect(mistakes.get_by_text("my name are Deniz")).to_be_visible()
    expect(mistakes.get_by_text("my name is Deniz")).to_be_visible()
    expect(mistakes.get_by_text("Meet Your Neighbor")).to_be_visible()

    expect(page.get_by_role("region", name="What to practise next")).to_be_visible()
    expect(page.get_by_role("heading", name="Your skills over time")).to_be_visible()
    expect(page.get_by_text("Nothing to show yet")).to_be_hidden()
    assert console.errors == []
