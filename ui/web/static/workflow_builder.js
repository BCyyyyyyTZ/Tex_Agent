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
  /** 避免快速切换工作流时异步图示乱序 */
  var registryPreviewSeq = 0;

  /** 与 tools/tool_list 常见工具对齐；未知工具用 {}，可在节点列表里再改 */
  var TOOL_INPUT_DEFAULTS = {
    docling_parse: { doc_path: "doc/sample.pdf", redo: false, md_preview_chars: 500 },
    file_loading: "doc/readme.txt",
    markdown_section: {
      md_path: "doc/sample.md",
      mode: "outline",
      section_keywords: ["abstract"],
      max_chars: 4000,
    },
    docling_search: {
      json_path: "${metadata.docling_parse.metadata.tool_metadata.json_path}",
      candidates: "${metadata.formatter.result}",
      min_score: 0.2,
    },
    pdf_comment: {
      pdf_path: "doc/sample.pdf",
      annotations: [],
      output_path: "doc/annotated.pdf",
    },
    pymupdf_parse: { pdf_path: "doc/sample.pdf" },
    chapter_index: { md_path: "doc/outline.md" },
    ref_checker: { md_path: "doc/paper.md" },
    figure_ref_checker: { md_path: "doc/paper.md" },
    rag_retrieve: { query: "检索查询" },
    arxiv_search: "machine learning",
    command_running: { command: "echo ok", cwd: "." },
    user_persona_none: {},
    user_persona_get: {},
    user_persona_merge: { delta: {} },
    user_persona_set: { fields: {} },
    user_persona_clear: { clear_keys: [] },
  };

  var FALLBACK_TOOL_NAMES = [
    "docling_parse",
    "file_loading",
    "markdown_section",
    "docling_search",
    "pdf_comment",
    "arxiv_search",
    "pymupdf_parse",
    "command_running",
    "rag_retrieve",
    "ref_checker",
    "figure_ref_checker",
    "chapter_index",
    "user_persona_none",
    "user_persona_get",
    "user_persona_merge",
    "user_persona_set",
    "user_persona_clear",
  ];

  function defaultToolInputFor(toolName) {
    if (Object.prototype.hasOwnProperty.call(TOOL_INPUT_DEFAULTS, toolName)) {
      var v = TOOL_INPUT_DEFAULTS[toolName];
      if (v !== null && typeof v === "object" && !Array.isArray(v)) {
        return JSON.parse(JSON.stringify(v));
      }
      return v;
    }
    return {};
  }

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
        history_mode: "minimal"
      },
    };
  }

  function newToolNode(idHint) {
    var id = (idHint && String(idHint).trim()) || "tool_" + nodeIdSeq++;
    if (!/^[a-zA-Z0-9_-]+$/.test(id)) {
      id = "tool_" + nodeIdSeq++;
    }
    return {
      node_id: id,
      node_type: "tool",
      tool_name: "markdown_section",
      config: {
        tool_input: {
          md_path: "${metadata.some_node.metadata.tool_metadata.markdown_path}",
          mode: "outline"
        },
        depends_on: [],
        history_mode: "minimal"
      },
    };
  }

  function fillToolSelectFromNames(names) {
    var sel = document.getElementById("tool-select");
    if (!sel) return;
    sel.innerHTML = "";
    names.forEach(function (name) {
      sel.appendChild(el("option", { value: name, textContent: name }));
    });
  }

  function migrateDeliverToExecute() {
    var hasExecute = state.nodes.some(function (n) {
      return n.node_id === "execute";
    });
    state.nodes.forEach(function (n) {
      if (n.node_id === "deliver" && !hasExecute) {
        n.node_id = "execute";
        hasExecute = true;
      }
    });
    state.edges.forEach(function (e) {
      if (e.from_node === "deliver") e.from_node = "execute";
      if (e.to_node === "deliver") e.to_node = "execute";
    });
  }

  function ensureDesignExecute() {
    var hasDesign = state.nodes.some(function (n) {
      return n.node_id === "design";
    });
    var hasExecute = state.nodes.some(function (n) {
      return n.node_id === "execute";
    });
    if (!hasDesign) {
      var d = newAgentNode("design");
      d.config.system_prompt =
        "你是设计节点，把用户问题整理为清晰任务说明与可执行结构，供下一节点使用。";
      state.nodes.unshift(d);
    }
    if (!hasExecute) {
      var x = newAgentNode("execute");
      x.config.system_prompt =
        "你是执行/交付节点，基于上游设计生成完整、可执行的最终回答。";
      state.nodes.push(x);
    }
  }

  /** 从输出点拖到输入点连边：{ fromId, onMove, onUp } */
  var edgeDrag = null;
  /** 拖拽结束后浏览器可能补发 click，避免误开编辑 */
  var wfIgnoreRectClickUntil = 0;
  /** 节点矩形拖拽：{ nid, grabDx, grabDy, sx, sy, moved, onMove, onUp } */
  var nodePointerDrag = null;

  function clientToSvgPoint(svg, clientX, clientY) {
    var pt = svg.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }

  function endEdgeDrag(ev) {
    if (!edgeDrag) return;
    var fromId = edgeDrag.fromId;
    document.removeEventListener("pointermove", edgeDrag.onMove, true);
    document.removeEventListener("pointerup", edgeDrag.onUp, true);
    document.removeEventListener("pointercancel", edgeDrag.onUp, true);
    edgeDrag = null;

    var hit = document.elementFromPoint(ev.clientX, ev.clientY);
    var toId = null;
    if (hit && typeof hit.closest === "function") {
      var tin = hit.closest('[data-wf-port="in"]');
      if (tin) toId = tin.getAttribute("data-node-id") || null;
    }
    var ok =
      toId &&
      toId !== fromId &&
      !state.edges.some(function (ex) {
        return ex.from_node === fromId && ex.to_node === toId;
      });
    if (ok) {
      state.edges.push({ from_node: fromId, to_node: toId, condition: null });
    }
    wfIgnoreRectClickUntil = Date.now() + 450;
    render();
  }

  function startEdgeDrag(svg, gDrag, fromId, x0, y0, ev) {
    if (nodePointerDrag) return;
    ev.preventDefault();
    ev.stopPropagation();
    var NS = "http://www.w3.org/2000/svg";
    var line = document.createElementNS(NS, "line");
    line.setAttribute("x1", String(x0));
    line.setAttribute("y1", String(y0));
    line.setAttribute("x2", String(x0));
    line.setAttribute("y2", String(y0));
    line.setAttribute("class", "wf-edge wf-edge--drag");

    function onMove(e) {
      var p = clientToSvgPoint(svg, e.clientX, e.clientY);
      if (p) {
        line.setAttribute("x2", String(p.x));
        line.setAttribute("y2", String(p.y));
      }
    }
    function onUp(e) {
      endEdgeDrag(e);
    }

    gDrag.appendChild(line);
    edgeDrag = { fromId: fromId, onMove: onMove, onUp: onUp };
    document.addEventListener("pointermove", onMove, true);
    document.addEventListener("pointerup", onUp, true);
    document.addEventListener("pointercancel", onUp, true);
  }

  function isProtectedNode(nodeId) {
    return nodeId === "design" || nodeId === "execute";
  }

  function getWorkflowSelectValue() {
    var sel = document.getElementById("workflow-select");
    return (sel && sel.value) || "default";
  }

  function refreshWorkflowCanvas() {
    var prev = document.getElementById("wf-preview");
    if (!prev) return;
    var v = getWorkflowSelectValue();
    if (v === "__web__") {
      renderWfPreview(prev, state.nodes, state.edges, { readOnly: false });
      return;
    }
    var seq = ++registryPreviewSeq;
    var q = encodeURIComponent(v);
    fetch(API + "workflow/graph?name=" + q, { method: "GET" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) {
        if (seq !== registryPreviewSeq) return;
        var nodes = (d.nodes || []).map(function (x) {
          return JSON.parse(JSON.stringify(x));
        });
        var edges = (d.edges || []).map(function (x) {
          return {
            from_node: x.from_node || x.from,
            to_node: x.to_node || x.to,
            condition: x.condition != null ? x.condition : null,
          };
        });
        renderWfPreview(prev, nodes, edges, { readOnly: true });
      })
      .catch(function () {
        if (seq !== registryPreviewSeq) return;
        prev.innerHTML = "<p class=\"wf-preview-empty\">无法加载该工作流图示</p>";
      });
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
        refreshWorkflowCanvas();
      })
      .catch(function () {
        refreshWorkflowCanvas();
      });
  }

  /** 自动分层布局（无 ui_pos 的节点使用） */
  function layoutWfGraphAuto(nodes, edges) {
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
    return { W: W, H: H, pos: pos, edges: edges };
  }

  /** 合并节点上的 ui_pos（随草稿保存）与自动布局 */
  function layoutForPreview(nodes, edges) {
    var autoL = layoutWfGraphAuto(nodes, edges);
    var nodeW = 80;
    var nodeH = 28;
    var margin = 28;
    var pos = {};
    var i, n, id, up, id2, p, r, b;
    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      id = n.node_id;
      up = n.ui_pos;
      if (
        up &&
        typeof up.x === "number" &&
        typeof up.y === "number" &&
        !isNaN(up.x) &&
        !isNaN(up.y)
      ) {
        pos[id] = { x: +up.x, y: +up.y, w: nodeW, h: nodeH, n: n };
      } else if (autoL.pos[id]) {
        pos[id] = autoL.pos[id];
      } else {
        pos[id] = { x: margin, y: margin, w: nodeW, h: nodeH, n: n };
      }
    }
    var maxR = 360;
    var maxB = autoL.H;
    for (id2 in pos) {
      p = pos[id2];
      r = p.x + p.w + margin;
      b = p.y + p.h + margin;
      if (r > maxR) maxR = r;
      if (b > maxB) maxB = b;
    }
    return {
      W: Math.max(360, maxR),
      H: Math.max(480, Math.max(autoL.H, maxB)),
      pos: pos,
      edges: edges,
    };
  }

  function endNodePointerDrag() {
    if (!nodePointerDrag) return;
    var moved = nodePointerDrag.moved;
    var nid = nodePointerDrag.nid;
    document.removeEventListener("pointermove", nodePointerDrag.onMove, true);
    document.removeEventListener("pointerup", nodePointerDrag.onUp, true);
    document.removeEventListener("pointercancel", nodePointerDrag.onUp, true);
    nodePointerDrag = null;
    if (moved) {
      wfIgnoreRectClickUntil = Date.now() + 400;
      render();
      return;
    }
    if (nid) {
      var idx = state.nodes.findIndex(function (nd) {
        return nd.node_id === nid;
      });
      if (idx >= 0) editNode(state.nodes[idx], idx);
    }
  }

  function startNodePointerDrag(svg, w, ev) {
    if (edgeDrag || nodePointerDrag) return;
    if (ev.pointerType === "mouse" && ev.button !== 0) return;
    if (Date.now() < wfIgnoreRectClickUntil) return;
    var p0 = clientToSvgPoint(svg, ev.clientX, ev.clientY);
    if (!p0) return;
    ev.preventDefault();
    ev.stopPropagation();
    var st = {
      nid: w.n.node_id,
      grabDx: p0.x - w.x,
      grabDy: p0.y - w.y,
      sx: ev.clientX,
      sy: ev.clientY,
      moved: false,
    };
    function onMove(e) {
      if (!nodePointerDrag) return;
      if (!nodePointerDrag.moved) {
        if (
          Math.abs(e.clientX - nodePointerDrag.sx) > 4 ||
          Math.abs(e.clientY - nodePointerDrag.sy) > 4
        ) {
          nodePointerDrag.moved = true;
        }
      }
      if (!nodePointerDrag.moved) return;
      var mountEl = document.getElementById("wf-preview");
      var svgEl = mountEl && mountEl.querySelector("svg");
      if (!svgEl) return;
      var p = clientToSvgPoint(svgEl, e.clientX, e.clientY);
      if (!p) return;
      var nd = state.nodes.find(function (x) {
        return x.node_id === nodePointerDrag.nid;
      });
      if (!nd) return;
      var nx = Math.round(p.x - nodePointerDrag.grabDx);
      var ny = Math.round(p.y - nodePointerDrag.grabDy);
      nx = Math.max(4, Math.min(4000, nx));
      ny = Math.max(4, Math.min(4000, ny));
      nd.ui_pos = { x: nx, y: ny };
      render();
    }
    function onUp() {
      endNodePointerDrag();
    }
    st.onMove = onMove;
    st.onUp = onUp;
    nodePointerDrag = st;
    document.addEventListener("pointermove", onMove, true);
    document.addEventListener("pointerup", onUp, true);
    document.addEventListener("pointercancel", onUp, true);
  }

  function renderWfPreview(mount, nodes, edges, opts) {
    var NS = "http://www.w3.org/2000/svg";
    var i, j, e, a, b, L, svg, gE, gN, t1, t2, g, w, p;
    var readOnly = !!(opts && opts.readOnly);
    if (!nodes || nodes.length === 0) {
      mount.innerHTML = "<p class=\"wf-preview-empty\">尚无节点</p>";
      return;
    }
    L = layoutForPreview(nodes, edges);
    svg = document.createElementNS(NS, "svg");
    var minBoxH = Math.max(L.H, 480); // 与 .wf-preview 最小高度协调
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", String(minBoxH));
    svg.setAttribute("viewBox", "0 0 " + L.W + " " + minBoxH);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    gE = document.createElementNS(NS, "g");
    gE.setAttribute("class", "wf-edge-group");
    gN = document.createElementNS(NS, "g");
    gN.setAttribute("class", "wf-node-group");
    var gDrag = document.createElementNS(NS, "g");
    gDrag.setAttribute("class", "wf-edge-drag-layer");

    // 绘制边（底层可见线）
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

    var gEdgeUi = document.createElementNS(NS, "g");
    gEdgeUi.setAttribute("class", "wf-edge-ui-layer");

    // 绘制节点；readOnly 时仅展示，不可拖拽/连边/删除
    for (p in L.pos) {
      (function (w) {
        g = document.createElementNS(NS, "g");
        g.setAttribute("class", readOnly ? "wf-node-readonly" : "wf-node-interactive");
        g.setAttribute("transform", "translate(" + w.x + "," + w.y + ")");
        var nodeType = (w.n && w.n.node_type) || "agent";
        var nidStr = (w.n && w.n.node_id) || "?";
        g.setAttribute("data-wf-node-id", nidStr);

        t1 = document.createElementNS(NS, "rect");
        t1.setAttribute("width", w.w);
        t1.setAttribute("height", w.h);
        t1.setAttribute("rx", 6);
        var rectClass = "wf-node-rect";
        if (nodeType === "tool") rectClass += " tool-node";
        if (readOnly) rectClass += " wf-node-rect--readonly";
        t1.setAttribute("class", rectClass);
        if (!readOnly) {
          t1.addEventListener("pointerdown", function (ev) {
            startNodePointerDrag(svg, w, ev);
          });
        }

        t2 = document.createElementNS(NS, "text");
        t2.setAttribute("x", w.w / 2);
        t2.setAttribute("y", w.h / 2 + 4);
        t2.setAttribute("text-anchor", "middle");
        t2.setAttribute("class", "wf-node-txt");
        var label = nidStr.length > 11 ? nidStr.slice(0, 10) + "…" : nidStr;
        if (nodeType === "tool") label = "🛠 " + label;
        t2.textContent = label;

        var cx = w.w / 2;
        var circIn = document.createElementNS(NS, "circle");
        circIn.setAttribute("cx", String(cx));
        circIn.setAttribute("cy", "0");
        circIn.setAttribute("r", "7");
        circIn.setAttribute(
          "class",
          readOnly ? "wf-port wf-port-in wf-port--readonly" : "wf-port wf-port-in"
        );
        if (!readOnly) {
          circIn.setAttribute("data-wf-port", "in");
          circIn.setAttribute("data-node-id", nidStr);
          circIn.setAttribute("title", "输入：从他节点下方连接点拖线到此松开");
        }

        var circOut = document.createElementNS(NS, "circle");
        circOut.setAttribute("cx", String(cx));
        circOut.setAttribute("cy", String(w.h));
        circOut.setAttribute("r", "7");
        circOut.setAttribute(
          "class",
          readOnly ? "wf-port wf-port-out wf-port--readonly" : "wf-port wf-port-out"
        );
        if (!readOnly) {
          circOut.setAttribute("data-wf-port", "out");
          circOut.setAttribute("data-node-id", nidStr);
          circOut.setAttribute("title", "输出：按住拖向目标节点上方的点");
          circOut.addEventListener("pointerdown", function (ev) {
            var ax = w.x + cx;
            var ay = w.y + w.h;
            startEdgeDrag(svg, gDrag, nidStr, ax, ay, ev);
          });
        }

        g.appendChild(t1);
        g.appendChild(t2);
        g.appendChild(circIn);
        g.appendChild(circOut);

        var nid = nidStr;
        if (!readOnly && !isProtectedNode(nid)) {
          var btnRm = document.createElementNS(NS, "g");
          btnRm.setAttribute("class", "wf-node-remove");
          btnRm.setAttribute("transform", "translate(" + (w.w - 15) + ",1)");
          var rmbg = document.createElementNS(NS, "circle");
          rmbg.setAttribute("cx", "6");
          rmbg.setAttribute("cy", "6");
          rmbg.setAttribute("r", "8");
          rmbg.setAttribute("class", "wf-node-remove-bg");
          var rmtxt = document.createElementNS(NS, "text");
          rmtxt.setAttribute("x", "6");
          rmtxt.setAttribute("y", "10");
          rmtxt.setAttribute("text-anchor", "middle");
          rmtxt.setAttribute("class", "wf-node-remove-x");
          rmtxt.textContent = "×";
          btnRm.appendChild(rmbg);
          btnRm.appendChild(rmtxt);
          btnRm.setAttribute("title", "删除节点");
          btnRm.addEventListener("click", function (ev) {
            ev.stopPropagation();
            ev.preventDefault();
            if (!confirm("删除节点 " + nid + "？将清除所有相关边。")) return;
            state.nodes = state.nodes.filter(function (n) {
              return n.node_id !== nid;
            });
            state.edges = state.edges.filter(function (ed) {
              return ed.from_node !== nid && ed.to_node !== nid;
            });
            render();
          });
          g.appendChild(btnRm);
        }

        gN.appendChild(g);
      })(L.pos[p]);
    }

    // 边交互：仅可编辑模式
    if (!readOnly) for (j = 0; j < L.edges.length; j++) {
      e = L.edges[j];
      a = L.pos[e.from_node];
      b = L.pos[e.to_node];
      if (!a || !b) continue;
      (function (fx1, fy1, fx2, fy2, fromN, toN) {
        var mx = (fx1 + fx2) / 2;
        var my = (fy1 + fy2) / 2;
        var wrap = document.createElementNS(NS, "g");
        wrap.setAttribute("class", "wf-edge-wrap");
        // 仅中点附近可悬停，避免整条透明线盖住节点拦截点击
        var hit = document.createElementNS(NS, "circle");
        hit.setAttribute("cx", String(mx));
        hit.setAttribute("cy", String(my));
        hit.setAttribute("r", "24");
        hit.setAttribute("class", "wf-edge-hit");
        hit.setAttribute("title", "悬停显示删除");
        var chip = document.createElementNS(NS, "g");
        chip.setAttribute("class", "wf-edge-remove");
        chip.setAttribute("transform", "translate(" + mx + "," + my + ")");
        var ebg = document.createElementNS(NS, "circle");
        ebg.setAttribute("r", "7");
        ebg.setAttribute("class", "wf-edge-remove-bg");
        var etx = document.createElementNS(NS, "text");
        etx.setAttribute("y", "4");
        etx.setAttribute("text-anchor", "middle");
        etx.setAttribute("class", "wf-edge-remove-x");
        etx.textContent = "×";
        chip.appendChild(ebg);
        chip.appendChild(etx);
        chip.setAttribute("title", "删除此边");
        wrap.appendChild(hit);
        wrap.appendChild(chip);
        chip.addEventListener("click", function (ev) {
          ev.stopPropagation();
          ev.preventDefault();
          if (!confirm("删除边 " + fromN + " → " + toN + "？")) return;
          state.edges = state.edges.filter(function (ed) {
            return !(ed.from_node === fromN && ed.to_node === toN);
          });
          render();
        });
        gEdgeUi.appendChild(wrap);
      })(
        a.x + a.w / 2,
        a.y + a.h,
        b.x + b.w / 2,
        b.y,
        e.from_node,
        e.to_node
      );
    }

    svg.appendChild(gE);
    svg.appendChild(gN);
    svg.appendChild(gEdgeUi);
    svg.appendChild(gDrag);
    mount.innerHTML = "";
    mount.appendChild(svg);
  }

  function render() {
    if (getWorkflowSelectValue() === "__web__") {
      refreshWorkflowCanvas();
    }
  }

  function editNode(node, idx) {
    var msg = "编辑节点 " + node.node_id + " (" + (node.node_type || "agent") + ")\n\n";
    if (node.node_type === "agent") {
      var newPrompt = prompt(msg + "更新 system_prompt:", node.config && node.config.system_prompt || "");
      if (newPrompt !== null) {
        if (!node.config) node.config = {};
        node.config.system_prompt = newPrompt;
      }
    } else if (node.node_type === "tool") {
      var newTool = prompt(msg + "更新 tool_name:", node.tool_name || "");
      if (newTool !== null && newTool.trim()) {
        node.tool_name = newTool.trim();
      }
    }
    render();
  }

  function init() {
    if (!document.getElementById("wf-preview")) return;
    var st = document.getElementById("wf-status");
    var formSave = document.getElementById("wf-form-save");

    function setStatus(m, isErr) {
      if (!st) return;
      st.textContent = m || "";
      st.className = "wf-status" + (isErr ? " wf-status--err" : "");
    }

    /* 用 document 委托绑定，避免捕获阶段/遮罩导致按钮 click 不触发 */
    if (!document.documentElement.dataset.wfAddDelegated) {
      document.documentElement.dataset.wfAddDelegated = "1";
      document.addEventListener(
        "click",
        function (ev) {
          var tgt = ev.target;
          if (!tgt || typeof tgt.closest !== "function") return;
          if (tgt.closest("#add-agent-btn")) {
            ev.preventDefault();
            var idInput = document.getElementById("agent-id");
            var promptInput = document.getElementById("agent-prompt");
            var nodeId = (idInput && idInput.value ? idInput.value : "agent_" + nodeIdSeq++).trim();
            var promptText = (promptInput && promptInput.value
              ? promptInput.value
              : "请完成本步骤任务。"
            ).trim();
            if (!nodeId) {
              setStatus("请输入节点 ID", true);
              return;
            }
            if (state.nodes.some(function (n) { return n.node_id === nodeId; })) {
              setStatus("节点 ID 已存在，请换一个: " + nodeId, true);
              return;
            }
            var newNode = newAgentNode(nodeId);
            newNode.config.system_prompt = promptText;
            state.nodes.push(newNode);
            render();
            setStatus("已添加 Agent 节点: " + nodeId, false);
            if (promptInput) promptInput.value = "";
            return;
          }
          if (tgt.closest("#add-tool-btn")) {
            ev.preventDefault();
            var sel = document.getElementById("tool-select");
            var idInputT = document.getElementById("tool-node-id");
            var toolName = (sel && sel.value) || "markdown_section";
            var nodeIdT = (idInputT && idInputT.value ? idInputT.value : toolName).trim();
            if (!nodeIdT) nodeIdT = toolName;
            if (state.nodes.some(function (n) { return n.node_id === nodeIdT; })) {
              nodeIdT = toolName + "_" + nodeIdSeq++;
            }
            var newTool = newToolNode(nodeIdT);
            newTool.tool_name = toolName;
            newTool.config.tool_input = defaultToolInputFor(toolName);
            state.nodes.push(newTool);
            render();
            setStatus("已添加 Tool 节点: " + nodeIdT + " → " + toolName, false);
          }
        },
        false
      );
    }

    fillToolSelectFromNames(FALLBACK_TOOL_NAMES);
    fetch(API + "tools/list", { method: "GET" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) {
        var tools = (d && d.tools) || [];
        var sel = document.getElementById("tool-select");
        if (!sel) return;
        if (!tools.length) {
          fillToolSelectFromNames(FALLBACK_TOOL_NAMES);
          return;
        }
        sel.innerHTML = "";
        tools.forEach(function (t) {
          var name = (t && t.name) ? String(t.name).trim() : "";
          if (!name) return;
          var label = name;
          if (t.description) {
            label += " — " + String(t.description).slice(0, 52);
          }
          sel.appendChild(el("option", { value: name, textContent: label }));
        });
        if (!sel.options.length) {
          fillToolSelectFromNames(FALLBACK_TOOL_NAMES);
        }
      })
      .catch(function () {
        fillToolSelectFromNames(FALLBACK_TOOL_NAMES);
      });

    fetch(API + "workflow/draft", { method: "GET" })
      .then(function (r) {
        return r.json();
      })
      .then(function (d) {
        state.nodes = (d.nodes || []).map(function (x) {
          return JSON.parse(JSON.stringify(x));
        });
        state.edges = (d.edges || []).map(function (x) {
          return { from_node: x.from_node || x.from, to_node: x.to_node || x.to, condition: null };
        });
        migrateDeliverToExecute();
        ensureDesignExecute();
        refreshWorkflowCanvas();
        setStatus("已从服务器加载草稿（design / execute 已保证）", false);
      })
      .catch(function () {
        state.nodes = [newAgentNode("design"), newAgentNode("execute")];
        state.nodes[0].config.system_prompt =
          "你是设计节点，把用户问题整理为清晰任务说明与可执行结构，供下一节点使用。";
        state.nodes[1].config.system_prompt =
          "你是执行/交付节点，基于上游设计生成完整、可执行的最终回答。";
        state.edges = [{ from_node: "design", to_node: "execute", condition: null }];
        refreshWorkflowCanvas();
        setStatus("已加载默认 design → execute", false);
      });

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

    var wfSel = document.getElementById("workflow-select");
    if (wfSel) {
      wfSel.addEventListener("change", refreshWorkflowCanvas, false);
    }
    var modeSel = document.getElementById("mode");
    if (modeSel) {
      modeSel.addEventListener("change", refreshWorkflowCanvas, false);
    }
  }

  /** 高亮当前执行批次对应的节点（与 /api/chat NDJSON 的 exec_nodes 配合） */
  function setTexAgentWorkflowActiveNodes(nodeIds) {
    var prev = document.getElementById("wf-preview");
    if (!prev) return;
    var svg = prev.querySelector("svg");
    if (!svg) return;
    var want = {};
    if (nodeIds && nodeIds.length) {
      nodeIds.forEach(function (id) {
        if (id == null) return;
        var s = String(id).trim();
        if (s) want[s] = true;
      });
    }
    svg.querySelectorAll("[data-wf-node-id]").forEach(function (el) {
      var id = el.getAttribute("data-wf-node-id");
      if (id && want[id]) el.classList.add("wf-node-exec-active");
      else el.classList.remove("wf-node-exec-active");
    });
  }
  window.setTexAgentWorkflowActiveNodes = setTexAgentWorkflowActiveNodes;

  /** plan 模式聊天返回的运行时图（供 app.js 调用） */
  function applyPlanGraphPreview(graph) {
    if (!graph) return;
    var prev = document.getElementById("wf-preview");
    if (!prev) return;
    var nodes = (graph.nodes || []).map(function (x) {
      return JSON.parse(JSON.stringify(x));
    });
    var edges = (graph.edges || []).map(function (x) {
      return {
        from_node: x.from_node || x.from,
        to_node: x.to_node || x.to,
        condition: x.condition != null ? x.condition : null,
      };
    });
    if (!nodes.length) return;
    renderWfPreview(prev, nodes, edges, { readOnly: true });
  }
  window.applyTexAgentPlanGraph = applyPlanGraphPreview;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
