(function () {
  "use strict";

  const LINE_H = 22;
  const GUTTER = 52;
  const POLL_MS = 1500;

  let snapshot = null;
  let projectTree = null;
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

  function isSuggestionDismissed(sug) {
    return dismissed.has(cardKey(sug));
  }

  function buildPendingIndexes() {
    const fixByFile = {};
    const polishByFile = {};
    let fixCount = 0;
    let polishCount = 0;

    (snapshot?.suggestions || []).forEach((sug) => {
      if (isSuggestionDismissed(sug)) return;
      const file = sug.file || "";
      if (!file) return;
      fixByFile[file] = (fixByFile[file] || 0) + 1;
      fixCount += 1;
    });

    (snapshot?.polish_suggestions || []).forEach((sug) => {
      if (isSuggestionDismissed(sug)) return;
      const file = sug.file || "";
      if (!file) return;
      polishByFile[file] = (polishByFile[file] || 0) + 1;
      polishCount += 1;
    });

    return { fixByFile, polishByFile, fixCount, polishCount };
  }

  function collectFiles() {
    const files = [];
    const seen = new Set();
    const roots = projectTree?.nodes || [];
    const walk = (nodes, depth) => {
      (nodes || []).forEach((node) => {
        const path = node?.path || "";
        if (path && !seen.has(path)) {
          seen.add(path);
          files.push({
            path,
            kind: node.kind || "tex",
            depth: depth || 0,
          });
        }
        if (node?.children?.length) {
          walk(node.children, (depth || 0) + 1);
        }
      });
    };
    walk(roots, 0);

    const fallback = []
      .concat(snapshot?.suggestions || [])
      .concat(snapshot?.polish_suggestions || [])
      .concat((snapshot?.issues || []).map((i) => i.file).filter(Boolean))
      .concat(snapshot?.main_tex || []);
    fallback.forEach((entry) => {
      const f = typeof entry === "string" ? entry : entry?.file;
      if (!f || seen.has(f)) return;
      seen.add(f);
      files.push({ path: f, kind: "tex", depth: 0 });
    });
    return files;
  }

  function statusForFile(file, pending) {
    const err = Number(pending.fixByFile[file] || 0);
    const polish = Number(pending.polishByFile[file] || 0);
    return { err, polish };
  }

  function statusLabel(status) {
    const marks = [];
    if (status.err > 0) marks.push("●");
    if (status.polish > 0) marks.push("●");
    return marks.join("");
  }

  function renderGlobalStatus(pending) {
    const holder = $("file-pick-global-status");
    if (!holder) return;
    const hasErr = pending.fixCount > 0;
    const hasPolish = pending.polishCount > 0;
    const dots = [];
    if (hasErr) dots.push('<span class="status-dot error" title="存在待处理纠错卡"></span>');
    if (hasPolish) dots.push('<span class="status-dot polish" title="存在待处理润色卡"></span>');
    holder.innerHTML = dots.join("");
  }

  function renderFileSelect() {
    const sel = $("file-select");
    const polishSel = $("polish-target-file");
    const files = collectFiles();
    const pending = buildPendingIndexes();
    if (!files.length) {
      sel.innerHTML = "<option>（无 .tex）</option>";
      if (polishSel) polishSel.innerHTML = "<option>（无可用文件）</option>";
      renderGlobalStatus(pending);
      return;
    }
    const filePaths = files.map((f) => f.path);
    if (!currentFile || !filePaths.includes(currentFile)) {
      currentFile = filePaths[0];
    }
    sel.innerHTML = files
      .map(
        (item) => {
          const f = item.path;
          const status = statusForFile(f, pending);
          const labelPrefix = statusLabel(status);
          const indent = item.depth > 0 ? "  ".repeat(item.depth) + "└ " : "";
          const kindPrefix = item.kind === "bib" ? "[bib] " : "";
          const title = `${labelPrefix ? labelPrefix + " " : ""}${indent}${kindPrefix}${f}`;
          return `<option value="${escapeAttr(f)}"${f === currentFile ? " selected" : ""}>${escapeHtml(title)}</option>`;
        }
      )
      .join("");
    if (polishSel) {
      const nowTarget = polishSel.value;
      polishSel.innerHTML = files
        .map(
          (item) =>
            `<option value="${escapeAttr(item.path)}"${item.path === nowTarget ? " selected" : ""}>${escapeHtml(item.path)}</option>`
        )
        .join("");
      if (!polishSel.value) polishSel.value = currentFile;
    }
    renderGlobalStatus(pending);
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
        persistDismiss(sug);
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
    updateStats();
    renderFileSelect();
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
    const pending = buildPendingIndexes();
    const issues = snapshot.issues || [];
    const err = issues.filter((i) => i.severity === "error").length;
    const warn = issues.filter((i) => i.severity === "warning").length;
    $("stats").textContent =
      `v${snapshot.project_version} · ${err} 错误 · ${warn} 警告 · ` +
      `${pending.fixCount} 修改 · ` +
      `${pending.polishCount} 润色`;
    $("meta-root").textContent = snapshot.root || "—";
  }

  function updateCompileIndicator() {
    const bar = $("compile-indicator");
    const icon = $("compile-indicator-icon");
    const text = $("compile-indicator-text");
    if (!bar) return;
    const state = snapshot?.compile_state || (snapshot?.compile_running ? "running" : "idle");
    if (state === "idle") {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;
    if (!icon || !text) return;
    if (state === "running") {
      icon.className = "compile-icon compile-running";
      text.textContent = "正在进行编译检查";
      return;
    }
    if (state === "done") {
      icon.className = "compile-icon compile-done";
      text.textContent = "编译检查完成";
      return;
    }
    icon.className = "compile-icon compile-failed";
    text.textContent = "编译检查失败";
  }

  function persistDismiss(sug) {
    if (!sug) return;
    api("/api/ghost/dismiss", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ suggestion: sug }),
    }).catch(() => {});
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

  function loadProjectTree() {
    return api("/api/project-tree")
      .then((tree) => {
        projectTree = tree;
      })
      .catch(() => {
        projectTree = null;
      });
  }

  function refresh() {
    const prevVersion = snapshot?.project_version ?? -1;
    const prevCompileRunning = !!snapshot?.compile_running;
    return Promise.all([api("/api/snapshot"), loadProjectTree()])
      .then(([snap]) => {
        snapshot = snap;
        updateStats();
        updateCompileIndicator();
        const versionChanged = prevVersion !== (snap.project_version ?? -1);
        const compileChanged = prevCompileRunning !== !!snap.compile_running;
        if (!versionChanged && !compileChanged) return;
        renderFileSelect();
        // 不再因 error_signature 变化自动清空忽略态，避免已忽略卡片反复出现。
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
  $("trigger-compile").addEventListener("click", () => {
    api("/api/ghost/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    })
      .then(() => refresh())
      .catch((e) => alert("触发编译失败: " + e.message));
  });
  $("submit-polish").addEventListener("click", submitPolish);
  $("polish-query").addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitPolish();
  });

  refresh();
  setInterval(refresh, POLL_MS);
})();
