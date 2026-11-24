const DEFAULT_API_BASE = "https://bridgecf-api.onrender.com";

const handleInput = document.querySelector("#userHandle");
const apiBaseInput = document.querySelector("#apiBaseUrl");
const status = document.querySelector("#status");
const statusText = document.querySelector("#statusText");

function showStatus(message, state = "idle") {
  status.dataset.state = state;
  statusText.textContent = message;
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get(["userHandle", "apiBaseUrl"]);
  handleInput.value = settings.userHandle || "";
  apiBaseInput.value = settings.apiBaseUrl || DEFAULT_API_BASE;
}

document.querySelector("#save").addEventListener("click", async () => {
  const userHandle = handleInput.value.trim();
  if (!userHandle) {
    showStatus("Enter your Codeforces handle first.", "error");
    handleInput.focus();
    return;
  }

  const apiBaseUrl = apiBaseInput.value.trim().replace(/\/$/, "") || DEFAULT_API_BASE;
  await chrome.storage.sync.set({ userHandle, apiBaseUrl });
  showStatus("Saved. Open a Codeforces problem to get started.", "success");
});

document.querySelector("#testConnection").addEventListener("click", async () => {
  const apiBaseUrl = apiBaseInput.value.trim().replace(/\/$/, "") || DEFAULT_API_BASE;
  await chrome.storage.sync.set({ apiBaseUrl });
  showStatus("Checking the backend…", "pending");
  chrome.runtime.sendMessage({ type: "CHECK_HEALTH" }, (response) => {
    if (chrome.runtime.lastError) {
      showStatus(chrome.runtime.lastError.message, "error");
    } else if (response?.ok) {
      showStatus("Backend is reachable.", "success");
    } else {
      showStatus(response?.error || "Could not reach the backend.", "error");
    }
  });
});

loadSettings().catch((error) => {
  showStatus(`Could not load settings: ${error.message}`, "error");
});
