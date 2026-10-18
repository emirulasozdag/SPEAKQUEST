// Renders the shared site header into <header data-component="navbar">.
// Use data-variant="game" for in-game pages, "public" for landing and auth pages.

const GAME_LINKS = [
  { href: "/pages/dashboard.html", label: "Dashboard" },
  { href: "/pages/map.html", label: "City map" },
  { href: "/pages/journal.html", label: "Quest journal" },
  { href: "/pages/progress.html", label: "Progress" },
  { href: "/pages/profile.html", label: "Profile" },
];

function linkItem({ href, label }) {
  const current = window.location.pathname === href ? ' aria-current="page"' : "";
  return `<li class="nav-item"><a class="nav-link px-lg-3" href="${href}"${current}>${label}</a></li>`;
}

function gameNav() {
  return `
    <button class="navbar-toggler border-light" type="button" data-bs-toggle="collapse"
            data-bs-target="#sq-nav" aria-controls="sq-nav" aria-expanded="false"
            aria-label="Toggle navigation">
      <span class="navbar-toggler-icon" style="filter: invert(1)"></span>
    </button>
    <div class="collapse navbar-collapse" id="sq-nav">
      <ul class="navbar-nav me-auto">${GAME_LINKS.map(linkItem).join("")}</ul>
      <span class="sq-status" data-api-status>Checking server…</span>
    </div>`;
}

function publicNav() {
  return `
    <div class="d-flex align-items-center gap-3 ms-auto">
      <span class="sq-status d-none d-sm-inline" data-api-status>Checking server…</span>
      <a class="btn btn-sm btn-outline-light" href="/pages/login.html">Log in</a>
    </div>`;
}

export function renderNavbar(host) {
  const variant = host.dataset.variant ?? "game";
  host.classList.add("sq-header");
  host.innerHTML = `
    <nav class="navbar navbar-expand-lg py-3" aria-label="Main">
      <div class="container">
        <a class="navbar-brand" href="/">SpeakQuest</a>
        ${variant === "game" ? gameNav() : publicNav()}
      </div>
    </nav>`;
}
