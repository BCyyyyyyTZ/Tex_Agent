/**
 * 侧栏显隐：顶栏切换 RAG / 工作流 / 分支 / 资料列（状态存 localStorage）。
 */
(function () {
  "use strict";

  var LS_KEY = "texagent.layout.panels";

  var PANELS = [
    { id: "rag", colId: "col-rag", gutterId: "gutter-right-rag", label: "RAG" },
    { id: "wf", colId: "col-wf", gutterId: "gutter-wf-branch", label: "工作流" },
    { id: "branch", colId: "col-branch", gutterId: "gutter-branch-main", label: "分支" },
    { id: "right", colId: "col-right", gutterId: "gutter-main-right", label: "资料" },
  ];

  var state = load();

  function defaultState() {
    return { rag: true, wf: true, branch: true, right: true };
  }

  function load() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return defaultState();
      var o = JSON.parse(raw);
      var d = defaultState();
      PANELS.forEach(function (p) {
        if (typeof o[p.id] === "boolean") d[p.id] = o[p.id];
      });
      return d;
    } catch (_e) {
      return defaultState();
    }
  }

  function save() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(state));
    } catch (_e) {
      /* ignore */
    }
  }

  function isVisible(id) {
    return state[id] !== false;
  }

  function setVisible(id, visible) {
    state[id] = !!visible;
    save();
    apply();
    syncButtons();
  }

  function toggle(id) {
    setVisible(id, !isVisible(id));
  }

  function apply() {
    PANELS.forEach(function (p) {
      var col = document.getElementById(p.colId);
      var gutter = document.getElementById(p.gutterId);
      var on = isVisible(p.id);
      if (col) col.classList.toggle("is-collapsed", !on);
      if (gutter) gutter.classList.toggle("is-collapsed", !on);
    });
    try {
      window.dispatchEvent(new CustomEvent("texagent:panels-changed"));
    } catch (_e) {
      /* ignore */
    }
  }

  function syncButtons() {
    document.querySelectorAll(".panel-toggle[data-panel]").forEach(function (btn) {
      var id = btn.getAttribute("data-panel");
      var on = isVisible(id);
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function bindTopbar() {
    var group = document.getElementById("panel-toggles");
    if (!group) return;
    group.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".panel-toggle[data-panel]");
      if (!btn) return;
      toggle(btn.getAttribute("data-panel"));
    });
  }

  function init() {
    apply();
    syncButtons();
    bindTopbar();
  }

  window.TexAgentPanels = {
    load: load,
    apply: apply,
    isVisible: isVisible,
    setVisible: setVisible,
    toggle: toggle,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
