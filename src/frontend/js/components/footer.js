// Renders the shared footer into <footer data-component="footer">.

export function renderFooter(host) {
  host.classList.add("sq-footer", "py-4", "mt-5");
  host.innerHTML = `
    <div class="container d-flex flex-column flex-sm-row justify-content-between gap-2">
      <p class="mb-0">SpeakQuest — your words change the story.</p>
      <p class="mb-0">SENG461 course project · <a href="/api/docs">API docs</a></p>
    </div>`;
}
