// Dialogue page: the conversation with the NPC of a quest, language feedback and quest completion.
// Replies, feedback, goals and XP all come from the API; the browser only shows them.

import {
  ApiError,
  completeQuest,
  getActiveQuest,
  getDialogueHistory,
  getDialogueSummary,
  getLocations,
  getQuests,
  handleApiError,
  sendDialogueMessage,
} from "../api.js";
import { showDecisions } from "../components/decisions.js";
import { showAlert } from "../components/form.js";
import { ENDING_PAGE, portraitUrl } from "../components/quests.js";

const loading = document.querySelector("#dialogue-loading");
const alertBox = document.querySelector("#dialogue-alert");
const emptyBox = document.querySelector("#dialogue-empty");
const content = document.querySelector("#dialogue-content");
const conversation = document.querySelector("#conversation");
const form = document.querySelector("#message-form");
const input = document.querySelector("#player-message");
const counter = document.querySelector("#message-count");
const sendButton = document.querySelector("#send-button");
const retryBox = document.querySelector("#retry-box");
const completeBox = document.querySelector("#complete-box");
const completeButton = document.querySelector("#complete-button");
const resultBox = document.querySelector("#result-box");

const state = {
  quest: null,
  npc: null,
  place: null,
  sending: false,
  finished: false,
  objectives: [],
  // Story decisions of this quest not made yet; "Complete quest" waits for them
  openDecisions: 0,
};

function categoryLabel(category) {
  const text = category.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function showEmpty(message) {
  document.querySelector("#dialogue-empty-text").textContent = message;
  emptyBox.hidden = false;
  content.hidden = true;
}

function scrollToLatest() {
  conversation.lastElementChild?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function npcBubble(text) {
  const row = document.createElement("div");
  row.className = "sq-bubble-row";
  const portrait = document.createElement("img");
  portrait.className = `sq-portrait sq-portrait-sm sq-${state.quest.location_slug}`;
  portrait.src = portraitUrl(state.quest.npc_slug);
  portrait.alt = "";
  const bubble = document.createElement("div");
  bubble.className = "sq-bubble sq-bubble-npc";
  const speaker = document.createElement("p");
  speaker.className = "sq-speaker";
  speaker.textContent = state.npc?.name ?? "Character";
  const line = document.createElement("p");
  line.className = "mb-0";
  line.textContent = text;
  bubble.append(speaker, line);
  row.append(portrait, bubble);
  return row;
}

function playerBubble(text) {
  const bubble = document.createElement("div");
  bubble.className = "sq-bubble sq-bubble-player";
  const line = document.createElement("p");
  line.className = "mb-0";
  line.textContent = text;
  bubble.append(line);
  return bubble;
}

// Whether the NPC understood the player is shown apart from grammar: a message can be
// understood and still contain mistakes.
function communicationNote(success) {
  const note = document.createElement("p");
  note.className = `sq-comm ${success ? "is-understood" : "is-missed"} mb-0`;
  const name = state.npc?.name ?? "The character";
  note.textContent = success
    ? `✓ ${name} understood you.`
    : `✗ ${name} did not fully understand. Try saying it another way.`;
  return note;
}

function correctionItem(fix) {
  const item = document.createElement("li");
  item.className = "sq-fix-item";
  const category = document.createElement("span");
  category.className = "small text-secondary d-block";
  category.textContent = categoryLabel(fix.category);
  const change = document.createElement("span");
  change.className = "d-block";
  const wrong = document.createElement("span");
  wrong.className = "sq-wrong";
  wrong.textContent = fix.original;
  const right = document.createElement("span");
  right.className = "sq-right";
  right.textContent = fix.corrected;
  change.append(wrong, " → ", right);
  const why = document.createElement("span");
  why.className = "small d-block";
  why.textContent = fix.explanation;
  item.append(category, change, why);
  return item;
}

function correctionList(corrections, label) {
  const list = document.createElement("ul");
  list.className = "list-unstyled mb-0";
  list.setAttribute("aria-label", label);
  list.append(...corrections.map(correctionItem));
  return list;
}

let feedbackCount = 0;

// A badge next to the communication note opens the corrections. They are closed by default so
// the story is not interrupted; the button is keyboard operable and announces its state.
function feedbackBlock(success, corrections) {
  const box = document.createElement("div");
  box.className = "sq-turn-feedback";
  box.append(communicationNote(success));
  if (!corrections.length) return box;

  const panelId = `corrections-${(feedbackCount += 1)}`;
  const count = corrections.length;
  const label = count === 1 ? "1 correction" : `${count} corrections`;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "sq-correction-badge";
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-controls", panelId);
  toggle.textContent = label;
  const panel = document.createElement("div");
  panel.id = panelId;
  panel.hidden = true;
  panel.append(correctionList(corrections, label));
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    panel.hidden = !open;
  });
  box.append(toggle, panel);
  return box;
}

function addTurn(turn) {
  conversation.append(playerBubble(turn.player_message.text));
  conversation.append(feedbackBlock(turn.communication_success, turn.corrections));
  conversation.append(npcBubble(turn.npc_reply));
  scrollToLatest();
}

function showHistory(messages) {
  for (const message of messages) {
    if (message.role === "npc") {
      conversation.append(npcBubble(message.text));
      continue;
    }
    conversation.append(playerBubble(message.text));
    if (message.communication_success !== null) {
      conversation.append(feedbackBlock(message.communication_success, message.corrections));
    }
  }
  scrollToLatest();
}

function showObjectives(objectives) {
  const list = document.querySelector("#objective-list");
  list.replaceChildren();
  for (const objective of objectives) {
    const item = document.createElement("li");
    item.className = `sq-goal ${objective.met ? "is-met" : ""}`;
    const mark = document.createElement("span");
    mark.className = "sq-goal-mark";
    mark.setAttribute("aria-hidden", "true");
    mark.textContent = objective.met ? "✓" : "○";
    const text = document.createElement("span");
    text.textContent = objective.description;
    const status = document.createElement("span");
    status.className = "visually-hidden";
    status.textContent = objective.met ? " (done)" : " (not done yet)";
    item.append(mark, text, status);
    list.append(item);
  }

  const done = objectives.filter((objective) => objective.met).length;
  const bar = document.querySelector("#objective-bar");
  bar.setAttribute("aria-valuenow", String(done));
  bar.setAttribute("aria-valuemax", String(objectives.length));
  bar.firstElementChild.style.width = `${objectives.length ? (done / objectives.length) * 100 : 0}%`;
  document.querySelector("#objective-text").textContent = `${done} of ${objectives.length} goals done`;
  state.objectives = objectives;
  const allDone = !state.finished && objectives.length > 0 && done === objectives.length;
  // A quest cannot be completed with a decision left open, so point to the choice instead
  completeBox.hidden = !allDone || state.openDecisions > 0;
  document.querySelector("#decision-note").hidden = !allDone || state.openDecisions === 0;
}

// Goals are verified by the backend, so they are fetched again after each message.
async function refreshObjectives() {
  try {
    const active = await getActiveQuest();
    if (active && active.id === state.quest.id) showObjectives(active.objectives);
  } catch {
    // The conversation itself worked; the goal list updates on the next message
  }
}

function lockConversation(note) {
  state.finished = true;
  input.disabled = true;
  sendButton.disabled = true;
  input.placeholder = note;
  completeBox.hidden = true;
}

function setSending(sending) {
  state.sending = sending;
  sendButton.disabled = sending;
  sendButton.textContent = sending ? "Sending…" : "Send";
  sendButton.setAttribute("aria-busy", String(sending));
  input.readOnly = sending;
  document.querySelector("#retry-button").disabled = sending;
}

async function sendCurrentMessage() {
  const message = input.value.trim();
  if (state.sending || state.finished) return;
  if (!message) {
    showAlert(alertBox, "Write a message first.", "warning");
    input.focus();
    return;
  }

  alertBox.hidden = true;
  retryBox.hidden = true;
  setSending(true);
  try {
    const turn = await sendDialogueMessage(message);
    if (turn.status === "ai_unavailable") {
      // Nothing was saved, so the text stays in the box and can be sent again
      document.querySelector("#retry-text").textContent =
        "The AI helper is not available right now, so your message was not sent. Your text is still in the box. Try again in a moment.";
      retryBox.hidden = false;
      return;
    }
    input.value = "";
    updateCounter();
    addTurn(turn);
    // The reply already carries every goal with its state, so no second request is needed
    showObjectives(turn.objectives);
  } catch (error) {
    if (error instanceof ApiError && error.status !== 0 && error.status !== 401) {
      showAlert(alertBox, error.message, "danger");
      if (error.status === 409) lockConversation("This quest is not active.");
    } else {
      handleApiError(error);
    }
  } finally {
    setSending(false);
    if (!state.finished) input.focus();
  }
}

function updateCounter() {
  counter.textContent = `${input.value.length} / ${input.maxLength}`;
}

// The end-of-quest summary comes from stored data (GET /dialogue/summary), so it is the same after
// a reload. If it cannot be loaded the quest is still complete and the rest of the page works.
async function showSummary() {
  const panel = document.querySelector("#summary-panel");
  const body = document.querySelector("#summary-body");
  try {
    const summary = await getDialogueSummary(state.quest.id);
    body.replaceChildren();

    const understood = document.createElement("p");
    understood.className = "mb-2";
    understood.textContent = summary.messages_sent
      ? `${state.npc?.name ?? "The character"} understood ${summary.understood} of your ${summary.messages_sent} messages.`
      : "You finished this quest without sending any messages.";
    const xp = document.createElement("p");
    xp.className = "mb-3 fw-bold";
    xp.textContent = `XP earned: +${state.quest.reward_xp}`;
    body.append(understood, xp);

    if (!summary.mistakes) {
      const clean = document.createElement("p");
      clean.className = "sq-right mb-0";
      clean.textContent = "No grammar mistakes. Great work!";
      body.append(clean);
    } else {
      const top = document.createElement("p");
      top.className = "mb-2";
      top.textContent = `Most common mistake: ${categoryLabel(summary.top_category)} (${summary.mistakes} in total).`;
      const heading = document.createElement("h3");
      heading.className = "h6";
      heading.textContent = summary.examples.length === 1 ? "Example correction" : "Example corrections";
      body.append(top, heading, correctionList(summary.examples, "Example corrections"));
    }
    panel.hidden = false;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return handleApiError(error);
    body.textContent = "Your summary could not be loaded.";
    panel.hidden = false;
  }
}

async function finishQuest() {
  completeButton.disabled = true;
  completeButton.textContent = "Completing…";
  try {
    const done = await completeQuest(state.quest.id);
    lockConversation("This quest is complete.");
    resultBox.replaceChildren();
    const title = document.createElement("p");
    title.className = "fw-bold mb-1";
    title.textContent = `Quest complete! +${done.xp_gained} XP`;
    const total = document.createElement("p");
    total.className = "small mb-2";
    total.textContent = done.leveled_up
      ? `Level up! You are now level ${done.level} with ${done.xp} XP.`
      : `You now have ${done.xp} XP (level ${done.level}).`;
    const link = document.createElement("a");
    link.className = "btn btn-sm btn-outline-primary";
    link.href = "/pages/dashboard.html";
    link.textContent = "Back to dashboard";
    resultBox.append(title, total);
    if (done.ending) {
      // This was the last quest the story allows: show how it ended
      const ending = document.createElement("div");
      ending.className = "sq-ending mb-2";
      ending.innerHTML = '<p class="small text-secondary mb-1">The end</p><p class="fw-bold mb-1"></p><p class="small mb-0"></p>';
      ending.querySelector(".fw-bold").textContent = done.ending.title;
      ending.querySelector(".small.mb-0").textContent = done.ending.summary;
      resultBox.append(ending);
      // The ending screen replaces the dashboard as the next step
      link.href = ENDING_PAGE;
      link.textContent = "See how your story ended";
    }
    if (done.unlocked_quests?.length) {
      const unlocked = document.createElement("p");
      unlocked.className = "small mb-2";
      unlocked.textContent = `New quest unlocked: ${done.unlocked_quests.map((quest) => quest.title).join(", ")}.`;
      resultBox.append(unlocked);
    }
    resultBox.append(link);
    resultBox.hidden = false;
    await showSummary();
  } catch (error) {
    completeButton.disabled = false;
    completeButton.textContent = "Complete quest";
    if (error instanceof ApiError && error.status === 409) {
      showAlert(alertBox, error.message, "warning");
      await refreshObjectives();
    } else {
      handleApiError(error);
    }
  }
}

async function loadDialogue() {
  try {
    const requested = Number(new URLSearchParams(window.location.search).get("quest"));
    const [quests, active, locations] = await Promise.all([getQuests(), getActiveQuest(), getLocations()]);

    const questId = requested || active?.id;
    const summary = quests.find((quest) => quest.id === questId);
    if (!questId || !summary) {
      showEmpty(
        requested
          ? "That quest does not exist."
          : "You have no active quest right now. Pick a place on the city map to start one.",
      );
      return;
    }
    if (summary.status === "locked" || summary.status === "available") {
      showEmpty(`"${summary.title}" has not been started yet. Start it from the city map.`);
      return;
    }

    const isActive = summary.status === "active";
    state.quest = isActive ? active : summary;
    state.place = locations.find((place) => place.slug === summary.location_slug);
    state.npc = state.place?.npcs.find((npc) => npc.slug === summary.npc_slug) ?? null;
    const history = await getDialogueHistory(summary.id);

    document.title = `${summary.title} – SpeakQuest`;
    document.querySelector("#quest-title").textContent = summary.title;
    document.querySelector("#quest-panel").classList.add(`sq-${summary.location_slug}`);
    document.querySelector("#scene-bg").src = `/assets/scenes/${summary.location_slug}.svg`;
    document.querySelector("#scene").classList.add(`sq-${summary.location_slug}`);
    document.querySelector("#scene-portrait").src = portraitUrl(summary.npc_slug);
    document.querySelector("#scene-name").textContent = state.npc?.name ?? "";
    document.querySelector("#scene-role").textContent =
      [state.npc?.role, state.place?.name].filter(Boolean).join(" · ");

    showHistory(history.messages);
    const decisionPanel = document.querySelector("#decision-panel");
    state.openDecisions = await showDecisions(decisionPanel, summary.id);
    decisionPanel.addEventListener("decision-made", () => {
      state.openDecisions = Math.max(0, state.openDecisions - 1);
      showObjectives(state.objectives);
    });
    if (isActive) {
      showObjectives(active.objectives);
    } else {
      document.querySelector("#objective-list").replaceChildren();
      document.querySelector("#objective-bar").hidden = true;
      document.querySelector("#objective-text").textContent = "You completed this quest.";
      lockConversation("This quest is complete.");
      await showSummary();
    }
    content.hidden = false;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      showEmpty("This conversation could not be found. Start a quest from the city map.");
    } else {
      showAlert(alertBox, "Your conversation could not be loaded. Refresh the page to try again.");
      handleApiError(error);
    }
  } finally {
    loading.hidden = true;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendCurrentMessage();
});

// Enter sends; Shift+Enter adds a new line. isComposing keeps IME input (accents, etc.) working.
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    sendCurrentMessage();
  }
});
input.addEventListener("input", updateCounter);
document.querySelector("#retry-button").addEventListener("click", sendCurrentMessage);
completeButton.addEventListener("click", finishQuest);

loadDialogue();
