const DEFAULT_API_BASE = "http://127.0.0.1:8000";

async function loadSettings() {
  const settings = await chrome.storage.sync.get(["userHandle", "apiBaseUrl"]);
  document.querySelector("#userHandle").value = settings.userHandle || "";
  document.querySelector("#apiBaseUrl").value =
    settings.apiBaseUrl || DEFAULT_API_BASE;
}

document.querySelector("#save").addEventListener("click", async () => {
  const userHandle = document.querySelector("#userHandle").value.trim();
  const apiBaseUrl = document.querySelector("#apiBaseUrl").value.trim().replace(/\/$/, "");
  await chrome.storage.sync.set({ userHandle, apiBaseUrl });
  document.querySelector("#status").textContent = "Saved.";
});

document.querySelector("#testConnection").addEventListener("click", () => {
  const status = document.querySelector("#status");
  status.textContent = "Testing...";
  chrome.runtime.sendMessage({ type: "CHECK_HEALTH" }, (response) => {
    if (chrome.runtime.lastError) {
      status.textContent = chrome.runtime.lastError.message;
    } else if (response?.ok) {
      status.textContent = "Connected.";
    } else {
      status.textContent = response?.error || "Connection failed.";
    }
  });
});

loadSettings();
