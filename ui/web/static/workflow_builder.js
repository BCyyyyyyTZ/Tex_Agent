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

  var selectedFrom = null; // 用于直接在图示上连边

  function isProtectedNode(nodeId) {
    return nodeId === "design" || nodeId === "execute";
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
    var minBoxH = Math.max(L.H, 360); // 匹配更大预览区
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", String(minBoxH));
    svg.setAttribute("viewBox", "0 0 " + L.W + " " + minBoxH);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    gE = document.createElementNS(NS, "g");
    gE.setAttribute("class", "wf-edge-group");
    gN = document.createElementNS(NS, "g");
    gN.setAttribute("class", "wf-node-group");

    // 绘制边
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

    // 绘制节点 + 交互连边（IIFE 固定闭包，避免 for-in 共用同一 w）
    for (p in L.pos) {
      (function (w) {
        g = document.createElementNS(NS, "g");
        g.setAttribute("transform", "translate(" + w.x + "," + w.y + ")");
        var nodeType = (w.n && w.n.node_type) || "agent";
        var isSelected = selectedFrom && selectedFrom === w.n.node_id;

        t1 = document.createElementNS(NS, "rect");
        t1.setAttribute("width", w.w);
        t1.setAttribute("height", w.h);
        t1.setAttribute("rx", 6);
        var rectClass = "wf-node-rect";
        if (nodeType === "tool") rectClass += " tool-node";
        if (isSelected) rectClass += " selected";
        t1.setAttribute("class", rectClass);

        t2 = document.createElementNS(NS, "text");
        t2.setAttribute("x", w.w / 2);
        t2.setAttribute("y", w.h / 2 + 4);
        t2.setAttribute("text-anchor", "middle");
        t2.setAttribute("class", "wf-node-txt");
        var label = w.n.node_id.length > 11 ? w.n.node_id.slice(0, 10) + "…" : w.n.node_id;
        if (nodeType === "tool") label = "🛠 " + label;
        if (isSelected) label = "● " + label;
        t2.textContent = label;

        g.style.cursor = "pointer";
        g.addEventListener("click", function (ev) {
          ev.stopImmediatePropagation();
          var clickedId = w.n.node_id;
          var isProt = isProtectedNode(clickedId);
          var mountEl = document.getElementById("wf-preview");

          if (selectedFrom === null) {
            if (!isProt) {
              selectedFrom = clickedId;
              if (mountEl) renderWfPreview(mountEl, state.nodes, state.edges);
              window.setTimeout(function () {
                selectedFrom = null;
                if (mountEl) renderWfPreview(mountEl, state.nodes, state.edges);
              }, 8000);
            } else {
              editNode(w.n, state.nodes.findIndex(function (nd) { return nd.node_id === clickedId; }));
            }
          } else {
            if (selectedFrom !== clickedId && !state.edges.some(function (ex) {
              return ex.from_node === selectedFrom && ex.to_node === clickedId;
            })) {
              state.edges.push({ from_node: selectedFrom, to_node: clickedId, condition: null });
            }
            selectedFrom = null;
            render();
          }
        });

        g.appendChild(t1);
        g.appendChild(t2);
        gN.appendChild(g);
      })(L.pos[p]);
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

    state.nodes.forEach(function (node, idx) {
      var isProtected = isProtectedNode(node.node_id);
      var box = el("div", { 
        className: "wf-node-row" + (isProtected ? " wf-node-protected" : ""),
        title: isProtected ? "入口 design / 出口 execute 不可删除。点击可编辑" : "点击节点编辑 prompt/tool"
      });
      box.addEventListener("click", function (e) {
        if (e.target.tagName === "BUTTON" || e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
        editNode(node, idx);
      });

      var h = el("div", { className: "wf-node-row-h" });
      var typeBadge = el("span", { 
        className: "wf-node-type-badge",
        textContent: node.node_type || "agent"
      });
      if (node.node_type === "tool") typeBadge.style.background = "#2a5e2a";
      if (node.node_type === "entry" || node.node_type === "exit") typeBadge.style.background = "#3a3a8a";
      h.appendChild(typeBadge);

      h.appendChild(
        el("label", { className: "wf-inline", textContent: "ID" })
      );
      var idInp = el("input", { type: "text", className: "branch-input wf-node-id" });
      idInp.value = node.node_id;
      idInp.setAttribute("data-oid", node.node_id);
      idInp.disabled = isProtected;
      idInp.addEventListener("change", function () {
        var ov = idInp.getAttribute("data-oid");
        var nv = (idInp.value || "").trim().replace(/[^a-zA-Z0-9_-]/g, "_");
        if (!nv || isProtectedNode(ov)) {
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
      rm.textContent = isProtected ? "保护" : "删除";
      rm.disabled = isProtected;
      rm.addEventListener("click", function (e) {
        e.stopPropagation();
        if (isProtected) {
          alert("入口 design 与出口 execute 不可删除。");
          return;
        }
        if (confirm("删除节点 " + node.node_id + "？这将清除所有相关边。")) {
          var oid = node.node_id;
          state.nodes = state.nodes.filter(function (x) {
            return x.node_id !== oid;
          });
          state.edges = state.edges.filter(function (e) {
            return e.from_node !== oid && e.to_node !== oid;
          });
          render();
          initEdgeForm();
        }
      });
      h.appendChild(rm);
      box.appendChild(h);

      // 条件编辑字段
      if (node.node_type === "agent" || node.node_type === "SimpleAgent") {
        var taPrompt = el("textarea", { className: "wf-ta" });
        taPrompt.setAttribute("rows", "3");
        taPrompt.placeholder = "system_prompt：论文检查专家职责...";
        taPrompt.value = (node.config && node.config.system_prompt) || (node.config && node.config.subtask) || "";
        taPrompt.addEventListener("change", function () {
          if (!node.config) node.config = {};
          node.config.system_prompt = taPrompt.value;
        });
        box.appendChild(taPrompt);
      } else if (node.node_type === "tool") {
        var toolNameLabel = el("div", { className: "wf-field-label", textContent: "tool_name" });
        box.appendChild(toolNameLabel);
        var toolInp = el("input", { 
          type: "text", 
          className: "branch-input wf-tool-name",
          value: node.tool_name || ""
        });
        toolInp.addEventListener("change", function () {
          node.tool_name = toolInp.value.trim();
        });
        box.appendChild(toolInp);

        var taInput = el("textarea", { className: "wf-ta" });
        taInput.setAttribute("rows", "3");
        taInput.placeholder = 'tool_input JSON 或字符串 (支持 ${metadata.xxx})';
        var inputVal = node.config && node.config.tool_input;
        taInput.value = typeof inputVal === "object" ? JSON.stringify(inputVal, null, 2) : String(inputVal || "");
        taInput.addEventListener("change", function () {
          if (!node.config) node.config = {};
          try {
            node.config.tool_input = JSON.parse(taInput.value);
          } catch (e) {
            node.config.tool_input = taInput.value;
          }
        });
        box.appendChild(taInput);
      } else {
        // entry/exit or other
        var desc = el("div", { className: "wf-ta", style: "background:#252526;padding:8px;font-size:11px;min-height:40px;" });
        desc.textContent = (node.config && node.config.description) || (node.node_type + " 节点");
        box.appendChild(desc);
      }

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
      renderWfPreview(prev, state.nodes, state.edges);
    }
    initEdgeForm();
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
            initEdgeForm();
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
            initEdgeForm();
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
        render();
        initEdgeForm();
        setStatus("已从服务器加载草稿（design / execute 已保证）", false);
      })
      .catch(function () {
        state.nodes = [newAgentNode("design"), newAgentNode("execute")];
        state.nodes[0].config.system_prompt =
          "你是设计节点，把用户问题整理为清晰任务说明与可执行结构，供下一节点使用。";
        state.nodes[1].config.system_prompt =
          "你是执行/交付节点，基于上游设计生成完整、可执行的最终回答。";
        state.edges = [{ from_node: "design", to_node: "execute", condition: null }];
        render();
        initEdgeForm();
        setStatus("已加载默认 design → execute", false);
      });

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
