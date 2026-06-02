(function () {
  "use strict";

  const LINE_H = 22;
  const GUTTER = 52;
  const POLL_MS = 1500;

  let snapshot = null;
  let currentFile = "";
  let fileLines = [];
  let dismissed = new Set();
  let cardPositions = {};

  const $ = (id) => document.getElementById(id);

  function api(path, opts) {
    return fetch(path, opts).then((r) => {
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    });
  }

  function lineFromSuggestion(sug) {
    const r = sug.range || {};
    const start = r.start || {};
    return (start.line ?? 0) + 1;
  }

  function cardKey(sug) {
    return (
      (sug.request_id || "") +
      ":" +
      (sug.file || "") +
      ":" +
      lineFromSuggestion(sug)
    );
  }

  function collectFiles() {
    const set = new Set();
    if (snapshot && snapshot.main_tex) set.add(snapshot.main_tex);
    const all = []
      .concat(snapshot?.suggestions || [])
      .concat(snapshot?.polish_suggestions || [])
      .concat(
        (snapshot?.issues || []).map((i) => i.file).filter(Boolean)
      );
    all.forEach((f) => set.add(f));
    return Array.from(set).sort();
  }

  function renderFileSelect() {
    const sel = $("file-select");
    const files = collectFiles();
    if (!files.length) {
      sel.innerHTML = "<option>（无 .tex）</option>";
      return;
    }
    if (!currentFile || !files.includes(currentFile)) {
      currentFile = files[0];
    }
    sel.innerHTML = files
      .map(
        (f) =>
          `<option value="${escapeAttr(f)}"${f === currentFile ? " selected" : ""}>${escapeHtml(f)}</option>`
      )
      .join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/"/g, "&quot;");
  }

  function issuesForLine(lineNo) {
    return (snapshot?.issues || []).filter(
      (i) => i.file === currentFile && i.line === lineNo
    );
  }

  function renderSource() {
    const panel = $("source-panel");
    const html = fileLines
      .map((text, idx) => {
        const lineNo = idx + 1;
        const issues = issuesForLine(lineNo);
        let inner = escapeHtml(text || " ");
        issues.forEach((iss) => {
          const cls =
            iss.severity === "error" ? "issue-error" : "issue-warn";
          inner = `<mark class="${cls}" title="${escapeAttr(iss.message || "")}">${inner}</mark>`;
        });
        return `<div class="line-row" data-line="${lineNo}"><span class="line-gutter">${lineNo}</span><span class="line-text">${inner}</span></div>`;
      })
      .join("");
    panel.innerHTML = html || '<div class="line-row"><span class="line-gutter">1</span><span class="line-text">（空文件）</span></div>';
    panel.style.setProperty("--gutter", GUTTER + "px");
  }

  function suggestionsForFile() {
    const fix = (snapshot?.suggestions || []).filter(
      (s) => s.file === currentFile
    );
    const showPolish = $("show-polish").checked;
    const polish = showPolish
      ? (snapshot?.polish_suggestions || []).filter(
          (s) => s.file === currentFile
        )
      : [];
    return fix.map((s) => ({ sug: s, kind: "fix" })).concat(
      polish.map((s) => ({ sug: s, kind: "polish" }))
    );
  }

  function renderGhostCards() {
    const layer = $("ghost-layer");
    layer.innerHTML = "";
    if (!$("ghost-enabled").checked) return;

    const items = suggestionsForFile();
    const wrap = $("editor-wrap");
    const scrollTop = wrap.scrollTop;

    items.forEach((item, index) => {
      const sug = item.sug;
      const key = cardKey(sug);
      if (dismissed.has(key)) return;

      const lineNo = lineFromSuggestion(sug);
      const top =
        12 +
        (lineNo - 1) * LINE_H -
        scrollTop +
        (cardPositions[key]?.dy || 0);
      const left =
        GUTTER + 8 + (cardPositions[key]?.dx || index * 12);

      const card = document.createElement("div");
      card.className = `ghost-card kind-${item.kind}`;
      card.dataset.key = key;
      card.dataset.line = String(lineNo);
      card.style.top = Math.max(12, top) + "px";
      card.style.left = left + "px";
      if (cardPositions[key]?.w) {
        card.style.width = cardPositions[key].w + "px";
        card.style.height = cardPositions[key].h + "px";
      }

      const title =
        item.kind === "fix" ? "修改建议" : "润色建议";
      const rep = (sug.replacement || "").trim();
      card.innerHTML = `
        <div class="card-head"><span>${title} · 行 ${lineNo}</span><span>⠿</span></div>
        <div class="card-body">
          <div class="rationale">${escapeHtml(sug.rationale_zh || sug.message || "（无说明）")}</div>
          ${rep ? `<pre class="replacement">${escapeHtml(rep)}</pre>` : ""}
        </div>
        <div class="card-actions">
          ${rep ? '<button type="button" class="primary btn-apply">应用</button>' : ""}
          <button type="button" class="btn-dismiss">忽略</button>
        </div>
      `;

      setupDrag(card, key);
      const applyBtn = card.querySelector(".btn-apply");
      if (applyBtn) {
        applyBtn.addEventListener("click", () => applySuggestion(sug, key));
      }
      card.querySelector(".btn-dismiss").addEventListener("click", () => {
        dismissed.add(key);
        card.classList.add("dismissed");
      });

      layer.appendChild(card);
    });
  }

  function setupDrag(card, key) {
    const head = card.querySelector(".card-head");
    let startX, startY, origDx, origDy;

    head.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      startX = e.clientX;
      startY = e.clientY;
      origDx = cardPositions[key]?.dx || 0;
      origDy = cardPositions[key]?.dy || 0;

      function onMove(ev) {
        const dx = origDx + (ev.clientX - startX);
        const dy = origDy + (ev.clientY - startY);
        cardPositions[key] = {
          ...(cardPositions[key] || {}),
          dx,
          dy,
        };
        const lineNo = parseInt(card.dataset.line || "1", 10);
        const top =
          12 +
          (lineNo - 1) * LINE_H -
          $("editor-wrap").scrollTop +
          dy;
        card.style.top = Math.max(12, top) + "px";
        card.style.left = GUTTER + 8 + dx + "px";
      }

      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        saveCardGeom(card, key);
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    const ro = new ResizeObserver(() => saveCardGeom(card, key));
    ro.observe(card);
  }

  function saveCardGeom(card, key) {
    cardPositions[key] = {
      ...(cardPositions[key] || {}),
      dx: cardPositions[key]?.dx || 0,
      dy: cardPositions[key]?.dy || 0,
      w: card.offsetWidth,
      h: card.offsetHeight,
    };
  }

  function applySuggestion(sug, key) {
    api("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestion: sug }),
    })
      .then(() => {
        dismissed.add(key);
        refresh();
      })
      .catch((e) => alert("应用失败: " + e.message));
  }

  function updateStats() {
    if (!snapshot) return;
    const issues = snapshot.issues || [];
    const err = issues.filter((i) => i.severity === "error").length;
    const warn = issues.filter((i) => i.severity === "warning").length;
    $("stats").textContent =
      `v${snapshot.project_version} · ${err} 错误 · ${warn} 警告 · ` +
      `${(snapshot.suggestions || []).length} 修改 · ` +
      `${(snapshot.polish_suggestions || []).length} 润色`;
    $("meta-root").textContent = snapshot.root || "—";
  }

  function loadFile() {
    if (!currentFile) return Promise.resolve();
    return api("/api/file?path=" + encodeURIComponent(currentFile)).then(
      (data) => {
        fileLines = data.lines || [];
        renderSource();
        renderGhostCards();
      }
    );
  }

  function refresh() {
    return api("/api/snapshot")
      .then((snap) => {
        const prevVer = snapshot?.project_version;
        snapshot = snap;
        updateStats();
        renderFileSelect();
        if (prevVer !== snap.project_version) {
          dismissed.clear();
        }
        return loadFile();
      })
      .catch((e) => {
        $("stats").textContent = "连接失败: " + e.message;
      });
  }

  $("file-select").addEventListener("change", (e) => {
    currentFile = e.target.value;
    loadFile();
  });
  $("show-polish").addEventListener("change", () => renderGhostCards());
  $("ghost-enabled").addEventListener("change", () => renderGhostCards());
  $("editor-wrap").addEventListener("scroll", () => renderGhostCards());

  refresh();
  setInterval(refresh, POLL_MS);
})();
