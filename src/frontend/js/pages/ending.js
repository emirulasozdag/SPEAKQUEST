// Ending screen: which ending the player reached, the decisions that led there, the XP they
// earned and the skill that improved most. Every value comes from GET /story/ending.

import { getStoryEnding, handleApiError } from "../api.js";
import { showAlert } from "../components/form.js";
import { skillLabel } from "../components/skills.js";

const loading = document.querySelector("#ending-loading");
const alertBox = document.querySelector("#ending-alert");
const pending = document.querySelector("#ending-pending");
const content = document.querySelector("#ending-content");

function showNumbers(ending) {
  document.querySelector("#stat-xp").textContent = String(ending.xp);
  document.querySelector("#stat-quests").textContent = String(ending.quests_completed);
  document.querySelector("#stat-level").textContent = String(ending.level);

  const box = document.querySelector("#improved-skill");
  const skill = ending.most_improved_skill;
  if (!skill) {
    box.innerHTML = '<p class="small text-secondary mb-0">No skill has risen above its starting score yet. Every conversation you have from now on still counts.</p>';
    return;
  }
  box.innerHTML = `
    <p class="fw-bold mb-1"></p>
    <div class="progress sq-skill-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100">
      <div class="progress-bar"></div>
    </div>
    <p class="small text-secondary mb-0 mt-1"></p>`;
  box.querySelector(".fw-bold").textContent = skillLabel(skill.category);
  const bar = box.querySelector(".progress");
  bar.setAttribute("aria-label", `${skillLabel(skill.category)} score`);
  bar.setAttribute("aria-valuenow", String(skill.score));
  bar.setAttribute("aria-valuetext", `${skill.score} of 100, up from ${skill.start_score}`);
  bar.firstElementChild.style.width = `${skill.score}%`;
  box.querySelector("p.small").textContent = `From ${skill.start_score} to ${skill.score} out of 100`;
}

function showDecisions(decisions) {
  const list = document.querySelector("#decision-list");
  if (!decisions.length) {
    list.innerHTML = '<li class="text-secondary">You did not make any story decisions this time.</li>';
    return;
  }
  for (const decision of decisions) {
    const item = document.createElement("li");
    item.className = "sq-decision";
    item.innerHTML = `
      <p class="small text-secondary mb-1"></p>
      <p class="mb-1 decision-prompt"></p>
      <p class="fw-bold mb-0"></p>`;
    item.querySelector(".small").textContent = decision.quest_title;
    item.querySelector(".decision-prompt").textContent = decision.prompt;
    item.querySelector(".fw-bold").textContent = `You chose: ${decision.choice}`;
    list.append(item);
  }
}

async function loadEnding() {
  try {
    const ending = await getStoryEnding();
    if (!ending) {
      pending.hidden = false;
      return;
    }
    document.querySelector("#ending-title").textContent = ending.title;
    document.querySelector("#ending-summary").textContent = ending.summary;
    document.title = `${ending.title} – SpeakQuest`;
    showNumbers(ending);
    showDecisions(ending.decisions);
    content.hidden = false;
  } catch (error) {
    showAlert(alertBox, "Your ending could not be loaded. Refresh the page to try again.");
    handleApiError(error);
  } finally {
    loading.hidden = true;
  }
}

loadEnding();
