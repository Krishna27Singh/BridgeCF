const DEFAULT_API_BASE = "https://bridgecf-api.onrender.com";

async function getApiBaseUrl() {
  const stored = await chrome.storage.sync.get(["apiBaseUrl"]);
  return (stored.apiBaseUrl || DEFAULT_API_BASE).replace(/\/$/, "");
}

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let payload = null;
    try {
      payload = await response.json();
    } catch (_) {
      payload = null;
    }
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: payload?.error || payload?.detail || `HTTP ${response.status}`,
      };
    }
    return { ok: true, status: response.status, data: payload };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error.name === "AbortError"
        ? "Backend request timed out"
        : `Network error: ${error.message}`,
    };
  } finally {
    clearTimeout(timeout);
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!["GET_HINT", "CHECK_HEALTH"].includes(message?.type)) {
    sendResponse({ ok: false, status: 0, error: "Unknown message type" });
    return false;
  }

  (async () => {
    const apiBaseUrl = await getApiBaseUrl();
    if (message.type === "CHECK_HEALTH") {
      sendResponse(await fetchJson(`${apiBaseUrl}/health`, { method: "GET" }));
      return;
    }
    sendResponse(
      await fetchJson(`${apiBaseUrl}/api/hint`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          problem_id: message.payload.problem_id,
          user_handle: message.payload.user_handle,
          max_bridges: 3,
          problem_statement: message.payload.problem_statement || null,
        }),
      }),
    );
  })();
  return true;
});
