// Small Bootstrap toast used for short notices.

let container;

export function showToast(message) {
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container position-fixed bottom-0 end-0 p-3";
    container.setAttribute("aria-live", "polite");
    document.body.append(container);
  }

  const toast = document.createElement("div");
  toast.className = "toast align-items-center text-bg-dark border-0";
  toast.setAttribute("role", "status");
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body"></div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto"
              data-bs-dismiss="toast" aria-label="Close"></button>
    </div>`;
  toast.querySelector(".toast-body").textContent = message;
  container.append(toast);

  const instance = window.bootstrap.Toast.getOrCreateInstance(toast, { delay: 3500 });
  toast.addEventListener("hidden.bs.toast", () => toast.remove());
  instance.show();
}
