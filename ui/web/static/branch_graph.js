/**
 * 对话分支树：根据 /api/branches 绘制父→子关系，可点击切换、从节点派生新分支
 */
(function () {
  "use strict";

  var API_BASE = (function () {
    try {
      return new URL("/api/", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/";
    }
  })();

  var NS = "http://www.w3.org/2000/svg";

  function el(tag, attrs, children) {
    var t = document.createElementNS(NS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "textContent" || k === "text") {
          t.textContent = attrs[k] || "";
        } else {
          t.setAttribute(k, String(attrs[k]));
        }
      });
    }
    (children || []).forEach(function (c) {
      if (c) t.appendChild(c);
    });
    return t;
  }

  function buildLevels(nodes) {
    var byId = {};
    var i, n, d, p, maxD, levels, r, row, di, nobj;
    for (i = 0; i < nodes.length; i++) {
      nobj = nodes[i];
      byId[nobj.id] = nobj;
    }
    var memo = {};
    function depthOf(id) {
      if (memo[id] != null) return memo[id];
      n = byId[id];
      if (!n) {
        memo[id] = 0;
        return 0;
      }
      p = n.parent;
      if (!p || !byId[p]) {
        memo[id] = 0;
        return 0;
      }
      memo[id] = 1 + depthOf(p);
      return memo[id];
    }
    for (i = 0; i < nodes.length; i++) {
      depthOf(nodes[i].id);
    }
    maxD = 0;
    for (i = 0; i < nodes.length; i++) {
      d = memo[nodes[i].id] || 0;
      if (d > maxD) maxD = d;
    }
    levels = [];
    for (d = 0; d <= maxD; d++) levels.push([]);
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      d = memo[n.id] || 0;
      levels[d].push(n);
    }
    for (d = 0; d < levels.length; d++) {
      levels[d].sort(function (a, b) {
        return a.id.localeCompare(b.id, "en");
      });
    }
    return { levels: levels, memo: memo, maxD: maxD };
  }

  function layoutTree(nodes) {
    var W = 640;
    var nodeW = 108;
    var nodeH = 30;
    var rowH = 72;
    var padT = 16;
    var padL = 12;
    var bl = buildLevels(nodes);
    var pos = {};
    if (!nodes || nodes.length === 0) {
      return { W: 320, H: 80, pos: pos, nodeW: nodeW, nodeH: nodeH, edges: [] };
    }
    var levels = bl.levels;
    var di, row, j, n, nCount, totalW, gap, startX, x, y;
    for (di = 0; di < levels.length; di++) {
      row = levels[di];
      nCount = row.length;
      totalW = nCount * nodeW + Math.max(0, nCount - 1) * 14;
      startX = (W - totalW) / 2;
      if (startX < padL) startX = padL;
      y = padT + di * rowH;
      for (j = 0; j < row.length; j++) {
        n = row[j];
        x = startX + j * (nodeW + 14);
        pos[n.id] = { x: x, y: y, w: nodeW, h: nodeH, n: n };
      }
    }
    var H = padT * 2 + (levels.length > 0 ? (levels.length - 1) * rowH : 0) + nodeH + 8;
    var edges = [];
    var k, p, nn;
    for (k = 0; k < nodes.length; k++) {
      nn = nodes[k];
      p = nn.parent;
      if (p && pos[nn.id] && pos[p]) {
        edges.push({ from: p, to: nn.id });
      }
    }
    return { W: W, H: H, pos: pos, nodeW: nodeW, nodeH: nodeH, edges: edges };
  }

  function renderSvg(mount, tree, onSwitch) {
    var data = tree && tree.nodes ? tree.nodes : [];
    var current = (tree && tree.current) || "main";
    var L = layoutTree(data);
    var svg = el("svg", {
      width: "100%",
      height: String(Math.max(L.H, 220)),
      viewBox: "0 0 " + L.W + " " + Math.max(L.H, 220),
    });
    var gEdges = el("g", { class: "branch-edges" });
    var gNodes = el("g", { class: "branch-nodes" });
    var i, e, a, b, x1, y1, x2, y2;
    for (i = 0; i < L.edges.length; i++) {
      e = L.edges[i];
      a = L.pos[e.from];
      b = L.pos[e.to];
      if (!a || !b) continue;
      x1 = a.x + a.w / 2;
      y1 = a.y + a.h;
      x2 = b.x + b.w / 2;
      y2 = b.y;
      gEdges.appendChild(
        el("line", {
          x1: x1,
          y1: y1,
          x2: x2,
          y2: y2,
          class: "branch-edge",
        })
      );
    }
    i = 0;
    for (i = 0; i < data.length; i++) {
      (function (node) {
        var p = L.pos[node.id];
        if (!p) return;
        var g = el("g", { class: "branch-node", "data-bid": node.id, transform: "translate(" + p.x + "," + p.y + ")" });
        if (node.id === current) g.setAttribute("class", "branch-node branch-node--current");
        g.appendChild(
          el("rect", {
            width: p.w,
            height: p.h,
            rx: 6,
            class: "branch-node-rect",
          })
        );
        g.appendChild(
          el("text", {
            x: p.w / 2,
            y: p.h / 2 + 4,
            "text-anchor": "middle",
            class: "branch-node-label",
            textContent: node.id,
          })
        );
        g.appendChild(
          el("title", {
            textContent: node.id + (node.messages != null ? " · 对话" + node.messages + "条" : ""),
          })
        );
        g.style.cursor = "pointer";
        g.addEventListener("click", function (ev) {
          ev.stopPropagation();
          if (onSwitch) onSwitch(node.id);
        });
        gNodes.appendChild(g);
      })(data[i]);
    }
    svg.appendChild(gEdges);
    svg.appendChild(gNodes);
    mount.innerHTML = "";
    mount.appendChild(svg);
  }

  function setStatus(el, text, isError) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "branch-panel-status" + (isError ? " branch-panel-status--err" : "");
  }

  function fillFromSelect(select, nodes) {
    if (!select) return;
    var cur = select.value;
    select.innerHTML = "";
    var i, n, opt;
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      opt = document.createElement("option");
      opt.value = n.id;
      opt.textContent = n.id;
      select.appendChild(opt);
    }
    if (cur && [].some.call(select.options, function (o) { return o.value === cur; })) {
      select.value = cur;
    } else {
      var found = (nodes[0] && nodes[0].id) || "main";
      select.value = found;
    }
  }

  function init() {
    var mount = document.getElementById("branch-graph");
    var currentLbl = document.getElementById("branch-current-lbl");
    var form = document.getElementById("branch-new-form");
    var nameIn = document.getElementById("branch-new-name");
    var fromSel = document.getElementById("branch-new-from");
    var status = document.getElementById("branch-panel-status");
    if (!mount) return;

    var lastTree = { current: "main", nodes: [] };
    var historyLoadSeq = 0;
    window.texAgentBranchHistorySeq = 0;

    function syncLabel() {
      if (currentLbl) currentLbl.textContent = "当前分支: " + (lastTree.current || "main");
    }

    function prepareUiForBranchChange(fromBranch, toBranch) {
      if (typeof window.texAgentPrepareBranchSwitch === "function") {
        window.texAgentPrepareBranchSwitch(fromBranch, toBranch);
      }
    }

    function setActiveBranchUi(bid) {
      if (typeof window.texAgentSetActiveBranch === "function") {
        window.texAgentSetActiveBranch(bid || "main");
      }
    }

    function reloadChatForBranch(bid) {
      setActiveBranchUi(bid);
      var seq = ++historyLoadSeq;
      window.texAgentBranchHistorySeq = seq;
      var q = encodeURIComponent(bid || "main");
      fetch(API_BASE + "branches/history?branch=" + q, { method: "GET" })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || r.statusText); });
          return r.json();
        })
        .then(function (j) {
          if (seq !== historyLoadSeq) return;
          if (typeof window.texAgentReplaceChatFromHistory === "function") {
            window.texAgentReplaceChatFromHistory(j.messages || [], seq);
          }
        })
        .catch(function (_e) {
          if (seq !== historyLoadSeq) return;
          if (typeof window.texAgentReplaceChatFromHistory === "function") {
            window.texAgentReplaceChatFromHistory([], seq);
          }
        });
    }

    function doSwitch(bid) {
      if (bid === lastTree.current) {
        setStatus(status, "已在 " + bid, false);
        return;
      }
      setStatus(status, "切换中…", false);
      var fromBranch = lastTree.current || "main";
      prepareUiForBranchChange(fromBranch, bid);
      fetch(API_BASE + "branches/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: bid }),
      })
        .then(function (r) {
          if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || r.statusText); });
          return r.json();
        })
        .then(function (j) {
          lastTree = j;
          fillFromSelect(fromSel, j.nodes || []);
          renderSvg(mount, j, doSwitch);
          syncLabel();
          setStatus(status, "已切到 " + (j.current || bid), false);
          reloadChatForBranch(j.current || bid);
        })
        .catch(function (e) {
          setStatus(status, (e && e.message) || String(e), true);
        });
    }

    function load() {
      setStatus(status, "加载中…", false);
      fetch(API_BASE + "branches", { method: "GET" })
        .then(function (r) {
          if (!r.ok) throw new Error(r.statusText);
          return r.json();
        })
        .then(function (j) {
          lastTree = j;
          fillFromSelect(fromSel, j.nodes || []);
          renderSvg(mount, j, doSwitch);
          syncLabel();
          setStatus(status, "点击节点切换；下方可从所选父节点拉出新分支", false);
          reloadChatForBranch(j.current || "main");
        })
        .catch(function (e) {
          setStatus(status, "无法加载分支: " + ((e && e.message) || String(e)), true);
        });
    }

    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var nm = (nameIn && nameIn.value) ? nameIn.value.trim() : "";
        var from = (fromSel && fromSel.value) || "main";
        if (!nm) {
          setStatus(status, "请填写新分支名", true);
          return;
        }
        setStatus(status, "创建中…", false);
        fetch(API_BASE + "branches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: nm, from_branch: from }),
        })
          .then(function (r) {
            if (r.status === 409) {
              return r.json().then(function (d) { throw new Error(d.detail || "已存在或父分支无效"); });
            }
            if (!r.ok) return r.json().then(function (d) { throw new Error((d && d.detail) || r.statusText); });
            return r.json();
          })
          .then(function (j) {
            lastTree = j;
            if (nameIn) nameIn.value = "";
            fillFromSelect(fromSel, j.nodes || []);
            renderSvg(mount, j, doSwitch);
            setStatus(status, "已创建（当前仍为 " + (j.current || "main") + "，可点击新节点切换）", false);
            syncLabel();
          })
          .catch(function (e) {
            setStatus(status, (e && e.message) || String(e), true);
          });
      });
    }

    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
