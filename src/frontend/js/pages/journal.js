// Quest journal: every quest by status, with its reward, why a locked quest is still locked and
// why the Adaptive Quest Engine suggests the next one. Everything shown comes from the API.

import { getLocations, getQuests, getStoryEnding, handleApiError } from "../api.js";
import { showAlert } from "../components/form.js";
import {
  ENDING_PAGE,
  MAP_PAGE,
  QUEST_STATUS_LABELS,
  RECOMMENDATION_HEADING,
  dialogueUrl,
} from "../components/quests.js";
import { skillLabel } from "../components/skills.js";

const loading = document.querySelector("#journal-loading");
const content = document.querySelector("#journal-content");
const alertBox = document.querySelector("#journal-alert");

const EMPTY_TEXT = {
  active: "Nothing to play right now. Check the locked quests to see what opens them.",
  done: "No quests completed yet. Your first one is waiting in the city.",
  locked: "No locked quests. Every quest in the city is open to you or already done.",
};

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function questMeta(quest, place) {
  const npc = place?.npcs.find((item) => item.slug === quest.npc_slug);
  const practises = `Practises ${quest.target_skills.map(skillLabel).join(", ")}`;
  if (quest.status === "completed") {
    const when = quest.completed_at ? `Completed ${formatDate(quest.completed_at)}` : "Completed";
    return [place?.name, npc?.name, when, `+${quest.reward_xp} XP`];
  }
  return [place?.name, npc?.name, practises, `Reward: ${quest.reward_xp} XP`];
}

function questAction(quest) {
  if (quest.status === "active") return { href: dialogueUrl(quest.id), label: "Continue conversation", primary: true };
  if (quest.status === "available") return { href: MAP_PAGE, label: "Find it on the city map", primary: quest.recommended };
  if (quest.status === "completed") return { href: dialogueUrl(quest.id), label: "Read the conversation" };
  return null;
}

function questCard(quest, places) {
  const place = places.get(quest.location_slug);
  const card = document.createElement("article");
  card.className = "sq-panel sq-line-tag mb-3";
  card.classList.add(quest.status === "locked" ? "sq-quest-locked" : `sq-${quest.location_slug}`);
  card.innerHTML = `
    <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
      <h2 class="h4 mb-0"></h2>
      <span class="sq-quest-status"></span>
    </div>
    <p class="mb-2 quest-summary"></p>
    <p class="small text-secondary mb-0 quest-meta"></p>`;
  card.querySelector("h2").textContent = quest.title;
  const status = card.querySelector(".sq-quest-status");
  status.dataset.status = quest.status;
  status.textContent = QUEST_STATUS_LABELS[quest.status] ?? quest.status;
  card.querySelector(".quest-summary").textContent = quest.summary;
  card.querySelector(".quest-meta").textContent = questMeta(quest, place).filter(Boolean).join(" · ");

  if (quest.recommended && quest.recommendation_reason) {
    const why = document.createElement("div");
    why.className = "sq-recommended mt-3";
    why.innerHTML = '<p class="small fw-bold mb-1"></p><p class="mb-0"></p>';
    why.querySelector(".fw-bold").textContent = RECOMMENDATION_HEADING;
    why.querySelector(".mb-0").textContent = quest.recommendation_reason;
    card.append(why);
  }
  if (quest.status === "locked" && quest.locked_reason) {
    const lock = document.createElement("p");
    lock.className = "sq-lock-reason mt-3 mb-0";
    lock.innerHTML = '<span class="fw-bold">What opens it: </span><span></span>';
    lock.lastElementChild.textContent = quest.locked_reason;
    card.append(lock);
  }
  const action = questAction(quest);
  if (action) {
    const link = document.createElement("a");
    link.className = `btn btn-sm mt-3 ${action.primary ? "btn-primary" : "btn-outline-primary"}`;
    link.href = action.href;
    link.textContent = action.label;
    card.append(link);
  }
  return card;
}

function fillTab(key, panel, quests, places) {
  document.querySelector(`[data-count="${key}"]`).textContent = String(quests.length);
  if (!quests.length) {
    const empty = document.createElement("p");
    empty.className = "text-secondary";
    empty.textContent = EMPTY_TEXT[key];
    panel.replaceChildren(empty);
    return;
  }
  panel.replaceChildren(...quests.map((quest) => questCard(quest, places)));
}

function showEnding(ending) {
  const box = document.querySelector("#journal-next");
  box.className = "sq-ending mb-4";
  box.innerHTML = `
    <p class="small text-secondary mb-1">Your story has ended</p>
    <p class="h5 mb-1"></p>
    <p class="mb-2 ending-summary"></p>
    <a class="btn btn-sm btn-primary" href="${ENDING_PAGE}">See how your story ended</a>`;
  box.querySelector(".h5").textContent = ending.title;
  box.querySelector(".ending-summary").textContent = ending.summary;
  box.hidden = false;
}

async function loadJournal() {
  try {
    const [quests, locations] = await Promise.all([getQuests(), getLocations()]);
    const places = new Map(locations.map((place) => [place.slug, place]));
    // The suggested quest first, then the API's story order
    const active = quests
      .filter((quest) => quest.status === "active" || quest.status === "available")
      .sort((a, b) => (b.status === "active") - (a.status === "active") || b.recommended - a.recommended);
    const done = quests
      .filter((quest) => quest.status === "completed")
      .sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? ""));
    const locked = quests.filter((quest) => quest.status === "locked");

    fillTab("active", document.querySelector("#quests-active"), active, places);
    fillTab("done", document.querySelector("#quests-done"), done, places);
    fillTab("locked", document.querySelector("#quests-locked"), locked, places);

    // Only asked once nothing is left to play
    if (!active.length) {
      const ending = await getStoryEnding();
      if (ending) showEnding(ending);
    }
    content.hidden = false;
  } catch (error) {
    showAlert(alertBox, "Your quests could not be loaded. Refresh the page to try again.");
    handleApiError(error);
  } finally {
    loading.hidden = true;
  }
}

loadJournal();
