/**
 * 左侧工作流组装：拉取/保存 /api/workflow/draft，节点与边维护，小图预览
 */
(function () {
  "use strict";

  var API = (function () {
    try {
      return new URL("/api/", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/";
    }
  })();

  var state = { nodes: [], edges: [] };
  var nodeIdSeq = 1;

  function el(tag, attrs) {
    var t = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "textContent") t.textContent = attrs[k] || "";
        else if (k === "className") t.className = attrs[k];
        else t.setAttribute(k, attrs[k]);
      });
    }
    return t;
  }

  function newAgentNode(idHint) {
    var id = (idHint && String(idHint).trim()) || "step_" + nodeIdSeq++;
    if (!/^[a-zA-Z0-9_-]+$/.test(id)) {
      id = "step_" + nodeIdSeq++;
    }
    return {
      node_id: id,
      node_type: "agent",
      agent_name: "SimpleAgent",
      config: {
        system_prompt: "请说明本步骤的职责与输出要求。",
        subtask: "完成本步任务。",
        depends_on: [],
        temperature: 0.5,
      },
    };
  }

  function syncWorkflowSelect() {
    var sel = document.getElementById("workflow-select");
    if (!sel) return;
    var cur = sel.value;
    fetch(API + "workflow/registry", { method: "GET" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        var wfs = (d && d.workflows) || [];
        sel.innerHTML = "";
        sel.appendChild(
          el("option", { value: "default", textContent: "default（注册表）" })
        );
        wfs.forEach(function (n) {
          if (n === "default") return;
          sel.appendChild(el("option", { value: n, textContent: n }));
        });
        sel.appendChild(
          el("option", { value: "__web__", textContent: "自定义（左侧编排）" })
        );
        if (wfs.indexOf(cur) >= 0 || cur === "__web__" || cur === "default") sel.value = cur;
        else sel.value = "default";
      })
      .catch(function () {
        /* 保留 HTML 内建 option */
      });
  }

  function layoutWfGraph(nodes, edges) {
    var W = 360;
    var nodeW = 80;
    var nodeH = 28;
    var rowH = 64;
    var padT = 16;
    var byId = {};
    var i, n, d, k, x, y, di, j, maxD, levels, pos, H;
    for (i = 0; i < nodes.length; i++) {
      byId[nodes[i].node_id] = nodes[i];
    }
    var memo = {};
    function depthOf(id) {
      if (memo[id] != null) return memo[id];
      if (!byId[id]) {
        memo[id] = 0;
        return 0;
      }
      var parents = [];
      for (k = 0; k < edges.length; k++) {
        if (edges[k].to_node === id) parents.push(edges[k].from_node);
      }
      if (parents.length === 0) {
        memo[id] = 0;
        return 0;
      }
      var best = 0;
      for (k = 0; k < parents.length; k++) {
        var pd = depthOf(parents[k]);
        if (pd + 1 > best) best = pd + 1;
      }
      if (best > 40) best = 40;
      memo[id] = best;
      return best;
    }
    for (i = 0; i < nodes.length; i++) {
      depthOf(nodes[i].node_id);
    }
    maxD = 0;
    for (i = 0; i < nodes.length; i++) {
      d = memo[nodes[i].node_id] || 0;
      if (d > maxD) maxD = d;
    }
    levels = [];
    for (d = 0; d <= maxD; d++) levels.push([]);
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      d = memo[n.node_id] || 0;
      levels[d].push(n);
    }
    for (d = 0; d < levels.length; d++) {
      levels[d].sort(function (a, b) {
        return a.node_id.localeCompare(b.node_id, "en");
      });
    }
    pos = {};
    for (di = 0; di < levels.length; di++) {
      var row = levels[di];
      var nCount = row.length;
      var totalW = nCount * nodeW + Math.max(0, nCount - 1) * 8;
      var startX = (W - totalW) / 2;
      if (startX < 6) startX = 6;
      y = padT + di * rowH;
      for (j = 0; j < row.length; j++) {
        n = row[j];
        x = startX + j * (nodeW + 8);
        pos[n.node_id] = { x: x, y: y, w: nodeW, h: nodeH, n: n };
      }
    }
    H = padT * 2 + (levels.length > 0 ? (levels.length - 1) * rowH : 0) + nodeH;
    return { W: W, H: H, pos: pos, edges: edges, byId: byId, memo: memo };
  }

  function renderWfPreview(mount, nodes, edges) {
    var NS = "http://www.w3.org/2000/svg";
    var i, j, e, a, b, L, svg, gE, gN, t1, t2, g, w, p;
    if (!nodes || nodes.length === 0) {
      mount.innerHTML = "<p class=\"wf-preview-empty\">尚无节点</p>";
      return;
    }
    L = layoutWfGraph(JSON.parse(JSON.stringify(nodes)), JSON.parse(JSON.stringify(edges)));
    svg = document.createElementNS(NS, "svg");
    /* 图示最小高度与 viewBox 一致，避免缩略图「看起来没变大」 */
    var minBoxH = Math.max(L.H, 300);
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", String(minBoxH));
    svg.setAttribute("viewBox", "0 0 " + L.W + " " + minBoxH);
    svg.setAttribute("preserveAspectRatio", "xMidYMin meet");
    gE = document.createElementNS(NS, "g");
    gE.setAttribute("class", "wf-edge-group");
    gN = document.createElementNS(NS, "g");
    gN.setAttribute("class", "wf-node-group");
    for (i = 0; i < L.edges.length; i++) {
      e = L.edges[i];
      a = L.pos[e.from_node];
      b = L.pos[e.to_node];
      if (!a || !b) continue;
      t1 = document.createElementNS(NS, "line");
      t1.setAttribute("x1", a.x + a.w / 2);
      t1.setAttribute("y1", a.y + a.h);
      t1.setAttribute("x2", b.x + b.w / 2);
      t1.setAttribute("y2", b.y);
      t1.setAttribute("class", "wf-edge");
      gE.appendChild(t1);
    }
    for (p in L.pos) {
      w = L.pos[p];
      g = document.createElementNS(NS, "g");
      g.setAttribute("transform", "translate(" + w.x + "," + w.y + ")");
      t1 = document.createElementNS(NS, "rect");
      t1.setAttribute("width", w.w);
      t1.setAttribute("height", w.h);
      t1.setAttribute("rx", 4);
      t1.setAttribute("class", "wf-node-rect");
      t2 = document.createElementNS(NS, "text");
      t2.setAttribute("x", w.w / 2);
      t2.setAttribute("y", w.h / 2 + 3);
      t2.setAttribute("text-anchor", "middle");
      t2.setAttribute("class", "wf-node-txt");
      t2.textContent = w.n.node_id.length > 8 ? w.n.node_id.slice(0, 7) + "…" : w.n.node_id;
      g.appendChild(t1);
      g.appendChild(t2);
      gN.appendChild(g);
    }
    svg.appendChild(gE);
    svg.appendChild(gN);
    mount.innerHTML = "";
    mount.appendChild(svg);
  }

  function render() {
    var list = document.getElementById("wf-nodes");
    var elist = document.getElementById("wf-edges");
    var prev = document.getElementById("wf-preview");
    if (!list || !elist) return;
    list.innerHTML = "";
    state.nodes.forEach(function (node) {
      var box = el("div", { className: "wf-node-row" });
      var h = el("div", { className: "wf-node-row-h" });
      h.appendChild(
        el("label", { className: "wf-inline", textContent: "ID" })
      );
      var idInp = el("input", { type: "text", className: "branch-input wf-node-id" });
      idInp.value = node.node_id;
      idInp.setAttribute("data-oid", node.node_id);
      idInp.addEventListener("change", function () {
        var ov = idInp.getAttribute("data-oid");
        var nv = (idInp.value || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
        if (!nv) {
          idInp.value = ov;
          return;
        }
        node.node_id = nv;
        state.edges.forEach(function (e) {
          if (e.from_node === ov) e.from_node = nv;
          if (e.to_node === ov) e.to_node = nv;
        });
        idInp.setAttribute("data-oid", nv);
        render();
      });
      h.appendChild(idInp);
      var rm = el("button", { type: "button", className: "btn-tiny" });
      rm.textContent = "删节点";
      rm.addEventListener("click", function () {
        var oid = node.node_id;
        state.nodes = state.nodes.filter(function (x) {
          return x.node_id !== oid;
        });
        state.edges = state.edges.filter(function (e) {
          return e.from_node !== oid && e.to_node !== oid;
        });
        render();
      });
      h.appendChild(rm);
      box.appendChild(h);
      var ta = el("textarea", { className: "wf-ta" });
      ta.setAttribute("rows", "2");
      ta.placeholder = "system_prompt：本步职责";
      ta.value = (node.config && node.config.system_prompt) || "";
      ta.addEventListener("change", function () {
        if (!node.config) node.config = {};
        node.config.system_prompt = ta.value;
      });
      box.appendChild(ta);
      list.appendChild(box);
    });

    elist.innerHTML = "";
    state.edges.forEach(function (edge) {
      var row = el("div", { className: "wf-edge-row" });
      row.textContent = edge.from_node + " → " + edge.to_node;
      var btn = el("button", { type: "button", className: "btn-tiny" });
      btn.textContent = "删";
      btn.addEventListener("click", function () {
        state.edges = state.edges.filter(function (e) {
          return !(e.from_node === edge.from_node && e.to_node === edge.to_node);
        });
        render();
      });
      row.appendChild(btn);
      elist.appendChild(row);
    });
    if (prev) {
      var nodes2 = state.nodes.map(function (n) {
        return { node_id: n.node_id, config: n.config };
      });
      var edges2 = state.edges.map(function (e) {
        return { from_node: e.from_node, to_node: e.to_node };
      });
      renderWfPreview(prev, nodes2, edges2);
    }
    initEdgeForm();
  }

  function initEdgeForm() {
    var fromS = document.getElementById("wf-edge-from");
    var toS = document.getElementById("wf-edge-to");
    if (!fromS || !toS) return;
    fromS.innerHTML = "";
    toS.innerHTML = "";
    state.nodes.forEach(function (n) {
      fromS.appendChild(el("option", { value: n.node_id, textContent: n.node_id }));
      toS.appendChild(el("option", { value: n.node_id, textContent: n.node_id }));
    });
  }

  function init() {
    var list = document.getElementById("wf-nodes");
    if (!list) return;
    var st = document.getElementById("wf-status");
    var formEdge = document.getElementById("wf-add-edge");
    var formSave = document.getElementById("wf-form-save");
    var btnAdd = document.getElementById("wf-add-node");

    function setStatus(m, isErr) {
      if (!st) return;
      st.textContent = m || "";
      st.className = "wf-status" + (isErr ? " wf-status--err" : "");
    }

    fetch(API + "workflow/draft", { method: "GET" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        state.nodes = (d.nodes || []).map(function (x) {
          return JSON.parse(JSON.stringify(x));
        });
        state.edges = (d.edges || []).map(function (x) {
          return { from_node: x.from_node, to_node: x.to_node, condition: null };
        });
        render();
        initEdgeForm();
        setStatus("已从服务器加载草稿", false);
      })
      .catch(function (e) {
        state.nodes = [newAgentNode("design")];
        state.nodes.push(newAgentNode("deliver"));
        state.nodes[0].config.system_prompt = "设计/理解任务。";
        state.nodes[1].config.system_prompt = "交付最终答案。";
        state.edges = [
          { from_node: "design", to_node: "deliver", condition: null },
        ];
        render();
        initEdgeForm();
        setStatus("加载失败，已用本地模板", true);
      });

    if (btnAdd) {
      btnAdd.addEventListener("click", function () {
        state.nodes.push(newAgentNode());
        render();
        initEdgeForm();
      });
    }

    if (formEdge) {
      formEdge.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var fromS = document.getElementById("wf-edge-from");
        var toS = document.getElementById("wf-edge-to");
        var a = (fromS && fromS.value) || "";
        var b = (toS && toS.value) || "";
        if (a && b && a !== b) {
          var dupe = state.edges.some(function (e) {
            return e.from_node === a && e.to_node === b;
          });
          if (!dupe) {
            state.edges.push({ from_node: a, to_node: b, condition: null });
            render();
            initEdgeForm();
          } else {
            setStatus("该边已存在", true);
          }
        }
      });
    }

    if (formSave) {
      formSave.addEventListener("submit", function (ev) {
        ev.preventDefault();
        setStatus("保存中…", false);
        fetch(API + "workflow/draft", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nodes: state.nodes, edges: state.edges }),
        })
          .then(function (r) {
            if (!r.ok) {
              return r.json().then(function (d) {
                var det = d.detail;
                if (typeof det === "string") throw new Error(det);
                throw new Error(r.statusText);
              });
            }
            return r.json();
          })
          .then(function () {
            setStatus("已保存。若跑「自定义」任务，请在上方选择工作流为「左侧编排」", false);
          })
          .catch(function (e) {
            setStatus((e && e.message) || String(e), true);
          });
      });
    }

    syncWorkflowSelect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
