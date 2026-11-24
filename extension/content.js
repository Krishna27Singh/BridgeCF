if (!window.bridgeCFHintInjected) {
  window.bridgeCFHintInjected = true;
  window.addEventListener("load", injectHintUI);
  if (document.readyState === "complete") injectHintUI();
}

const DEFAULT_API_BASE = "https://bridgecf-api.onrender.com";
const THEME_STORAGE_KEY = "theme";

function parseProblemId(pathname) {
  const problemset = pathname.match(
    /^\/problemset\/problem\/([0-9]+)\/([A-Za-z0-9]+)\/?$/i,
  );
  if (problemset) return `${problemset[1]}_${problemset[2].toUpperCase()}`;
  const contest = pathname.match(
    /^\/(?:contest|gym)\/([0-9]+)\/problem\/([A-Za-z0-9]+)\/?$/i,
  );
  if (contest) return `${contest[1]}_${contest[2].toUpperCase()}`;
  return null;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function formatNumber(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
}

function detectDarkTheme() {
  if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return true;

  const themeClasses = `${document.documentElement.className} ${document.body?.className || ""}`;
  if (/\bdark\b|\btheme-dark\b/i.test(themeClasses)) return true;

  for (const element of [document.body, document.documentElement]) {
    const background = getComputedStyle(element).backgroundColor;
    const channels = background.match(/[\d.]+/g)?.map(Number);
    if (!channels || channels.length < 3) continue;
    const alpha = channels.length > 3 ? channels[3] : 1;
    if (alpha > 0) return channels[0] + channels[1] + channels[2] < 330;
  }
  return false;
}

async function resolveHandle() {
  const stored = await chrome.storage.sync.get(["userHandle"]);
  if (stored.userHandle?.trim()) return stored.userHandle.trim();

  const profile = document.querySelector('a[href^="/profile/"]');
  if (profile) {
    const match = profile.getAttribute("href").match(/^\/profile\/([^/?#]+)/);
    if (match) return decodeURIComponent(match[1]);
  }

  const handle = window.prompt("Enter your Codeforces handle:");
  if (!handle?.trim()) return null;
  await chrome.storage.sync.set({ userHandle: handle.trim() });
  return handle.trim();
}

function injectHintUI() {
  if (document.querySelector("#bridgecf-hint-host")) return;
  const problemId = parseProblemId(window.location.pathname);
  if (!problemId) return;

  const host = document.createElement("div");
  host.id = "bridgecf-hint-host";
  const sidebar = document.querySelector("#sidebar");
  if (sidebar) {
    sidebar.insertBefore(host, sidebar.firstChild);
  } else {
    host.classList.add("bridgecf-floating");
    document.body.appendChild(host);
  }

  const shadow = host.attachShadow({ mode: "open" });
  const stylesheet = document.createElement("link");
  stylesheet.rel = "stylesheet";
  stylesheet.href = chrome.runtime.getURL("styles.css");
  shadow.appendChild(stylesheet);

  const app = document.createElement("div");
  app.className = "bridgecf-app";
  app.innerHTML = `
    <aside class="bridgecf-drawer" aria-label="BridgeCF adaptive hints">
      <header class="bridgecf-header">
        <div class="bridgecf-brand">
          <span class="bridgecf-mark" aria-hidden="true">B</span>
          <span class="bridgecf-wordmark">BridgeCF</span>
          <span class="bridgecf-provider" id="bridgecf-provider" hidden></span>
        </div>
        <div class="bridgecf-header-actions">
          <button class="bridgecf-icon-button" id="bridgecf-theme" type="button" aria-label="Switch theme"></button>
          <button class="bridgecf-icon-button" id="bridgecf-collapse" type="button" aria-label="Collapse BridgeCF">−</button>
        </div>
      </header>
      <main class="bridgecf-body">
        <div class="bridgecf-intro">
          <p class="bridgecf-kicker">ADAPTIVE PRACTICE</p>
          <p class="bridgecf-intro-copy">A small nudge for the problem you’re working on.</p>
        </div>
        <button class="bridgecf-primary" id="bridgecf-get-hint" type="button">
          <span>Get a hint</span><span aria-hidden="true">↗</span>
        </button>
        <div class="bridgecf-output" id="bridgecf-output" aria-live="polite"></div>
      </main>
    </aside>
    <button class="bridgecf-launcher" id="bridgecf-launcher" type="button" hidden>
      <span class="bridgecf-mark" aria-hidden="true">B</span> BridgeCF
    </button>
  `;
  shadow.appendChild(app);

  const themeButton = shadow.querySelector("#bridgecf-theme");
  let savedTheme = null;
  let mediaQuery = window.matchMedia?.("(prefers-color-scheme: dark)");
  const applyTheme = (theme) => {
    const resolvedTheme = theme || (detectDarkTheme() ? "dark" : "light");
    host.dataset.theme = resolvedTheme;
    themeButton.textContent = resolvedTheme === "dark" ? "Dark" : "Light";
    themeButton.setAttribute("aria-label", `Current theme: ${resolvedTheme}. Switch theme`);
  };
  chrome.storage.local.get([THEME_STORAGE_KEY]).then((settings) => {
    savedTheme = settings[THEME_STORAGE_KEY] || null;
    applyTheme(savedTheme);
  });
  applyTheme(null);
  themeButton.addEventListener("click", async () => {
    const nextTheme = host.dataset.theme === "dark" ? "light" : "dark";
    savedTheme = nextTheme;
    applyTheme(nextTheme);
    await chrome.storage.local.set({ [THEME_STORAGE_KEY]: nextTheme });
  });
  mediaQuery?.addEventListener("change", () => {
    if (!savedTheme) applyTheme(null);
  });
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local" && changes[THEME_STORAGE_KEY]) {
      savedTheme = changes[THEME_STORAGE_KEY].newValue || null;
      applyTheme(savedTheme);
    }
  });

  const collapse = () => {
    host.classList.add("is-collapsed");
    shadow.querySelector(".bridgecf-drawer").hidden = true;
    shadow.querySelector("#bridgecf-launcher").hidden = false;
  };
  const expand = () => {
    host.classList.remove("is-collapsed");
    shadow.querySelector(".bridgecf-drawer").hidden = false;
    shadow.querySelector("#bridgecf-launcher").hidden = true;
  };
  shadow.querySelector("#bridgecf-collapse").addEventListener("click", collapse);
  shadow.querySelector("#bridgecf-launcher").addEventListener("click", expand);

  shadow.querySelector("#bridgecf-get-hint").addEventListener("click", async () => {
    const output = shadow.querySelector("#bridgecf-output");
    output.innerHTML = `
      <div class="bridgecf-loading-card">
        <span class="bridgecf-spinner" aria-hidden="true"></span>
        <span>Finding a useful next step…</span>
        <span class="bridgecf-cold-note" hidden>Render is waking up; this first request can take a little longer.</span>
      </div>
      <div class="bridgecf-skeleton" aria-hidden="true"><i></i><i></i><i></i></div>`;
    const coldStartTimer = window.setTimeout(() => {
      const note = output.querySelector(".bridgecf-cold-note");
      if (note) note.hidden = false;
    }, 5000);

    try {
      const handle = await resolveHandle();
      if (!handle) {
        output.innerHTML = '<p class="bridgecf-error">Add a Codeforces handle in the BridgeCF popup to continue.</p>';
        return;
      }

      const statementElement = document.querySelector(".problem-statement");
      let problemStatement = null;
      if (statementElement) {
        const clone = statementElement.cloneNode(true);
        clone.querySelectorAll(".header, .sample-tests, .sample-test").forEach((node) => node.remove());
        problemStatement = clone.textContent.replace(/\s+/g, " ").trim().slice(0, 2000);
      }

      chrome.runtime.sendMessage(
        {
          type: "GET_HINT",
          payload: {
            problem_id: problemId,
            user_handle: handle,
            problem_statement: problemStatement,
          },
        },
        (response) => {
          window.clearTimeout(coldStartTimer);
          if (chrome.runtime.lastError) {
            output.innerHTML = `<p class="bridgecf-error">${escapeHtml(chrome.runtime.lastError.message)}</p>`;
            return;
          }
          if (!response?.ok) {
            output.innerHTML = `<p class="bridgecf-error">${escapeHtml(response?.error || "The hint request failed.")}</p>`;
            return;
          }
          renderHint(response.data, output, shadow);
        },
      );
    } catch (error) {
      window.clearTimeout(coldStartTimer);
      output.innerHTML = `<p class="bridgecf-error">${escapeHtml(error.message || "Could not prepare the hint request.")}</p>`;
    }
  });
}

function renderHint(data, output, shadow) {
  const provider = shadow.querySelector("#bridgecf-provider");
  provider.textContent = `${data.provider || "provider"}${data.fallback_used ? " · fallback" : ""}`;
  provider.hidden = false;

  const concepts = (data.missing_concepts || [])
    .map((concept) => `<span class="bridgecf-concept">${escapeHtml(concept)}</span>`)
    .join("");

  const bridges = (data.bridge_problems || []).map((item) => {
    const problem = item.problem || {};
    let problemUrl = "#";
    try {
      const candidateUrl = new URL(problem.url);
      if (candidateUrl.hostname === "codeforces.com" || candidateUrl.hostname.endsWith(".codeforces.com")) {
        problemUrl = candidateUrl.href;
      }
    } catch (_) {
      problemUrl = "#";
    }
    const matchPercent = Math.round(Math.max(0, Math.min(1, Number(item.final_score) || 0)) * 100);
    const scoreLine = `semantic ${formatNumber(item.semantic_score, 2)} · concept ${formatNumber(item.concept_score, 2)} · difficulty ${formatNumber(item.difficulty_score, 2)}`;
    return `
      <a class="bridgecf-bridge-row" href="${escapeHtml(problemUrl)}" target="_blank" rel="noopener noreferrer">
        <span class="bridgecf-bridge-main">
          <strong>${escapeHtml(problem.problem_id || "Codeforces problem")}</strong>
          <span class="bridgecf-bridge-open">Open problem <span aria-hidden="true">↗</span></span>
        </span>
        <span class="bridgecf-bridge-meta">
          ${problem.rating ? `<span class="bridgecf-rating">${escapeHtml(problem.rating)}</span>` : ""}
          <span class="bridgecf-match">${matchPercent}% match</span>
        </span>
        <span class="bridgecf-score-line">${scoreLine}</span>
      </a>`;
  }).join("");

  const hint = data.hint || {};
  const hintRows = [
    ["01", "Conceptual nudge", hint.conceptual_nudge],
    ["02", "Strategy", hint.strategy_hint],
    ["03", "Complexity", hint.complexity_nudge],
  ].filter(([, , text]) => String(text || "").trim());
  const hintMarkup = hintRows.map(([number, label, text], index) => `
    <details class="bridgecf-hint-row"${index === 0 ? " open" : ""}>
      <summary><span class="bridgecf-hint-number">${number}</span><span class="bridgecf-hint-number" aria-hidden="true">·</span><span>${label}</span><span class="bridgecf-chevron" aria-hidden="true"></span></summary>
      <p>${escapeHtml(text)}</p>
    </details>`).join("");
  const rationale = String(hint.bridge_rationale || "").trim();
  const timings = data.timings_ms || {};
  const cfFetch = Number(timings.cf_fetch_ms);
  const cfLabel = Number.isFinite(cfFetch) && cfFetch < 1 ? "CF cached" : `CF ${formatNumber(cfFetch)}ms`;

  output.innerHTML = `
    <section class="bridgecf-section">
      <h2>Bottleneck concepts</h2>
      <div class="bridgecf-concepts">${concepts || '<span class="bridgecf-muted">No specific concept flagged</span>'}</div>
    </section>
    <section class="bridgecf-section">
      <h2>Bridge problems</h2>
      <div class="bridgecf-bridge-list">${bridges || '<p class="bridgecf-muted">No bridge problem found.</p>'}</div>
    </section>
    <section class="bridgecf-section bridgecf-hints">
      <h2>Your hints</h2>
      ${hintMarkup || '<p class="bridgecf-muted">No hints available for this problem.</p>'}
    </section>
    ${rationale ? `<section class="bridgecf-rationale"><h2>Why this bridge?</h2><p>${escapeHtml(rationale)}</p></section>` : ""}
    <footer class="bridgecf-telemetry">C++ ${formatNumber(timings.graph_ms)}ms · ${cfLabel} · total ${formatNumber(Number(timings.total_ms) / 1000, 2)}s</footer>`;
}
