if (!window.bridgeCFHintInjected) {
  window.bridgeCFHintInjected = true;
  window.addEventListener("load", injectHintUI);
  if (document.readyState === "complete") injectHintUI();
}

function parseProblemId(pathname) {
  const problemset = pathname.match(/^\/problemset\/problem\/([0-9]+)\/([A-Za-z0-9]+)\/?$/i);
  if (problemset) return `${problemset[1]}_${problemset[2].toUpperCase()}`;
  const contest = pathname.match(/^\/(?:contest|gym)\/([0-9]+)\/problem\/([A-Za-z0-9]+)\/?$/i);
  if (contest) return `${contest[1]}_${contest[2].toUpperCase()}`;
  return null;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function badge(label, value) {
  return `<span class="bridgecf-badge"><b>${escapeHtml(label)}</b> ${escapeHtml(Number(value).toFixed(2))}</span>`;
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
  if (document.querySelector("#bridgecf-hint-panel")) return;
  const problemId = parseProblemId(window.location.pathname);
  if (!problemId) return;

  const panel = document.createElement("section");
  panel.id = "bridgecf-hint-panel";
  panel.innerHTML = `
    <div class="bridgecf-header">
      <div><strong>Adaptive Hint Engine</strong><span id="bridgecf-provider"></span></div>
      <button id="bridgecf-close" type="button" aria-label="Close">×</button>
    </div>
    <button id="bridgecf-get-hint" type="button">Get Adaptive Hint</button>
    <div id="bridgecf-output" aria-live="polite"></div>
  `;

  const sidebar = document.querySelector("#sidebar");
  if (sidebar) {
    panel.classList.add("bridgecf-sidebar");
    sidebar.insertBefore(panel, sidebar.firstChild);
  } else {
    document.body.appendChild(panel);
  }

  panel.querySelector("#bridgecf-close").addEventListener("click", () => panel.remove());
  panel.querySelector("#bridgecf-get-hint").addEventListener("click", async () => {
    const output = panel.querySelector("#bridgecf-output");
    output.innerHTML = '<span class="bridgecf-loading">Querying BridgeCF...</span>';
    const handle = await resolveHandle();
    if (!handle) {
      output.textContent = "A Codeforces handle is required.";
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
        if (chrome.runtime.lastError) {
          output.textContent = `Extension error: ${chrome.runtime.lastError.message}`;
          return;
        }
        if (!response?.ok) {
          output.textContent = response?.error || "The hint request failed.";
          return;
        }
        renderHint(response.data, output, panel);
      },
    );
  });
}

function renderHint(data, output, panel) {
  panel.querySelector("#bridgecf-provider").textContent =
    ` · ${data.provider || "unknown"}${data.fallback_used ? " · fallback" : ""}`;

  const concepts = (data.missing_concepts || [])
    .map((concept) => `<span class="bridgecf-concept">${escapeHtml(concept)}</span>`)
    .join("");

  const bridges = (data.bridge_problems || []).map((item) => {
    const problem = item.problem || {};
    return `
      <li>
        <a href="${escapeHtml(problem.url || "#")}" target="_blank" rel="noopener">
          ${escapeHtml(problem.problem_id)}${problem.rating ? ` · ${escapeHtml(problem.rating)}` : ""}
        </a>
        <div>
          ${badge("semantic", item.semantic_score)}
          ${badge("concept", item.concept_score)}
          ${badge("difficulty", item.difficulty_score)}
          ${badge("final", item.final_score)}
        </div>
      </li>`;
  }).join("");

  const hint = data.hint || {};
  const timings = data.timings_ms || {};
  output.innerHTML = `
    <div class="bridgecf-section">
      <h5>Bottleneck concepts</h5>
      <div>${concepts || '<span class="bridgecf-muted">None identified</span>'}</div>
    </div>
    <div class="bridgecf-section">
      <h5>Top bridge problems</h5>
      <ol>${bridges || "<li>No bridge problem found</li>"}</ol>
    </div>
    <div class="bridgecf-section bridgecf-hints">
      <button type="button" data-hint="1">Hint 1: Conceptual Nudge</button>
      <div data-hint-content="1" hidden>${escapeHtml(hint.conceptual_nudge)}</div>
      <button type="button" data-hint="2">Hint 2: Strategy Hint</button>
      <div data-hint-content="2" hidden>${escapeHtml(hint.strategy_hint)}</div>
      <button type="button" data-hint="3">Hint 3: Complexity Nudge</button>
      <div data-hint-content="3" hidden>${escapeHtml(hint.complexity_nudge)}</div>
      <button type="button" data-hint="4">Why This Bridge Problem</button>
      <div data-hint-content="4" hidden>${escapeHtml(hint.bridge_rationale)}</div>
    </div>
    <div class="bridgecf-timing">
      graph ${escapeHtml(timings.graph_ms?.toFixed?.(1) ?? timings.graph_ms)} ms ·
      CF fetch ${escapeHtml(timings.cf_fetch_ms?.toFixed?.(1) ?? timings.cf_fetch_ms)} ms ·
      total ${escapeHtml(timings.total_ms?.toFixed?.(1) ?? timings.total_ms)} ms
    </div>`;

  output.querySelectorAll("[data-hint]").forEach((button) => {
    button.addEventListener("click", () => {
      const content = output.querySelector(
        `[data-hint-content="${button.dataset.hint}"]`,
      );
      content.hidden = !content.hidden;
    });
  });
}
