(function () {
  "use strict";

  var LS_KEY = "texagent.userSettings.v1";
  var themes = [
    {
      id: "blue",
      label: "默认蓝",
      accent: "#58a6ff",
      strong: "#094771",
      dim: "rgba(88, 166, 255, 0.26)",
      bubble: "rgba(31, 111, 235, 0.1)",
      gradient: "linear-gradient(180deg, #5cadff 0%, #8b5cf6 100%)",
    },
    {
      id: "cyan",
      label: "赛博青",
      accent: "#22d3ee",
      strong: "#0e7490",
      dim: "rgba(34, 211, 238, 0.24)",
      bubble: "rgba(34, 211, 238, 0.1)",
      gradient: "linear-gradient(180deg, #22d3ee 0%, #818cf8 100%)",
    },
    {
      id: "violet",
      label: "紫罗兰",
      accent: "#a78bfa",
      strong: "#6d28d9",
      dim: "rgba(167, 139, 250, 0.25)",
      bubble: "rgba(167, 139, 250, 0.11)",
      gradient: "linear-gradient(180deg, #a78bfa 0%, #ec4899 100%)",
    },
    {
      id: "green",
      label: "论文绿",
      accent: "#34d399",
      strong: "#047857",
      dim: "rgba(52, 211, 153, 0.22)",
      bubble: "rgba(52, 211, 153, 0.1)",
      gradient: "linear-gradient(180deg, #34d399 0%, #22d3ee 100%)",
    },
    {
      id: "amber",
      label: "暖金",
      accent: "#f59e0b",
      strong: "#92400e",
      dim: "rgba(245, 158, 11, 0.22)",
      bubble: "rgba(245, 158, 11, 0.1)",
      gradient: "linear-gradient(180deg, #f59e0b 0%, #ef4444 100%)",
    },
    {
      id: "black",
      label: "纯黑",
      accent: "#e5e7eb",
      strong: "#111111",
      dim: "rgba(255, 255, 255, 0.14)",
      bubble: "rgba(255, 255, 255, 0.06)",
      gradient: "linear-gradient(180deg, #111111 0%, #111111 100%)",
      bg: "#000000",
      elevated: "#050505",
      input: "#000000",
      border: "#2a2a2a",
      text: "#f5f5f5",
      muted: "#a3a3a3",
      assistant: "#080808",
    },
    {
      id: "white",
      label: "纯白",
      accent: "#111827",
      strong: "#111827",
      dim: "rgba(17, 24, 39, 0.12)",
      bubble: "rgba(17, 24, 39, 0.05)",
      gradient: "linear-gradient(180deg, #ffffff 0%, #ffffff 100%)",
      bg: "#f8fafc",
      elevated: "#ffffff",
      input: "#ffffff",
      border: "#d0d7de",
      text: "#111827",
      muted: "#1f2937",
      assistant: "#f3f4f6",
    },
  ];
  var patterns = [
    { id: "grid", label: "量子网络", hint: "Q-NET" },
    { id: "circuit", label: "电路脉冲", hint: "CIRCUIT" },
    { id: "orbit", label: "轨道星图", hint: "ORBIT" },
    { id: "none", label: "极简无纹", hint: "MIN" },
  ];

  var defaults = {
    theme: "blue",
    pattern: "grid",
    profile: {
      displayName: "",
      affiliation: "",
      researchFields: "",
      homepage: "",
      note: "",
    },
  };

  function cloneDefaults() {
    return JSON.parse(JSON.stringify(defaults));
  }

  function getTheme(id) {
    for (var i = 0; i < themes.length; i++) {
      if (themes[i].id === id) return themes[i];
    }
    return themes[0];
  }

  function loadSettings() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return cloneDefaults();
      var parsed = JSON.parse(raw);
      return {
        theme: parsed.theme || defaults.theme,
        pattern: parsed.pattern || defaults.pattern,
        profile: Object.assign({}, defaults.profile, parsed.profile || {}),
      };
    } catch (_e) {
      return cloneDefaults();
    }
  }

  function saveSettings(settings) {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(settings));
    } catch (_e) {
      /* ignore */
    }
  }

  function applyTheme(themeId) {
    var t = getTheme(themeId);
    var root = document.documentElement;
    root.style.setProperty("--accent", t.accent);
    root.style.setProperty("--accent-strong", t.strong);
    root.style.setProperty("--accent-dim", t.dim);
    root.style.setProperty("--user-bubble", t.bubble);
    root.style.setProperty("--accent-gradient", t.gradient);
    root.style.setProperty("--bg", t.bg || "#1e1e1e");
    root.style.setProperty("--bg-elev", t.elevated || "#252526");
    root.style.setProperty("--bg-input", t.input || "#1e1e1e");
    root.style.setProperty("--border", t.border || "#3c3c3c");
    root.style.setProperty("--text", t.text || "#e6edf3");
    root.style.setProperty("--text-muted", t.muted || "#9d9d9d");
    root.style.setProperty("--asst-bubble", t.assistant || "#2d2d2d");
    root.setAttribute("data-user-theme", t.id);
  }

  function applySettings(settings) {
    applyTheme(settings.theme || defaults.theme);
    document.documentElement.setAttribute("data-user-pattern", settings.pattern || defaults.pattern);
    window.texAgentUserSettings = settings;
  }

  function val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }

  function setVal(id, value) {
    var el = document.getElementById(id);
    if (el) el.value = value || "";
  }

  function setOpen(overlay, open) {
    if (!overlay) return;
    overlay.classList.toggle("is-open", !!open);
    overlay.setAttribute("aria-hidden", open ? "false" : "true");
    document.body.style.overflow = open ? "hidden" : "";
  }

  function buildThemeButtons(currentTheme) {
    var wrap = document.getElementById("settings-theme-list");
    if (!wrap) return;
    wrap.innerHTML = "";
    themes.forEach(function (t) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "settings-theme-btn" + (t.id === currentTheme ? " is-active" : "");
      btn.setAttribute("data-theme", t.id);
      var swatch = t.bg || t.accent;
      var swatchBorder = t.id === "white" ? "#cbd5e1" : t.accent;
      btn.innerHTML =
        '<span class="settings-theme-dot" style="background:' +
        swatch +
        '; color:' +
        swatchBorder +
        '; border-color:' +
        swatchBorder +
        '"></span><span>' +
        t.label +
        "</span>";
      btn.addEventListener("click", function () {
        var s = loadSettings();
        s.theme = t.id;
        saveSettings(s);
        applySettings(s);
        buildThemeButtons(t.id);
      });
      wrap.appendChild(btn);
    });
  }

  function buildPatternButtons(currentPattern) {
    var wrap = document.getElementById("settings-pattern-list");
    if (!wrap) return;
    wrap.innerHTML = "";
    patterns.forEach(function (p) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "settings-theme-btn settings-pattern-btn" + (p.id === currentPattern ? " is-active" : "");
      btn.setAttribute("data-pattern", p.id);
      btn.innerHTML =
        '<span class="settings-pattern-preview settings-pattern-preview--' +
        p.id +
        '"></span><span>' +
        p.label +
        '</span><span class="settings-pattern-code">' +
        p.hint +
        "</span>";
      btn.addEventListener("click", function () {
        var s = loadSettings();
        s.pattern = p.id;
        saveSettings(s);
        applySettings(s);
        buildPatternButtons(p.id);
      });
      wrap.appendChild(btn);
    });
  }

  function fillForm(settings) {
    buildThemeButtons(settings.theme || defaults.theme);
    buildPatternButtons(settings.pattern || defaults.pattern);
    setVal("settings-display-name", settings.profile.displayName);
    setVal("settings-affiliation", settings.profile.affiliation);
    setVal("settings-research-fields", settings.profile.researchFields);
    setVal("settings-homepage", settings.profile.homepage);
    setVal("settings-note", settings.profile.note);
  }

  function collectForm() {
    var current = loadSettings();
    return {
      theme: current.theme || defaults.theme,
      pattern: current.pattern || defaults.pattern,
      profile: {
        displayName: val("settings-display-name"),
        affiliation: val("settings-affiliation"),
        researchFields: val("settings-research-fields"),
        homepage: val("settings-homepage"),
        note: val("settings-note"),
      },
    };
  }

  function init() {
    var settings = loadSettings();
    applySettings(settings);

    var overlay = document.getElementById("user-settings-overlay");
    var closeBtn = document.getElementById("user-settings-close");
    var saveBtn = document.getElementById("user-settings-save");
    var resetBtn = document.getElementById("user-settings-reset");

    fillForm(settings);

    function openSettings() {
      fillForm(loadSettings());
      setOpen(overlay, true);
    }

    window.TexAgentSettings = {
      open: openSettings,
      close: function () { setOpen(overlay, false); },
      load: loadSettings,
      apply: applySettings,
    };

    document.addEventListener(
      "click",
      function (ev) {
        var trigger = ev.target && ev.target.closest ? ev.target.closest("[data-user-settings-open]") : null;
        if (!trigger) return;
        ev.preventDefault();
        ev.stopPropagation();
        openSettings();
      },
      true
    );
    if (closeBtn) closeBtn.addEventListener("click", function () { setOpen(overlay, false); });
    if (overlay) {
      overlay.addEventListener("click", function (ev) {
        if (ev.target === overlay) setOpen(overlay, false);
      });
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        var next = collectForm();
        saveSettings(next);
        applySettings(next);
        setOpen(overlay, false);
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        var next = cloneDefaults();
        saveSettings(next);
        applySettings(next);
        fillForm(next);
      });
    }
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && overlay && overlay.classList.contains("is-open")) {
        setOpen(overlay, false);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
