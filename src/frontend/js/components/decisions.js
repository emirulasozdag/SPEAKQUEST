// Story decisions of a started quest, shown next to the conversation. The options come from the
// API without their effects; the backend applies flags and trust when one is chosen.

import { ApiError, getDecisions, handleApiError, makeDecision } from "../api.js";
import { showAlert } from "./form.js";

function chosenNote(decision) {
  const option = decision.options.find((item) => item.id === decision.chosen);
  const note = document.createElement("p");
  note.className = "small text-secondary mb-0";
  note.textContent = `You chose: ${option?.label ?? decision.chosen}`;
  return note;
}

function resultNote(result) {
  const parts = result.npcs.map((npc) => `${npc.name} trusts you more (${npc.trust}/100).`);
  if (result.unlocked_quests.length) {
    parts.push(`New quest unlocked: ${result.unlocked_quests.map((quest) => quest.title).join(", ")}.`);
  }
  return parts.join(" ");
}

function decisionItem(decision, questId, panel) {
  const item = document.createElement("fieldset");
  item.className = "mb-3";
  const legend = document.createElement("legend");
  legend.className = "fs-6 mb-2";
  legend.textContent = decision.prompt;
  item.append(legend);

  if (decision.chosen) {
    item.append(chosenNote(decision));
    return item;
  }

  const buttons = document.createElement("div");
  buttons.className = "d-grid gap-2";
  for (const option of decision.options) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-outline-primary text-start";
    button.textContent = option.label;
    button.addEventListener("click", async () => {
      buttons.querySelectorAll("button").forEach((other) => { other.disabled = true; });
      try {
        const result = await makeDecision(questId, decision.id, option.id);
        buttons.replaceWith(chosenNote({ ...decision, chosen: option.id }));
        const message = resultNote(result);
        if (message) showAlert(panel.querySelector("[data-decision-alert]"), message, "success");
      } catch (error) {
        buttons.querySelectorAll("button").forEach((other) => { other.disabled = false; });
        if (error instanceof ApiError && (error.status === 400 || error.status === 409)) {
          showAlert(panel.querySelector("[data-decision-alert]"), error.message, "warning");
        } else {
          handleApiError(error);
        }
      }
    });
    buttons.append(button);
  }
  item.append(buttons);
  return item;
}

// Fills the panel with the quest's decisions; leaves it hidden when the quest has none.
export async function showDecisions(panel, questId) {
  try {
    const decisions = await getDecisions(questId);
    if (!decisions.length) return;
    const body = panel.querySelector("[data-decision-list]");
    body.replaceChildren(...decisions.map((decision) => decisionItem(decision, questId, panel)));
    panel.hidden = false;
  } catch (error) {
    // The conversation still works without this panel
    if (!(error instanceof ApiError && error.status === 409)) handleApiError(error);
  }
}
