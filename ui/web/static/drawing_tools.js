/**
 * 独立绘图工具弹窗：统计图表 + 概念示意图（与工作流无关）
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

  function showChartResult(url) {
    var wrap = qs("chart-plot-result");
    var img = qs("chart-plot-img");
    var dl = qs("chart-plot-download");
    if (!wrap || !img) return;
    var bust = url + (url.indexOf("?") >= 0 ? "&" : "?") + "t=" + Date.now();
    img.src = bust;
    if (dl) {
      dl.href = bust;
      dl.download = "chart.png";
    }
    wrap.hidden = false;
  }

  function showDiagramResult(url, mermaidCode) {
    var wrap = qs("concept-diagram-result");
    var img = qs("concept-diagram-img");
    var dl = qs("concept-diagram-download");
    var codeEl = qs("concept-diagram-code");
    if (!wrap || !img) return;
    var bust = url + (url.indexOf("?") >= 0 ? "&" : "?") + "t=" + Date.now();
    img.src = bust;
    if (dl) {
      dl.href = bust;
      dl.download = "diagram.png";
    }
    wrap.hidden = false;
    if (codeEl) {
      if (mermaidCode) {
        codeEl.textContent = mermaidCode;
        codeEl.hidden = false;
      } else {
        codeEl.hidden = true;
      }
    }
  }

  async function submitChart(ev) {
    ev.preventDefault();
    var statusEl = qs("chart-plot-status");
    var btn = qs("chart-plot-submit");
    setStatus(statusEl, "正在生成…", false);
    if (btn) btn.disabled = true;
    try {
      var data = parseChartData(qs("chart-data-json").value);
      var body = {
        chart_type: qs("chart-type").value,
        data: data,
        title: (qs("chart-title").value || "").trim(),
        x_label: (qs("chart-x-label").value || "").trim(),
        y_label: (qs("chart-y-label").value || "").trim(),
      };
      var res = await fetch(apiBase() + "drawing/chart-plot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      var json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.error || json.detail || "请求失败");
      }
      showChartResult(json.output_url);
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
      var body = {
        prompt: (qs("diagram-prompt").value || "").trim(),
        title: (qs("diagram-title").value || "").trim(),
        mermaid_code: (qs("diagram-mermaid").value || "").trim(),
      };
      var res = await fetch(apiBase() + "drawing/concept-diagram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      var json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.error || json.detail || "请求失败");
      }
      showDiagramResult(json.output_url, json.mermaid_code);
      setStatus(statusEl, "概念图已生成", false);
    } catch (e) {
      setStatus(statusEl, String(e.message || e), true);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bindTabs() {
    tabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        switchTab(btn.getAttribute("data-tab"));
      });
    });
  }

  function resetChart() {
    var f = qs("chart-plot-form");
    if (f) f.reset();
    var chartData = qs("chart-data-json");
    if (chartData) chartData.value = '{"x": ["A", "B", "C"], "y": [3, 5, 2]}';
    setStatus(qs("chart-plot-status"), "", false);
    var wrap = qs("chart-plot-result");
    if (wrap) wrap.hidden = true;
  }

  function resetDiagram() {
    var f = qs("concept-diagram-form");
    if (f) f.reset();
    var mermaid = qs("diagram-mermaid");
    if (mermaid) mermaid.value = "flowchart TB\n  A[数据采集] --> B[预处理]\n  B --> C[索引构建]\n  C --> D[在线检索]\n  D --> E[生成回答]";
    setStatus(qs("concept-diagram-status"), "", false);
    var wrap = qs("concept-diagram-result");
    if (wrap) wrap.hidden = true;
    var codeEl = qs("concept-diagram-code");
    if (codeEl) codeEl.hidden = true;
  }

  function bindForms() {
    var chartForm = qs("chart-plot-form");
    var diagramForm = qs("concept-diagram-form");
    if (chartForm) chartForm.addEventListener("submit", submitChart);
    if (diagramForm) diagramForm.addEventListener("submit", submitDiagram);

    var resetChartBtn = qs("chart-plot-reset");
    if (resetChartBtn) resetChartBtn.addEventListener("click", resetChart);
    var resetDiagramBtn = qs("concept-diagram-reset");
    if (resetDiagramBtn) resetDiagramBtn.addEventListener("click", resetDiagram);

    var chartType = qs("chart-type");
    var chartData = qs("chart-data-json");
    if (chartType && chartData) {
      chartType.addEventListener("change", function () {
        var ct = chartType.value;
        if (ct === "pie") {
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
