/**
 * 五列布局：拖动竖条调节 RAG / 工作流 / 分支 / 资料栏 宽度；中间区域 flex 伸缩。
 * 列间竖条在 CSS 中为 0 宽，靠伪元素保留拖曳命中区。
 * 宽度存 localStorage：texagent.layout.widths
 */
(function () {
  "use strict";

  var LS_KEY = "texagent.layout.widths";
  var DEFAULTS = { wf: 440, branch: 320, right: 300, rag: 340 };
  var MIN = { wf: 160, branch: 150, right: 180, rag: 220 };
  var MAX = { wf: 580, branch: 480, right: 520, rag: 560 };

  function load() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return Object.assign({}, DEFAULTS);
      var o = JSON.parse(raw);
      if (
        typeof o.wf !== "number" ||
        typeof o.branch !== "number" ||
        typeof o.right !== "number"
      ) {
        return Object.assign({}, DEFAULTS);
      }
      return {
        wf: clamp(o.wf, MIN.wf, MAX.wf),
        branch: clamp(o.branch, MIN.branch, MAX.branch),
        right: clamp(o.right, MIN.right, MAX.right),
        rag: clamp(
          typeof o.rag === "number" ? o.rag : DEFAULTS.rag,
          MIN.rag,
          MAX.rag
        ),
      };
    } catch (_e) {
      return Object.assign({}, DEFAULTS);
    }
  }

  function save(w) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(w));
    } catch (_e) {
      /* ignore */
    }
  }

  function clamp(n, lo, hi) {
    return Math.max(lo, Math.min(hi, n));
  }

  function applyWidths(w) {
    var elWf = document.getElementById("col-wf");
    var elBr = document.getElementById("col-branch");
    var elRt = document.getElementById("col-right");
    var elRag = document.getElementById("col-rag");
    if (elWf) {
      elWf.style.flex = "0 0 " + w.wf + "px";
      elWf.style.width = w.wf + "px";
    }
    if (elBr) {
      elBr.style.flex = "0 0 " + w.branch + "px";
      elBr.style.width = w.branch + "px";
    }
    if (elRt) {
      elRt.style.flex = "0 0 " + w.right + "px";
      elRt.style.width = w.right + "px";
    }
    if (elRag) {
      elRag.style.flex = "0 0 " + w.rag + "px";
      elRag.style.width = w.rag + "px";
    }
  }

  function bindGutter(gutter, which) {
    if (!gutter) return;
    gutter.addEventListener("mousedown", function (downEv) {
      downEv.preventDefault();
      var w = load();
      var startX = downEv.clientX;
      var start = { wf: w.wf, branch: w.branch, right: w.right, rag: w.rag };
      gutter.classList.add("is-dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";

      function onMove(ev) {
        var dx = ev.clientX - startX;
        if (which === 0) {
          w.rag = clamp(start.rag + dx, MIN.rag, MAX.rag);
        } else if (which === 1) {
          w.wf = clamp(start.wf + dx, MIN.wf, MAX.wf);
        } else if (which === 2) {
          w.branch = clamp(start.branch + dx, MIN.branch, MAX.branch);
        } else if (which === 3) {
          w.right = clamp(start.right - dx, MIN.right, MAX.right);
        }
        applyWidths(w);
      }

      function onUp() {
        document.removeEventListener("mousemove", onMove, true);
        document.removeEventListener("mouseup", onUp, true);
        gutter.classList.remove("is-dragging");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        save(w);
      }

      document.addEventListener("mousemove", onMove, true);
      document.addEventListener("mouseup", onUp, true);
    });
  }

  function init() {
    var w = load();
    applyWidths(w);
    bindGutter(document.getElementById("gutter-right-rag"), 0);
    bindGutter(document.getElementById("gutter-wf-branch"), 1);
    bindGutter(document.getElementById("gutter-branch-main"), 2);
    bindGutter(document.getElementById("gutter-main-right"), 3);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
