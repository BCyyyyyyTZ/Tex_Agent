/**
 * 顶会投稿日历：顶栏按钮打开科技感浮层，数据来自 /api/conferences/deadlines
 */
(function () {
  "use strict";

  var LS_FIELD = "texagent.conferences.field";
  var overlay = null;
  var listEl = null;
  var statusEl = null;
  var filtersEl = null;
  var activeField = "all";
  var fieldColors = {};
  var countdownTimer = null;

  function apiBase() {
    try {
      return new URL("/api/", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/";
    }
  }

  function loadSavedField() {
    try {
      return localStorage.getItem(LS_FIELD) || "all";
    } catch (_e) {
      return "all";
    }
  }

  function saveField(id) {
    try {
      localStorage.setItem(LS_FIELD, id);
    } catch (_e) {
      /* ignore */
    }
  }

  function fieldLabel(id, fields) {
    for (var i = 0; i < fields.length; i++) {
      if (fields[i].id === id) return fields[i].label;
    }
    return id;
  }

  function fieldColor(id, fields) {
    for (var i = 0; i < fields.length; i++) {
      if (fields[i].id === id) return fields[i].color || "#22d3ee";
    }
    return "#22d3ee";
  }

  function urgencyClass(u) {
    if (u === "critical") return "conf-cal-card--critical";
    if (u === "soon") return "conf-cal-card--soon";
    return "";
  }

  function formatDeadlineType(t) {
    if (t === "abstract") return "摘要";
    if (t === "full") return "全文";
    return "";
  }

  function deadlineAoETime(deadline) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(deadline || ""));
    if (!m) return null;
    var y = Number(m[1]);
    var mon = Number(m[2]) - 1;
    var d = Number(m[3]);
    // AoE = UTC-12；截止日 23:59:59 AoE 对应 UTC 次日 11:59:59。
    return Date.UTC(y, mon, d, 35, 59, 59);
  }

  function splitRemaining(ms) {
    var total = Math.max(0, Math.floor(ms / 1000));
    var days = Math.floor(total / 86400);
    total -= days * 86400;
    var hours = Math.floor(total / 3600);
    total -= hours * 3600;
    var minutes = Math.floor(total / 60);
    var seconds = total - minutes * 60;
    return { days: days, hours: hours, minutes: minutes, seconds: seconds };
  }

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function renderCountdownValue(el, targetTs) {
    if (!targetTs) {
      el.innerHTML = '<span class="conf-cal-time-expired">—</span>';
      return;
    }
    var remaining = targetTs - Date.now();
    if (remaining <= 0) {
      el.innerHTML = '<span class="conf-cal-time-expired">已截止</span>';
      return;
    }
    var p = splitRemaining(remaining);
    el.innerHTML =
      '<span class="conf-cal-time-part"><span class="conf-cal-time-num">' +
      p.days +
      '</span><span class="conf-cal-time-unit">天</span></span>' +
      '<span class="conf-cal-time-part"><span class="conf-cal-time-num">' +
      pad2(p.hours) +
      '</span><span class="conf-cal-time-unit">时</span></span>' +
      '<span class="conf-cal-time-part"><span class="conf-cal-time-num">' +
      pad2(p.minutes) +
      '</span><span class="conf-cal-time-unit">分</span></span>' +
      '<span class="conf-cal-time-part"><span class="conf-cal-time-num">' +
      pad2(p.seconds) +
      '</span><span class="conf-cal-time-unit">秒</span></span>';
  }

  function refreshCountdowns() {
    var nodes = document.querySelectorAll(".conf-cal-live-countdown");
    for (var i = 0; i < nodes.length; i++) {
      var ts = Number(nodes[i].getAttribute("data-deadline-ts") || "0");
      renderCountdownValue(nodes[i], ts);
    }
  }

  function ensureCountdownTimer() {
    if (countdownTimer) return;
    countdownTimer = window.setInterval(refreshCountdowns, 1000);
  }

  function renderFilters(fields) {
    if (!filtersEl) return;
    filtersEl.innerHTML = "";
    fields.forEach(function (f) {
      if (!f || !f.id) return;
      fieldColors[f.id] = f.color || "#22d3ee";
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "conf-cal-chip" + (activeField === f.id ? " is-active" : "");
      btn.textContent = f.label || f.id;
      btn.setAttribute("data-field", f.id);
      if (activeField === f.id && f.color) {
        btn.style.background = f.color;
        btn.style.color = "#0f172a";
        btn.style.boxShadow = "0 0 14px " + f.color;
      }
      btn.addEventListener("click", function () {
        activeField = f.id;
        saveField(activeField);
        renderFilters(fields);
        fetchAndRender();
      });
      filtersEl.appendChild(btn);
    });
  }

  function renderList(data) {
    if (!listEl) return;
    var items = data.deadlines || [];
    if (!items.length) {
      listEl.innerHTML =
        '<p class="conf-cal-empty">该领域暂无未来一年内的投稿截止项<br>可切换「全部」或其它方向查看</p>';
      return;
    }
    var ul = document.createElement("ul");
    ul.className = "conf-cal-list";
    items.forEach(function (it) {
      var li = document.createElement("li");
      var card = document.createElement("article");
      card.className = "conf-cal-card " + urgencyClass(it.urgency);

      var targetTs = deadlineAoETime(it.primary_deadline);
      var countdownLabel =
        it.days_left !== null && it.days_left !== undefined && it.days_left < 0
          ? "已过期"
          : "AoE 倒计时";

      var countdown = document.createElement("div");
      countdown.className = "conf-cal-countdown";
      countdown.innerHTML =
        '<span class="conf-cal-live-countdown" data-deadline-ts="' +
        (targetTs || 0) +
        '"></span><span class="conf-cal-days-label">' +
        countdownLabel +
        "</span>";

      var main = document.createElement("div");
      var h = document.createElement("h3");
      h.className = "conf-cal-name";
      h.textContent = it.name || it.id;
      var meta = document.createElement("p");
      meta.className = "conf-cal-meta";
      var parts = [];
      if (it.primary_deadline) {
        parts.push(
          formatDeadlineType(it.primary_type) +
            " " +
            it.primary_deadline +
            " (AoE)"
        );
      }
      if (it.abstract_deadline && it.abstract_deadline !== it.primary_deadline) {
        parts.push("摘要 " + it.abstract_deadline);
      }
      if (it.full_deadline && it.full_deadline !== it.primary_deadline) {
        parts.push("全文 " + it.full_deadline);
      }
      if (it.conference_start) parts.push("会议 " + it.conference_start);
      if (it.venue) parts.push(it.venue);
      meta.textContent = parts.join(" · ");
      main.appendChild(h);
      main.appendChild(meta);

      if (it.fields && it.fields.length) {
        var tags = document.createElement("div");
        tags.className = "conf-cal-tags";
        it.fields.forEach(function (fid) {
          var span = document.createElement("span");
          span.className = "conf-cal-tag";
          span.textContent = fieldLabel(fid, data.fields || []);
          span.style.borderColor = fieldColor(fid, data.fields || []);
          span.style.color = fieldColor(fid, data.fields || []);
          tags.appendChild(span);
        });
        main.appendChild(tags);
      }
      if (it.note) {
        var note = document.createElement("p");
        note.className = "conf-cal-meta";
        note.style.marginTop = "4px";
        note.style.color = "#64748b";
        note.textContent = it.note;
        main.appendChild(note);
      }

      var aside = document.createElement("div");
      if (it.url) {
        var a = document.createElement("a");
        a.className = "conf-cal-link";
        a.href = it.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = "官网 →";
        aside.appendChild(a);
      }

      card.appendChild(countdown);
      card.appendChild(main);
      card.appendChild(aside);
      li.appendChild(card);
      ul.appendChild(li);
    });
    listEl.innerHTML = "";
    listEl.appendChild(ul);
    refreshCountdowns();
    ensureCountdownTimer();
  }

  function fetchAndRender() {
    if (statusEl) statusEl.textContent = "SYNC // loading…";
    var q = activeField && activeField !== "all" ? "?fields=" + encodeURIComponent(activeField) : "";
    fetch(apiBase() + "conferences/deadlines" + q)
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        renderFilters(data.fields || []);
        renderList(data);
        if (statusEl) {
          statusEl.textContent =
            "STATIC DATA // " +
            (data.count || 0) +
            " entries · today " +
            (data.today || "") +
            " · " +
            ((data.meta && data.meta.note) || "");
        }
      })
      .catch(function (err) {
        if (listEl) {
          listEl.innerHTML =
            '<p class="conf-cal-empty">加载失败: ' +
            String(err.message || err) +
            "</p>";
        }
        if (statusEl) statusEl.textContent = "ERROR // fetch failed";
      });
  }

  function openModal() {
    if (!overlay) return;
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    fetchAndRender();
  }

  function closeModal() {
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function bindOpen(el) {
    if (el) el.addEventListener("click", openModal);
  }

  function shouldAutoOpenFromUrl() {
    try {
      var q = new URLSearchParams(window.location.search || "");
      if (q.get("open") === "calendar") return true;
      if (window.location.hash === "#calendar") return true;
    } catch (_e) {
      /* empty */
    }
    return false;
  }

  function buildDom() {
    overlay = document.getElementById("conf-cal-overlay");
    listEl = document.getElementById("conf-cal-list");
    statusEl = document.getElementById("conf-cal-status");
    filtersEl = document.getElementById("conf-cal-filters");

    var openers = document.querySelectorAll("[data-conf-cal-open]");
    for (var i = 0; i < openers.length; i++) {
      bindOpen(openers[i]);
    }

    var closeBtn = document.getElementById("conf-cal-close");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);

    if (overlay) {
      overlay.addEventListener("click", function (ev) {
        if (ev.target === overlay) closeModal();
      });
    }

    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && overlay && overlay.classList.contains("is-open")) {
        closeModal();
      }
    });
  }

  function init() {
    activeField = loadSavedField();
    buildDom();
    if (shouldAutoOpenFromUrl()) {
      openModal();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
