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
  let activeFixLineSet = new Set();
  let activePolishLineSet = new Set();

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

  function normalizeLineNo(lineNo) {
    const total = fileLines.length || 1;
    return Math.max(1, Math.min(lineNo, total));
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
    const polishSel = $("polish-target-file");
    const files = collectFiles();
    if (!files.length) {
      sel.innerHTML = "<option>（无 .tex）</option>";
      if (polishSel) polishSel.innerHTML = "<option>（无可用文件）</option>";
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
    if (polishSel) {
      const nowTarget = polishSel.value;
      polishSel.innerHTML = files
        .map(
          (f) =>
            `<option value="${escapeAttr(f)}"${f === nowTarget ? " selected" : ""}>${escapeHtml(f)}</option>`
        )
        .join("");
      if (!polishSel.value) polishSel.value = currentFile;
    }
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

  function findIssueForSuggestion(sug) {
    const issueId = sug.issue_id || "";
    if (!issueId) return null;
    return (snapshot?.issues || []).find((i) => i.id === issueId) || null;
  }

  function buildActiveFixLineSet() {
    const lines = new Set();
    const fixes = (snapshot?.suggestions || []).filter(
      (s) => s.file === currentFile
    );
    fixes.forEach((sug) => {
      const key = cardKey(sug);
      if (dismissed.has(key)) return;
      const start = (sug.range?.start?.line ?? 0) + 1;
      const end = (sug.range?.end?.line ?? sug.range?.start?.line ?? 0) + 1;
      const lo = normalizeLineNo(Math.min(start, end));
      const hi = normalizeLineNo(Math.max(start, end));
      for (let line = lo; line <= hi; line += 1) {
        lines.add(line);
      }
    });
    activeFixLineSet = lines;
  }

  function buildActivePolishLineSet() {
    const lines = new Set();
    if (!$("show-polish").checked) {
      activePolishLineSet = lines;
      return;
    }
    const polish = (snapshot?.polish_suggestions || []).filter(
      (s) => s.file === currentFile
    );
    polish.forEach((sug) => {
      const key = cardKey(sug);
      if (dismissed.has(key)) return;
      const start = (sug.range?.start?.line ?? 0) + 1;
      const end = (sug.range?.end?.line ?? sug.range?.start?.line ?? 0) + 1;
      const lo = normalizeLineNo(Math.min(start, end));
      const hi = normalizeLineNo(Math.max(start, end));
      for (let line = lo; line <= hi; line += 1) {
        lines.add(line);
      }
    });
    activePolishLineSet = lines;
  }

  function renderSource() {
    const panel = $("source-panel");
    const html = fileLines
      .map((text, idx) => {
        const lineNo = idx + 1;
        let inner = escapeHtml(text || " ");
        if (activeFixLineSet.has(lineNo)) {
          inner = `<mark class="suggestion-error" title="待修正范围">${inner}</mark>`;
        } else if (activePolishLineSet.has(lineNo)) {
          inner = `<mark class="suggestion-polish" title="待润色范围">${inner}</mark>`;
        }
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

      const lineNo = normalizeLineNo(lineFromSuggestion(sug));
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

      const title = item.kind === "fix" ? "报错修正建议" : "润色建议";
      const rep = (sug.replacement || "").trim();
      const issue = item.kind === "fix" ? findIssueForSuggestion(sug) : null;
      const issueMsg = issue?.message || sug.message || "（无报错信息）";
      const cause = sug.cause_zh || sug.rationale_zh || "（无原因分析）";
      const advice =
        sug.advice_zh ||
        (rep ? "将定位范围替换为建议文本，预计可消除该报错。" : "（无修改方案）");
      const location = `${escapeHtml(sug.file || currentFile)}:${lineNo}`;
      card.innerHTML = `
        <div class="card-head"><span>${title} · 行 ${lineNo}</span><span>⠿</span></div>
        <div class="card-body">
          ${
            item.kind === "fix"
              ? `<div class="field"><span class="label">报错信息</span><div class="value">${escapeHtml(issueMsg)}</div></div>
                 <div class="field"><span class="label">定位</span><div class="value mono">${location}</div></div>
                 <div class="field"><span class="label">原因分析</span><div class="value">${escapeHtml(cause)}</div></div>
                 <div class="field"><span class="label">改正方案</span><div class="value">${escapeHtml(advice)}</div></div>`
              : `<div class="rationale">${escapeHtml(sug.rationale_zh || sug.message || "（无说明）")}</div>`
          }
          ${rep ? `<pre class="replacement">${escapeHtml(rep)}</pre>` : ""}
        </div>
        <div class="card-actions">
          ${rep ? '<button type="button" class="primary btn-apply">应用</button>' : ""}
          ${rep ? '<button type="button" class="btn-compare">对比</button>' : ""}
          <button type="button" class="btn-dismiss">忽略</button>
        </div>
      `;

      setupDrag(card, key);
      const applyBtn = card.querySelector(".btn-apply");
      if (applyBtn) {
        applyBtn.addEventListener("click", () =>
          applySuggestion(sug, key, "replace")
        );
      }
      const compareBtn = card.querySelector(".btn-compare");
      if (compareBtn) {
        compareBtn.addEventListener("click", () =>
          applySuggestion(sug, key, "compare")
        );
      }
      card.querySelector(".btn-dismiss").addEventListener("click", () => {
        dismissCard(key, card);
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

  function dismissCard(key, card) {
    dismissed.add(key);
    if (card) card.classList.add("dismissed");
    buildActiveFixLineSet();
    buildActivePolishLineSet();
    renderSource();
    renderGhostCards();
  }

  function applySuggestion(sug, key, mode) {
    api("/api/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestion: sug, mode: mode || "replace" }),
    })
      .then(() => {
        dismissCard(key, null);
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
        buildActiveFixLineSet();
        buildActivePolishLineSet();
        renderSource();
        renderGhostCards();
      }
    );
  }

  function submitPolish() {
    const targetFile = $("polish-target-file").value || currentFile;
    const query = ($("polish-query").value || "").trim();
    if (!query) {
      $("polish-status").textContent = "请输入润色需求";
      return;
    }
    $("polish-status").textContent = "生成中…";
    api("/api/ghost/polish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        target_file: targetFile,
        context_file: currentFile || targetFile,
      }),
    })
      .then(() => {
        $("polish-status").textContent = "润色建议已生成";
        refresh();
      })
      .catch((e) => {
        $("polish-status").textContent = "生成失败";
        alert("润色失败: " + e.message);
      });
  }

  function refresh() {
    return api("/api/snapshot")
      .then((snap) => {
        const prevErrorSig = snapshot?.error_signature || "";
        snapshot = snap;
        updateStats();
        renderFileSelect();
        const nextErrorSig = snap.error_signature || "";
        if (prevErrorSig !== nextErrorSig) {
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
  $("show-polish").addEventListener("change", () => {
    buildActivePolishLineSet();
    renderSource();
    renderGhostCards();
  });
  $("ghost-enabled").addEventListener("change", () => renderGhostCards());
  $("editor-wrap").addEventListener("scroll", () => renderGhostCards());
  $("toggle-polish-panel").addEventListener("click", () => {
    const panel = $("polish-panel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden) {
      $("polish-target-file").value = currentFile;
      $("polish-query").focus();
    }
  });
  $("submit-polish").addEventListener("click", submitPolish);
  $("polish-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitPolish();
  });

  refresh();
  setInterval(refresh, POLL_MS);
})();
