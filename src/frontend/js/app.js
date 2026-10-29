// Entry point loaded by every page: protects game pages, renders shared components and wires
// placeholder actions.

import { getHealth, redirectToLogin } from "./api.js";
import { renderFooter } from "./components/footer.js";
import { renderNavbar } from "./components/navbar.js";
import { showToast } from "./components/toast.js";
import { clearSession, hasValidSession } from "./state.js";

// Pages marked <body data-auth="required"> are only for logged-in players.
// Returns false when the page is being left for the login page.
function guardProtectedPage() {
  if (document.body.dataset.auth === "required" && !hasValidSession()) {
    redirectToLogin();
    return false;
  }
  return true;
}

function renderComponents() {
  document.querySelectorAll('[data-component="navbar"]').forEach(renderNavbar);
  document.querySelectorAll('[data-component="footer"]').forEach(renderFooter);
}

function wireLogout() {
  document.addEventListener("click", (event) => {
    if (!event.target.closest('[data-action="logout"]')) return;
    event.preventDefault();
    clearSession();
    window.location.assign("/");
  });
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

if (guardProtectedPage()) {
  renderComponents();
  wireLogout();
  wirePlannedFeatures();
  showApiStatus();
}
