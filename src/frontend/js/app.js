// Entry point loaded by every page: renders shared components and wires placeholder actions.

import { getHealth } from "./api.js";
import { renderFooter } from "./components/footer.js";
import { renderNavbar } from "./components/navbar.js";
import { showToast } from "./components/toast.js";

function renderComponents() {
  document.querySelectorAll('[data-component="navbar"]').forEach(renderNavbar);
  document.querySelectorAll('[data-component="footer"]').forEach(renderFooter);
}

// Buttons and forms marked with data-feature are planned but not built yet.
function wirePlannedFeatures() {
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("button[data-feature], a[data-feature]");
    if (!trigger) return;
    event.preventDefault();
    showToast(`${trigger.dataset.feature} is not built yet. It is on the roadmap.`);
  });

  document.querySelectorAll("form[data-feature]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      showToast(`${form.dataset.feature} is not built yet. It is on the roadmap.`);
    });
  });
}

async function showApiStatus() {
  const badges = document.querySelectorAll("[data-api-status]");
  if (!badges.length) return;

  let state = "down";
  let label = "Server offline";
  try {
    const health = await getHealth();
    const dbOk = health.database === "ok";
    state = dbOk ? "ok" : "down";
    label = dbOk ? "Server online" : "Server online, database offline";
  } catch {
    // Keep the offline label.
  }

  badges.forEach((badge) => {
    badge.dataset.state = state;
    badge.textContent = label;
  });
}

renderComponents();
wirePlannedFeatures();
showApiStatus();
