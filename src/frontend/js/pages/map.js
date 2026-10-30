// City map: draws each place's state from the API, lists its characters and quests,
// and starts a quest. Quest status and locks are decided by the backend only.

import { ApiError, getLocations, handleApiError, startQuest } from "../api.js";
import { showAlert } from "../components/form.js";
import { QUEST_STATUS_LABELS, dialogueUrl, portraitUrl } from "../components/quests.js";

const alertBox = document.querySelector("#map-alert");
const loading = document.querySelector("#places-loading");
const list = document.querySelector("#places-list");
const detail = document.querySelector("#place-detail");

let places = new Map();

// One state per place, shown on the map with a style and always with text as well
function placeState(place) {
  const statuses = place.quests.map((quest) => quest.status);
  const open = statuses.filter((status) => status === "available").length;
  if (statuses.includes("active")) return { key: "active", text: "Quest in progress" };
  if (open) return { key: "open", text: open === 1 ? "1 quest open" : `${open} quests open` };
  if (statuses.length && statuses.every((status) => status === "completed")) {
    return { key: "done", text: "All quests done" };
  }
  if (statuses.length && statuses.every((status) => status === "locked")) {
    return { key: "locked", text: "Locked" };
  }
  // Some quests done, the rest still locked
  return { key: "open", text: "More quests later" };
}

function drawMap() {
  document.querySelectorAll(".sq-place[data-location]").forEach((marker) => {
    const place = places.get(marker.dataset.location);
    // A drawn place that the API does not know about is not shown
    marker.style.display = place ? "" : "none";
    if (!place) return;
    const state = placeState(place);
    marker.classList.toggle("is-locked", state.key === "locked");
    marker.classList.toggle("is-active", state.key === "active");
    marker.querySelector("[data-place-status]").textContent = state.text;
    marker.setAttribute("aria-label", `${place.name}, ${state.text}`);
  });
}

function drawList() {
  list.replaceChildren();
  if (!places.size) {
    list.innerHTML = '<p class="text-secondary mb-0">The city has no places yet. Please try again later.</p>';
    return;
  }
  for (const place of places.values()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `sq-panel sq-line-tag sq-place-button sq-${place.slug}`;
    button.dataset.location = place.slug;
    button.innerHTML = '<h3 class="mb-1"></h3><p class="mb-0 small text-secondary"></p>';
    button.querySelector("h3").textContent = place.name;
    const people = place.npcs.map((npc) => npc.name).join(", ");
    button.querySelector("p").textContent = [people, placeState(place).text].filter(Boolean).join(" · ");
    list.append(button);
  }
}

function questItem(quest) {
  const item = document.createElement("li");
  item.className = "sq-skill-row";
  item.innerHTML = `
    <div class="d-flex justify-content-between align-items-start gap-2">
      <h4 class="h6 mb-1"></h4>
      <span class="sq-quest-status" data-status="${quest.status}"></span>
    </div>
    <p class="small mb-2"></p>`;
  item.querySelector("h4").textContent = quest.title;
  item.querySelector(".sq-quest-status").textContent = QUEST_STATUS_LABELS[quest.status] ?? quest.status;
  item.querySelector("p").textContent = quest.summary;

  if (quest.status === "available") {
    const start = document.createElement("button");
    start.type = "button";
    start.className = "btn btn-sm btn-primary";
    start.dataset.questId = quest.id;
    start.textContent = "Start quest";
    item.append(start);
  } else if (quest.status === "active") {
    const link = document.createElement("a");
    link.className = "btn btn-sm btn-outline-primary";
    link.href = dialogueUrl(quest.id);
    link.textContent = "Continue conversation";
    item.append(link);
  } else if (quest.status === "locked") {
    item.insertAdjacentHTML("beforeend", '<p class="small text-secondary mb-0">Unlocks as the story moves on.</p>');
  }
  return item;
}

function showPlace(slug) {
  const place = places.get(slug);
  if (!place) return;

  detail.className = `sq-panel sq-line-tag mb-4 sq-${place.slug}`;
  detail.innerHTML = `
    <div id="place-alert" role="alert" hidden></div>
    <h2 class="h4 mb-2"></h2>
    <p class="place-description"></p>
    <h3 class="sq-panel-title mb-2">People here</h3>
    <ul class="list-unstyled d-grid gap-2 mb-3 place-npcs"></ul>
    <h3 class="sq-panel-title mb-0">Quests</h3>
    <ul class="list-unstyled mb-0 place-quests"></ul>`;
  detail.querySelector("h2").textContent = place.name;
  detail.querySelector(".place-description").textContent = place.description;

  const npcs = detail.querySelector(".place-npcs");
  for (const npc of place.npcs) {
    const item = document.createElement("li");
    item.className = "d-flex align-items-center gap-2";
    item.innerHTML = `<img class="sq-portrait sq-portrait-sm sq-${place.slug}" src="${portraitUrl(npc.slug)}" alt=""><span><strong></strong> · <span class="npc-role"></span></span>`;
    item.querySelector("strong").textContent = npc.name;
    item.querySelector(".npc-role").textContent = npc.role;
    npcs.append(item);
  }

  const quests = detail.querySelector(".place-quests");
  if (!place.quests.length) {
    quests.innerHTML = '<li class="text-secondary small pt-2">No quests here yet.</li>';
  }
  place.quests.forEach((quest) => quests.append(questItem(quest)));

  detail.hidden = false;
  detail.focus();
}

async function onStartQuest(button) {
  button.disabled = true;
  button.textContent = "Starting…";
  try {
    const quest = await startQuest(button.dataset.questId);
    window.location.assign(dialogueUrl(quest.id));
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      // For example, another quest is already active: the API explains why
      showAlert(detail.querySelector("#place-alert"), error.message, "warning");
    } else {
      handleApiError(error);
    }
    button.disabled = false;
    button.textContent = "Start quest";
  }
}

document.addEventListener("click", (event) => {
  const start = event.target.closest("button[data-quest-id]");
  if (start) {
    onStartQuest(start);
    return;
  }
  const trigger = event.target.closest(".sq-place[data-location], .sq-place-button");
  if (trigger) {
    event.preventDefault();
    showPlace(trigger.dataset.location);
  }
});

async function loadMap() {
  try {
    const locations = await getLocations();
    places = new Map(locations.map((place) => [place.slug, place]));
    drawMap();
    drawList();
  } catch (error) {
    showAlert(alertBox, "The city map could not be loaded. Refresh the page to try again.");
    document.querySelectorAll("[data-place-status]").forEach((status) => {
      status.textContent = "Unavailable";
    });
    handleApiError(error);
  } finally {
    loading.hidden = true;
  }
}

loadMap();
