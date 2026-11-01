// Dashboard: the player's character, level and XP, the active quest and completed quests.
// Everything shown here comes from the API; nothing is calculated in the browser.

import {
  ApiError,
  getActiveQuest,
  getLocations,
  getProfile,
  getQuests,
  getStoryEnding,
  handleApiError,
} from "../api.js";
import { showAlert } from "../components/form.js";
import {
  ENDING_PAGE,
  JOURNAL_PAGE,
  MAP_PAGE,
  RECOMMENDATION_HEADING,
  avatarUrl,
  dialogueUrl,
  portraitUrl,
} from "../components/quests.js";
import { CHARACTER_PAGE } from "../session.js";

const loading = document.querySelector("#dashboard-loading");
const content = document.querySelector("#dashboard-content");
const alertBox = document.querySelector("#dashboard-alert");

function showProfile(profile) {
  document.querySelector("#player-avatar").src = avatarUrl(profile.avatar);
  document.querySelector("#player-name").textContent = `Good to see you, ${profile.character_name}`;
  document.querySelector("#player-level").textContent = `Level ${profile.level} · ${profile.english_level}`;

  const bar = document.querySelector("#xp-bar");
  const text = document.querySelector("#xp-text");
  const { xp_into_level: into, xp_needed_for_next: needed } = profile;
  if (typeof into !== "number") {
    // The API does not report level progress, so only the total is shown
    bar.hidden = true;
    text.textContent = `${profile.xp} XP`;
  } else if (needed === null) {
    bar.hidden = true;
    text.textContent = `${profile.xp} XP · highest level reached`;
  } else {
    bar.setAttribute("aria-valuenow", String(into));
    bar.setAttribute("aria-valuemax", String(needed));
    bar.firstElementChild.style.width = `${Math.min(100, (into / needed) * 100)}%`;
    text.textContent = `${into} / ${needed} XP to level ${profile.level + 1}`;
  }
}

// With no active quest: the Adaptive Quest Engine's suggestion, or the ending once the story is over
function showNextStep(body, recommended, places, ending) {
  if (recommended) {
    const place = places.get(recommended.location_slug);
    body.innerHTML = `
      <p class="small text-secondary mb-1">Suggested next quest</p>
      <h3></h3>
      <div class="sq-recommended mb-3">
        <p class="small fw-bold mb-1"></p>
        <p class="quest-reason mb-0"></p>
      </div>
      <div class="d-flex flex-wrap gap-2">
        <a class="btn btn-outline-primary" href="${MAP_PAGE}">Find it on the city map</a>
        <a class="btn btn-link" href="${JOURNAL_PAGE}">All quests</a>
      </div>`;
    body.querySelector("h3").textContent = [recommended.title, place?.name].filter(Boolean).join(" · ");
    body.querySelector(".sq-recommended .fw-bold").textContent = RECOMMENDATION_HEADING;
    body.querySelector(".quest-reason").textContent = recommended.recommendation_reason;
  } else if (ending) {
    body.innerHTML = `
      <p class="small text-secondary mb-1">Your story has ended</p>
      <h3></h3>
      <p class="ending-summary"></p>
      <a class="btn btn-primary" href="${ENDING_PAGE}">See how your story ended</a>`;
    body.querySelector("h3").textContent = ending.title;
    body.querySelector(".ending-summary").textContent = ending.summary;
  } else {
    body.innerHTML = `
      <p>You have no active quest right now. Pick a place on the city map to start one.</p>
      <a class="btn btn-outline-primary" href="${MAP_PAGE}">Open the city map</a>`;
  }
}

function showActiveQuest(quest, places, recommended, ending) {
  const panel = document.querySelector("#active-quest");
  const body = document.querySelector("#active-quest-body");
  const continueButton = document.querySelector("#continue-button");

  if (!quest) {
    showNextStep(body, recommended, places, ending);
    continueButton.href = ending && !recommended ? ENDING_PAGE : MAP_PAGE;
    return;
  }

  const place = places.get(quest.location_slug);
  const npc = place?.npcs.find((item) => item.slug === quest.npc_slug);
  panel.classList.add(`sq-${quest.location_slug}`);
  body.innerHTML = `
    <h3></h3>
    <p class="quest-summary"></p>
    <div class="d-flex align-items-center gap-2 mb-3">
      <img class="sq-portrait sq-portrait-sm sq-${quest.location_slug}" src="${portraitUrl(quest.npc_slug)}" alt="">
      <p class="mb-0 small quest-where"></p>
    </div>
    <p class="small text-secondary quest-meta"></p>
    <a class="btn btn-outline-primary" href="${dialogueUrl(quest.id)}">Open conversation</a>`;
  body.querySelector("h3").textContent = quest.title;
  body.querySelector(".quest-summary").textContent = quest.summary;
  body.querySelector(".quest-where").textContent = [npc?.name, place?.name].filter(Boolean).join(" · ");
  const done = quest.objectives.filter((objective) => objective.met).length;
  body.querySelector(".quest-meta").textContent =
    `Goals: ${done} of ${quest.objectives.length} done · Reward: ${quest.reward_xp} XP`;
  continueButton.href = dialogueUrl(quest.id);
}

function showCompleted(quests, places) {
  const list = document.querySelector("#completed-list");
  const completed = quests
    .filter((quest) => quest.status === "completed")
    .sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? ""));

  if (!completed.length) {
    list.innerHTML = '<li class="text-secondary">No quests completed yet. Your first one is waiting in the city.</li>';
    return;
  }
  for (const quest of completed) {
    const item = document.createElement("li");
    item.className = "sq-skill-row d-flex justify-content-between gap-3";
    const name = document.createElement("span");
    name.textContent = [quest.title, places.get(quest.location_slug)?.name].filter(Boolean).join(" · ");
    const reward = document.createElement("span");
    reward.className = "text-secondary text-nowrap";
    reward.textContent = `+${quest.reward_xp} XP`;
    item.append(name, reward);
    list.append(item);
  }
}

async function loadDashboard() {
  try {
    const [profile, activeQuest, quests, locations] = await Promise.all([
      getProfile(),
      getActiveQuest(),
      getQuests(),
      getLocations(),
    ]);
    const places = new Map(locations.map((place) => [place.slug, place]));
    showProfile(profile);
    const recommended = quests.find((item) => item.recommended);
    // Only needed when there is nothing left to play
    const ending = activeQuest || recommended ? null : await getStoryEnding();
    showActiveQuest(activeQuest, places, recommended, ending);
    showCompleted(quests, places);
    content.hidden = false;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // No character yet: creating one is the first step of the game
      window.location.replace(CHARACTER_PAGE);
      return;
    }
    showAlert(alertBox, "Your adventure could not be loaded. Refresh the page to try again.");
    handleApiError(error);
  } finally {
    loading.hidden = true;
  }
}

loadDashboard();
