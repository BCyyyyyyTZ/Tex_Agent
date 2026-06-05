/**
 * 独立工具箱弹窗：绘图 + 写作辅助小工具（与工作流无关）
 */
(function () {
  "use strict";

  var overlay = null;
  var closeBtn = null;
  var openBtns = null;
  var tabs = null;
  var panes = null;

  function apiBase() {
    try {
      return new URL("/api/", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/";
    }
  }

  function qs(id) {
    return document.getElementById(id);
  }

  function setStatus(el, msg, isErr) {
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("is-error", !!isErr);
  }

  async function postJson(path, body) {
    var res = await fetch(apiBase() + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    var json = await res.json();
    if (!res.ok || !json.success) {
      throw new Error(json.error || json.detail || "请求失败");
    }
    return json;
  }

  function showImageResult(wrapId, imgId, dlId, url, filename) {
    var wrap = qs(wrapId);
    var img = qs(imgId);
    var dl = dlId ? qs(dlId) : null;
    if (!wrap || !img) return;
    var bust = url + (url.indexOf("?") >= 0 ? "&" : "?") + "t=" + Date.now();
    img.src = bust;
    if (dl) {
      dl.href = bust;
      dl.download = filename || "output.png";
    }
    wrap.hidden = false;
  }

  function showTextOutput(preId, text) {
    var el = qs(preId);
    if (!el) return;
    el.textContent = text || "";
    el.hidden = !text;
  }

  async function copyText(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    var ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
  }

  function openOverlay() {
    if (!overlay) return;
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("drawing-tools-open");
    var first = overlay.querySelector(".drawing-tools-tab.is-active");
    if (first) first.focus();
  }

  function closeOverlay() {
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("drawing-tools-open");
    var trigger = document.getElementById("drawing-tools-open");
    if (trigger) trigger.focus();
  }

  function switchTab(tabId) {
    tabs.forEach(function (btn) {
      var on = btn.getAttribute("data-tab") === tabId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    panes.forEach(function (pane) {
      var on = pane.id === "drawing-tab-" + tabId;
      pane.classList.toggle("is-active", on);
      pane.hidden = !on;
    });
  }

  function parseChartData(raw) {
    var txt = (raw || "").trim();
    if (!txt) throw new Error("数据 JSON 不能为空");
    var obj = JSON.parse(txt);
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      throw new Error("数据必须是 JSON 对象");
    }
    return obj;
  }

  async function submitChart(ev) {
    ev.preventDefault();
    var statusEl = qs("chart-plot-status");
    var btn = qs("chart-plot-submit");
    setStatus(statusEl, "正在生成…", false);
    if (btn) btn.disabled = true;
    try {
      var json = await postJson("drawing/chart-plot", {
        chart_type: qs("chart-type").value,
        data: parseChartData(qs("chart-data-json").value),
        title: (qs("chart-title").value || "").trim(),
        x_label: (qs("chart-x-label").value || "").trim(),
        y_label: (qs("chart-y-label").value || "").trim(),
      });
      showImageResult("chart-plot-result", "chart-plot-img", "chart-plot-download", json.output_url, "chart.png");
      setStatus(statusEl, "图表已生成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function submitDiagram(ev) {
    ev.preventDefault();
    var statusEl = qs("concept-diagram-status");
    var btn = qs("concept-diagram-submit");
    setStatus(statusEl, "正在生成…", false);
    if (btn) btn.disabled = true;
    try {
      var json = await postJson("drawing/concept-diagram", {
        prompt: (qs("diagram-prompt").value || "").trim(),
        title: (qs("diagram-title").value || "").trim(),
        mermaid_code: (qs("diagram-mermaid").value || "").trim(),
      });
      showImageResult("concept-diagram-result", "concept-diagram-img", "concept-diagram-download", json.output_url, "diagram.png");
      if (json.mermaid_code) showTextOutput("concept-diagram-code", json.mermaid_code);
      setStatus(statusEl, "概念图已生成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function submitLatex(ev) {
    ev.preventDefault();
    var statusEl = qs("latex-table-status");
    setStatus(statusEl, "正在生成…", false);
    try {
      var json = await postJson("drawing/latex-table", {
        headers: (qs("latex-headers").value || "").trim(),
        rows: (qs("latex-rows").value || "").trim(),
        caption: (qs("latex-caption").value || "").trim(),
        label: (qs("latex-label").value || "").trim(),
        highlight_best: !!(qs("latex-highlight-best") && qs("latex-highlight-best").checked),
      });
      showTextOutput("latex-table-output", json.output_text);
      setStatus(statusEl, "LaTeX 已生成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    }
  }

  function renderPaletteSwatches(colors) {
    var wrap = qs("palette-swatches");
    if (!wrap) return;
    wrap.innerHTML = "";
    (colors || []).forEach(function (c) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "palette-chip";
      chip.style.background = c;
      chip.title = "点击复制 " + c;
      chip.textContent = c;
      chip.addEventListener("click", function () {
        copyText(c).then(function () {
          setStatus(qs("palette-status"), "已复制 " + c, false);
        });
      });
      wrap.appendChild(chip);
    });
    wrap.hidden = !(colors && colors.length);
  }

  async function submitPalette(ev) {
    ev.preventDefault();
    var statusEl = qs("palette-status");
    setStatus(statusEl, "正在生成…", false);
    try {
      var json = await postJson("drawing/palette", {
        theme: qs("palette-theme").value,
        count: Number(qs("palette-count").value || 6),
      });
      renderPaletteSwatches((json.metadata && json.metadata.colors) || []);
      showImageResult("palette-result", "palette-img", null, json.output_url, "palette.png");
      var meta = json.metadata || {};
      var descEl = qs("palette-desc");
      if (descEl) {
        var label = meta.theme_label || meta.theme || "";
        var desc = meta.description || "";
        descEl.textContent = label ? label + (desc ? " — " + desc : "") : desc;
        descEl.hidden = !(label || desc);
      }
      setStatus(statusEl, "配色已生成（点击色块可复制 HEX）", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    }
  }

  async function submitTextStats(ev) {
    ev.preventDefault();
    var statusEl = qs("text-stats-status");
    setStatus(statusEl, "正在统计…", false);
    try {
      var json = await postJson("drawing/text-stats", {
        text: (qs("text-stats-input").value || "").trim(),
      });
      showTextOutput("text-stats-output", json.output_text);
      setStatus(statusEl, "统计完成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    }
  }

  async function submitPaperTitle(ev) {
    ev.preventDefault();
    var statusEl = qs("paper-title-status");
    var useLlm = !!(qs("paper-title-use-llm") && qs("paper-title-use-llm").checked);
    setStatus(statusEl, useLlm ? "正在生成（3 本地 + 2 AI）…" : "正在生成（本地模板）…", false);
    try {
      var json = await postJson("drawing/paper-title", {
        keywords: (qs("paper-title-keywords").value || "").trim(),
        style: qs("paper-title-style").value,
        count: 5,
        use_llm: useLlm,
      });
      showTextOutput("paper-title-output", json.output_text);
      var meta = json.metadata || {};
      var mode = meta.mode || "";
      var skipped = meta.api_skipped_reason || "";
      var statusMsg = mode === "hybrid"
        ? "已生成（3 本地 + 2 AI）"
        : mode === "template-only"
          ? "已生成（仅本地模板）"
          : "已生成（本地模板，AI 未返回有效结果）";
      if (skipped) statusMsg += " — " + skipped;
      setStatus(statusEl, statusMsg, skipped && mode !== "hybrid");
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    }
  }

  async function submitQrcode(ev) {
    ev.preventDefault();
    var statusEl = qs("qrcode-status");
    setStatus(statusEl, "正在生成…", false);
    try {
      var json = await postJson("drawing/qrcode", {
        content: (qs("qrcode-content").value || "").trim(),
      });
      showImageResult("qrcode-result", "qrcode-img", "qrcode-download", json.output_url, "qrcode.png");
      setStatus(statusEl, "QR 码已生成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    }
  }

  function resetChart() {
    var f = qs("chart-plot-form");
    if (f) f.reset();
    qs("chart-data-json").value = '{"x": ["A", "B", "C"], "y": [3, 5, 2]}';
    setStatus(qs("chart-plot-status"), "", false);
    qs("chart-plot-result").hidden = true;
  }

  function resetDiagram() {
    var f = qs("concept-diagram-form");
    if (f) f.reset();
    qs("diagram-mermaid").value = "flowchart TB\n  A[数据采集] --> B[预处理]\n  B --> C[索引构建]\n  C --> D[在线检索]\n  D --> E[生成回答]";
    setStatus(qs("concept-diagram-status"), "", false);
    qs("concept-diagram-result").hidden = true;
    qs("concept-diagram-code").hidden = true;
  }

  function resetLatex() {
    qs("latex-headers").value = "Method, Accuracy, F1";
    qs("latex-rows").value = '[["BERT", "0.91", "0.88"], ["GPT", "0.93", "0.90"], ["Ours", "0.95", "0.92"]]';
    qs("latex-caption").value = "";
    qs("latex-label").value = "";
    var hl = qs("latex-highlight-best");
    if (hl) hl.checked = false;
    setStatus(qs("latex-table-status"), "", false);
    qs("latex-table-output").hidden = true;
  }

  function resetPalette() {
    qs("palette-theme").value = "academic";
    qs("palette-count").value = "6";
    setStatus(qs("palette-status"), "", false);
    var descEl = qs("palette-desc");
    if (descEl) {
      descEl.textContent = "";
      descEl.hidden = true;
    }
    qs("palette-swatches").hidden = true;
    qs("palette-result").hidden = true;
  }

  function resetTextStats() {
    qs("text-stats-input").value = "";
    setStatus(qs("text-stats-status"), "", false);
    qs("text-stats-output").hidden = true;
  }

  function resetPaperTitle() {
    qs("paper-title-keywords").value = "";
    qs("paper-title-style").value = "serious";
    var useLlm = qs("paper-title-use-llm");
    if (useLlm) useLlm.checked = true;
    setStatus(qs("paper-title-status"), "", false);
    qs("paper-title-output").hidden = true;
  }

  function resetQrcode() {
    qs("qrcode-content").value = "";
    setStatus(qs("qrcode-status"), "", false);
    qs("qrcode-result").hidden = true;
  }

  function bindTabs() {
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        switchTab(btn.getAttribute("data-tab"));
      });
    });
  }

  function bindForms() {
    var chartForm = qs("chart-plot-form");
    var diagramForm = qs("concept-diagram-form");
    if (chartForm) chartForm.addEventListener("submit", submitChart);
    if (diagramForm) diagramForm.addEventListener("submit", submitDiagram);
    qs("latex-table-form") && qs("latex-table-form").addEventListener("submit", submitLatex);
    qs("palette-form") && qs("palette-form").addEventListener("submit", submitPalette);
    qs("text-stats-form") && qs("text-stats-form").addEventListener("submit", submitTextStats);
    qs("paper-title-form") && qs("paper-title-form").addEventListener("submit", submitPaperTitle);
    qs("qrcode-form") && qs("qrcode-form").addEventListener("submit", submitQrcode);

    qs("chart-plot-reset") && qs("chart-plot-reset").addEventListener("click", resetChart);
    qs("concept-diagram-reset") && qs("concept-diagram-reset").addEventListener("click", resetDiagram);
    qs("latex-table-reset") && qs("latex-table-reset").addEventListener("click", resetLatex);
    qs("palette-reset") && qs("palette-reset").addEventListener("click", resetPalette);
    qs("text-stats-reset") && qs("text-stats-reset").addEventListener("click", resetTextStats);
    qs("paper-title-reset") && qs("paper-title-reset").addEventListener("click", resetPaperTitle);
    qs("qrcode-reset") && qs("qrcode-reset").addEventListener("click", resetQrcode);

    qs("latex-table-copy") &&
      qs("latex-table-copy").addEventListener("click", function () {
        var t = qs("latex-table-output").textContent;
        copyText(t).then(function () {
          setStatus(qs("latex-table-status"), "LaTeX 已复制到剪贴板", false);
        });
      });
    qs("paper-title-copy") &&
      qs("paper-title-copy").addEventListener("click", function () {
        var t = qs("paper-title-output").textContent;
        copyText(t).then(function () {
          setStatus(qs("paper-title-status"), "标题已复制到剪贴板", false);
        });
      });

    var chartType = qs("chart-type");
    var chartData = qs("chart-data-json");
    if (chartType && chartData) {
      chartType.addEventListener("change", function () {
        if (chartType.value === "pie") {
          chartData.value = '{"labels": ["A", "B", "C"], "values": [40, 35, 25]}';
        } else {
          chartData.value = '{"x": ["A", "B", "C"], "y": [3, 5, 2]}';
        }
      });
    }
  }

  function bindOpenClose() {
    openBtns = document.querySelectorAll("[data-drawing-tools-open]");
    openBtns.forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openOverlay();
      });
    });
    if (closeBtn) closeBtn.addEventListener("click", closeOverlay);
    if (overlay) {
      overlay.addEventListener("click", function (ev) {
        if (ev.target === overlay) closeOverlay();
      });
    }
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && overlay && overlay.classList.contains("is-open")) {
        closeOverlay();
      }
    });
  }

  function init() {
    overlay = qs("drawing-tools-overlay");
    closeBtn = qs("drawing-tools-close");
    tabs = Array.prototype.slice.call(document.querySelectorAll(".drawing-tools-tab"));
    panes = Array.prototype.slice.call(document.querySelectorAll(".drawing-tools-pane"));
    bindOpenClose();
    bindTabs();
    bindForms();
  }

  window.TexAgentDrawingTools = { open: openOverlay, close: closeOverlay };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
