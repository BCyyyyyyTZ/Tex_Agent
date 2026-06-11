(function () {
  const chat = document.getElementById("chat-scroll") || document.getElementById("chat");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  const mode = document.getElementById("mode");
  const workflowSelect = document.getElementById("workflow-select");
  const workflowSelectWrap = document.getElementById("workflow-select-wrap");

  var qs = {};
  try {
    qs = Object.fromEntries(new URLSearchParams(window.location.search).entries());
  } catch (_e) {
    /* empty */
  }
  var isVsCodeEmbed = qs._vscode_embed === "1" || qs._vscode_embed === "true";
  if (isVsCodeEmbed) {
    document.documentElement.setAttribute("data-vscode-embed", "1");
  }

  var submitLock = false;
  var thinkingTimerId = null;
  var thinkingStartMs = 0;
  var thinkingContentEl = null;
  /** 递增后可使进行中的 /api/chat 响应不再写回 DOM（分支切换等） */
  var chatRequestGen = 0;
  var chatAbortController = null;
  /** 各分支在 UI 上保留的用户↔Agent 对话（仅展示层；服务端上下文仍按分支隔离） */
  var branchDialogueCache = {};
  var activeBranchId = "main";

  /** 侧栏 iframe / 若干嵌入场景下须用绝对地址，避免相对 /api 解析到错误源 */
  function apiChatUrl() {
    try {
      return new URL("/api/chat", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/chat";
    }
  }

  const CHAT_URL = apiChatUrl();
  /** LLM 可能很慢，勿用短超时 */
  const FETCH_MS = 30 * 60 * 1000;

  var PURIFY = {
    ADD_ATTR: ["class", "id", "target", "rel", "open", "download"],
    ADD_TAGS: ["details", "summary", "span"],
  };

  /* marked v12+ 已移除 highlight 回调；gfm / breaks 建议随 parse 传入 */
  /* breaks:false — 仅空行分段；单换行由服务端 normalize_reply_display 处理 */
  var MARK_PARSE_OPTS = { gfm: true, breaks: false, async: false };

  /**
   * Markdown → 安全 HTML；DOMPurify 后再用 highlight.js 扫一遍 code 块
   * （否则代码块无 hljs 类名高亮，易被误认为「没解析」）
   */
  function renderMd(raw) {
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      const d = document.createElement("div");
      d.textContent = raw || "";
      return d.innerHTML;
    }
    const text = String(raw || "");
    try {
      const rawHtml = marked.parse(text, MARK_PARSE_OPTS);
      let pur = DOMPurify.sanitize(rawHtml, PURIFY);
      if (typeof hljs !== "undefined" && pur) {
        const wrap = document.createElement("div");
        wrap.innerHTML = pur;
        wrap.querySelectorAll("pre code").forEach(function (block) {
          try {
            if (typeof hljs.highlightElement === "function") {
              hljs.highlightElement(block);
            } else {
              const lang = (block.className || "").match(/language-(\S+)/);
              if (lang && lang[1] && hljs.getLanguage(lang[1])) {
                const r = hljs.highlight(block.textContent || "", { language: lang[1] });
                block.innerHTML = r.value;
                block.classList.add("hljs");
              } else {
                const r2 = hljs.highlightAuto(block.textContent || "", { ignoreIllegals: true });
                block.innerHTML = r2.value;
                block.classList.add("hljs");
              }
            }
          } catch (he) {
            console.warn("[TeX Agent UI] highlight 跳过", he);
          }
        });
        pur = wrap.innerHTML;
      }
      return pur;
    } catch (e) {
      console.warn("[TeX Agent UI] Markdown 解析失败，回退为纯文本", e);
      const d = document.createElement("div");
      d.textContent = text;
      return d.innerHTML;
    }
  }

  function hideEmptyPlaceholder() {
    const el = document.getElementById("chat-empty");
    if (el) {
      el.hidden = true;
    }
  }

  function isInternalAgentPrompt(text) {
    var t = String(text || "");
    if (!t) return false;
    if (t.indexOf("【用户本轮消息】") >= 0 && t.indexOf("【输出格式】") >= 0) {
      return true;
    }
    if (t.indexOf("[你的具体任务]") >= 0 && t.indexOf("[原始任务背景]") >= 0) {
      return true;
    }
    if (
      t.indexOf("【要求】") >= 0 &&
      t.indexOf("【禁止】") >= 0 &&
      t.indexOf("【输出格式】") >= 0
    ) {
      return true;
    }
    return false;
  }

  function normalizeDialogueList(messages) {
    const arr = Array.isArray(messages) ? messages : [];
    const out = [];
    for (let i = 0; i < arr.length; i++) {
      const m = arr[i];
      if (!m || typeof m !== "object") continue;
      const role = m.role === "user" ? "user" : "assistant";
      const raw = m.content != null ? String(m.content) : "";
      if (!raw.trim()) continue;
      if (role === "user" && isInternalAgentPrompt(raw)) continue;
      out.push({ role: role, content: raw });
    }
    return out;
  }

  function appendMessage(role, bodyHtml, plainText, skipCacheSync) {
    hideEmptyPlaceholder();
    const wrap = document.createElement("div");
    wrap.className = "msg " + role;
    if (plainText != null && String(plainText).trim()) {
      wrap.dataset.plainText = String(plainText);
    }
    const label = document.createElement("div");
    label.className = "msg-role";
    label.textContent = role === "user" ? "你" : "TeX Agent";
    const content = document.createElement("div");
    content.className = "md";
    content.innerHTML = bodyHtml;
    wrap.appendChild(label);
    wrap.appendChild(content);
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
    if (!skipCacheSync && activeBranchId) {
      syncBranchDialogueCache(activeBranchId);
    }
    return wrap;
  }

  function collectDialogueFromDom() {
    const scroll = document.getElementById("chat-scroll") || chat;
    if (!scroll) return [];
    const out = [];
    scroll.querySelectorAll(".msg").forEach(function (wrap) {
      if (wrap.classList.contains("loading")) return;
      const role = wrap.classList.contains("user") ? "user" : "assistant";
      const plain = wrap.dataset.plainText || "";
      if (!plain.trim()) return;
      if (role === "user" && isInternalAgentPrompt(plain)) return;
      out.push({ role: role, content: plain });
    });
    return out;
  }

  function syncBranchDialogueCache(branchId) {
    if (!branchId) return;
    branchDialogueCache[branchId] = collectDialogueFromDom();
  }

  function renderDialogueToChat(messages) {
    const scroll = document.getElementById("chat-scroll") || chat;
    if (!scroll) return;
    const arr = normalizeDialogueList(messages);
    clearChatMessages();
    const emptyEl = document.getElementById("chat-empty");
    if (!arr.length) {
      if (emptyEl) emptyEl.hidden = false;
      scroll.scrollTop = 0;
      return;
    }
    if (emptyEl) emptyEl.hidden = true;
    for (let i = 0; i < arr.length; i++) {
      const m = arr[i];
      appendMessage(m.role, renderMd(m.content), m.content, true);
    }
    if (activeBranchId) {
      branchDialogueCache[activeBranchId] = arr.slice();
    }
    scroll.scrollTop = scroll.scrollHeight;
  }

  function clearChatMessages() {
    const scroll = document.getElementById("chat-scroll") || chat;
    if (!scroll) return;
    scroll.querySelectorAll(".msg").forEach(function (n) {
      n.remove();
    });
  }

  /**
   * 切换分支后由 branch_graph 调用：用服务端该分支的对话记录重建聊天区。
   * @param {number} [expectedSeq] 与 branch_graph 的 historyLoadSeq 对齐，防止快速连点串台
   */
  function replaceChatFromHistory(messages, expectedSeq) {
    if (
      expectedSeq != null &&
      typeof window.texAgentBranchHistorySeq === "number" &&
      expectedSeq !== window.texAgentBranchHistorySeq
    ) {
      return;
    }
    renderDialogueToChat(messages);
  }

  function setActiveBranch(branchId) {
    activeBranchId = String(branchId || "main");
    window.texAgentActiveBranchId = activeBranchId;
  }

  /**
   * 切换分支：保存离开分支的 UI 对话，立即展示目标分支缓存，后端仅切换上下文。
   * @param {string} fromBranch 当前分支
   * @param {string} toBranch 目标分支
   */
  function prepareBranchSwitch(fromBranch, toBranch) {
    if (fromBranch) {
      syncBranchDialogueCache(fromBranch);
    }
    chatRequestGen += 1;
    if (chatAbortController) {
      try {
        chatAbortController.abort();
      } catch (_abort) {
        /* empty */
      }
      chatAbortController = null;
    }
    stopThinkingTimer();
    submitLock = false;
    setBusy(false);
    if (toBranch) {
      setActiveBranch(toBranch);
    }
    const cached = branchDialogueCache[activeBranchId];
    if (cached && cached.length) {
      renderDialogueToChat(cached);
    } else {
      clearChatMessages();
      const emptyEl = document.getElementById("chat-empty");
      if (emptyEl) emptyEl.hidden = false;
    }
    if (typeof window.setTexAgentWorkflowActiveNodes === "function") {
      window.setTexAgentWorkflowActiveNodes([]);
    }
    if (typeof window.texAgentRefreshWorkflowCanvas === "function") {
      window.texAgentRefreshWorkflowCanvas();
    }
  }

  window.texAgentRenderMd = renderMd;
  window.texAgentReplaceChatFromHistory = replaceChatFromHistory;
  window.texAgentPrepareBranchSwitch = prepareBranchSwitch;
  window.texAgentSetActiveBranch = setActiveBranch;
  window.texAgentActiveBranchId = activeBranchId;

  function setBusy(b) {
    if (send) send.disabled = b;
    if (input) input.readOnly = b;
  }

  function syncWorkflowSelectVisibility() {
    if (!workflowSelectWrap || !mode) return;
    var show = mode.value === "task";
    workflowSelectWrap.hidden = !show;
    workflowSelectWrap.style.display = show ? "" : "none";
  }

  function formatThinkingElapsed(ms) {
    var sec = Math.max(0, Math.floor(ms / 1000));
    if (sec < 60) return sec + " 秒";
    var min = Math.floor(sec / 60);
    sec = sec % 60;
    if (min < 60) return min + " 分 " + sec + " 秒";
    var hr = Math.floor(min / 60);
    min = min % 60;
    return hr + " 小时 " + min + " 分 " + sec + " 秒";
  }

  function thinkingPlaceholderHtml(modeVal) {
    if (modeVal === "plan") {
      return (
        '<p class="thinking-line">' +
        '<span class="thinking-status-text" data-status="思考中">思考中</span>' +
        '<span class="thinking-time" aria-live="polite"> · 0 秒</span>' +
        "</p>"
      );
    }
    return "<p>思考中…</p>";
  }

  function stopThinkingTimer() {
    if (thinkingTimerId != null) {
      window.clearInterval(thinkingTimerId);
      thinkingTimerId = null;
    }
    thinkingContentEl = null;
    thinkingStartMs = 0;
  }

  function updateThinkingTimeDisplay() {
    if (!thinkingContentEl || !thinkingStartMs) return;
    var timeEl = thinkingContentEl.querySelector(".thinking-time");
    if (!timeEl) return;
    timeEl.textContent = " · " + formatThinkingElapsed(Date.now() - thinkingStartMs);
  }

  function setThinkingStatus(contentEl, statusText) {
    if (!contentEl) return;
    var statusEl = contentEl.querySelector(".thinking-status-text");
    if (statusEl) {
      statusEl.setAttribute("data-status", statusText);
      statusEl.textContent = statusText;
    }
    updateThinkingTimeDisplay();
  }

  function startThinkingTimer(contentEl, modeVal) {
    stopThinkingTimer();
    if (modeVal !== "plan" || !contentEl) return;
    thinkingContentEl = contentEl;
    thinkingStartMs = Date.now();
    updateThinkingTimeDisplay();
    thinkingTimerId = window.setInterval(updateThinkingTimeDisplay, 1000);
  }

  function onSubmitForm(e) {
    if (e) e.preventDefault();
    if (submitLock) return;
    if (!form || !input) return;

    const text = (input.value || "").trim();
    if (!text) return;
    submitLock = true;
    chatRequestGen += 1;
    var requestGen = chatRequestGen;

    const modeVal = (mode && mode.value) || "task";
    /* eslint-disable no-console */
    console.debug("[TeX Agent UI] post", CHAT_URL, { mode: modeVal });

    let wrap;
    let contentEl;
    try {
      appendMessage("user", renderMd(text), text);
      input.value = "";
      setBusy(true);
      wrap = appendMessage("assistant", thinkingPlaceholderHtml(modeVal));
      wrap.classList.add("loading");
      contentEl = wrap.querySelector(".md");
      startThinkingTimer(contentEl, modeVal);
    } catch (err) {
      console.error(err);
      appendMessage("assistant", "<p class='error-banner'>页面渲染错误: " + String(err.message || err) + "</p>");
      submitLock = false;
      return;
    }

    const ac = new AbortController();
    chatAbortController = ac;
    const t = window.setTimeout(function () {
      ac.abort();
    }, FETCH_MS);
    const done = function () {
      window.clearTimeout(t);
      if (chatAbortController === ac) {
        chatAbortController = null;
      }
    };
    function isStaleRequest() {
      return requestGen !== chatRequestGen;
    }

    (async function () {
      try {
        var wfVal = null;
        if (workflowSelect && workflowSelect.value) {
          wfVal = workflowSelect.value;
          if (wfVal === "default") wfVal = null;
        }
        var payload = {
          message: text,
          mode: modeVal,
        };
        if (wfVal) payload.workflow = wfVal;
        var sel =
          typeof getWebAssetSelection === "function"
            ? getWebAssetSelection()
            : null;
        if (sel) {
          if (sel.active_pdfs && sel.active_pdfs.length) {
            payload.active_pdfs = sel.active_pdfs;
          }
          if (sel.active_documents && sel.active_documents.length) {
            payload.active_documents = sel.active_documents;
          }
          if (sel.active_skills && sel.active_skills.length) {
            payload.active_skills = sel.active_skills;
          }
          if (sel.active_checklists && sel.active_checklists.length) {
            payload.active_checklists = sel.active_checklists;
          }
        }
        if (modeVal === "plan" || modeVal === "task" || modeVal === "auto") {
          payload.stream = true;
        }
        const res = await fetch(CHAT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: ac.signal,
        });
        var ct = "";
        try {
          ct = (res.headers.get("content-type") || "").toLowerCase();
        } catch (_ct) {
          /* empty */
        }
        var useNdjson =
          (modeVal === "plan" || modeVal === "task" || modeVal === "auto") &&
          res.ok &&
          (ct.indexOf("ndjson") >= 0 || ct.indexOf("x-ndjson") >= 0);

        if (useNdjson && res.body && typeof res.body.getReader === "function") {
          const dec = new TextDecoder();
          let buf = "";
          const reader = res.body.getReader();
          let finalReply = "";
          let finalErr = null;
          let streamFail = null;
          while (true) {
            const step = await reader.read();
            if (step.done) break;
            buf += dec.decode(step.value, { stream: true });
            var nl;
            while ((nl = buf.indexOf("\n")) >= 0) {
              const line = buf.slice(0, nl).trim();
              buf = buf.slice(nl + 1);
              if (!line) continue;
              var obj;
              try {
                obj = JSON.parse(line);
              } catch (pe) {
                streamFail = pe;
                break;
              }
              if (!obj || typeof obj !== "object") continue;
              if (isStaleRequest()) break;
              if (obj.type === "plan_graph" && obj.plan_graph) {
                if (typeof window.applyTexAgentPlanGraph === "function") {
                  window.applyTexAgentPlanGraph(obj.plan_graph);
                }
                if (contentEl) {
                  setThinkingStatus(contentEl, "规划已完成，正在执行");
                }
              } else if (obj.type === "workflow_graph" && obj.workflow_graph) {
                if (typeof window.applyTexAgentPlanGraph === "function") {
                  window.applyTexAgentPlanGraph(obj.workflow_graph);
                }
                if (modeVal === "plan" && contentEl) {
                  setThinkingStatus(contentEl, "正在执行任务");
                } else if (contentEl) {
                  contentEl.innerHTML = "<p>正在执行任务…</p>";
                }
              } else if (obj.type === "error" && obj.detail != null) {
                if (typeof window.setTexAgentWorkflowActiveNodes === "function") {
                  window.setTexAgentWorkflowActiveNodes([]);
                }
                finalErr = String(obj.detail);
              } else if (obj.type === "exec_nodes" && obj.node_ids) {
                if (typeof window.setTexAgentWorkflowActiveNodes === "function") {
                  window.setTexAgentWorkflowActiveNodes(obj.node_ids);
                }
              } else if (obj.type === "result") {
                if (typeof window.setTexAgentWorkflowActiveNodes === "function") {
                  window.setTexAgentWorkflowActiveNodes([]);
                }
                finalReply = obj.reply != null ? String(obj.reply) : "";
                if (obj.error != null && obj.error !== "") {
                  finalErr = typeof obj.error === "string" ? obj.error : JSON.stringify(obj.error);
                }
              }
            }
            if (streamFail) break;
          }
          var planElapsedMs =
            modeVal === "plan" && thinkingStartMs
              ? Date.now() - thinkingStartMs
              : 0;
          stopThinkingTimer();
          if (isStaleRequest()) return;
          if (wrap) wrap.classList.remove("loading");
          if (streamFail) {
            throw streamFail;
          }
          let html = "";
          if (finalErr) {
            html +=
              '<div class="error-banner">' +
              (typeof finalErr === "string" ? finalErr : JSON.stringify(finalErr)) +
              "</div>";
          }
          if (modeVal === "plan" && planElapsedMs > 0) {
            html +=
              '<p class="thinking-done-meta">总耗时 ' +
              formatThinkingElapsed(planElapsedMs) +
              "</p>";
          }
          html += renderMd(finalReply);
          if (contentEl) contentEl.innerHTML = html;
          if (wrap) {
            wrap.dataset.plainText = finalErr
              ? String(finalErr) + "\n" + String(finalReply || "")
              : String(finalReply || "");
          }
          syncBranchDialogueCache(activeBranchId);
        } else {
          const data = await res.json().catch(function () {
            return {};
          });
          if (!res.ok) {
            const detail = data.detail || data.error || res.statusText;
            const msg = typeof detail === "string" ? detail : JSON.stringify(detail);
            throw new Error(msg);
          }
          const reply = data.reply != null ? String(data.reply) : "";
          const err = data.error;
          var planElapsedMs2 =
            modeVal === "plan" && thinkingStartMs
              ? Date.now() - thinkingStartMs
              : 0;
          stopThinkingTimer();
          if (isStaleRequest()) return;
          if (wrap) wrap.classList.remove("loading");
          let html = "";
          if (err) {
            html +=
              '<div class="error-banner">' +
              (typeof err === "string" ? err : JSON.stringify(err)) +
              "</div>";
          }
          if (modeVal === "plan" && planElapsedMs2 > 0) {
            html +=
              '<p class="thinking-done-meta">总耗时 ' +
              formatThinkingElapsed(planElapsedMs2) +
              "</p>";
          }
          /* 接口已只返回单段终局文本，这里直接当 Markdown 渲染 */
          html += renderMd(reply);
          if (contentEl) contentEl.innerHTML = html;
          if (wrap) {
            wrap.dataset.plainText = err
              ? String(err) + "\n" + String(reply || "")
              : String(reply || "");
          }
          syncBranchDialogueCache(activeBranchId);
          if (
            modeVal === "plan" &&
            data.plan_graph &&
            typeof window.applyTexAgentPlanGraph === "function"
          ) {
            window.applyTexAgentPlanGraph(data.plan_graph);
          }
        }
      } catch (err) {
        stopThinkingTimer();
        if (isStaleRequest()) return;
        if (typeof window.setTexAgentWorkflowActiveNodes === "function") {
          window.setTexAgentWorkflowActiveNodes([]);
        }
        if (err && err.name === "AbortError") {
          if (contentEl) {
            contentEl.innerHTML = '<div class="error-banner">请求超时，请重试或缩短任务/换用本地终端。</div>';
          }
        } else {
          if (wrap) wrap.classList.remove("loading");
          const msg = err && err.message ? err.message : String(err);
          if (contentEl) {
            contentEl.innerHTML = '<div class="error-banner"></div>';
            const b = contentEl.querySelector(".error-banner");
            if (b) b.textContent = msg;
          }
        }
      } finally {
        stopThinkingTimer();
        done();
        if (isStaleRequest()) return;
        setBusy(false);
        submitLock = false;
        if (input) {
          try {
            input.focus();
          } catch (_e) {
            /* 嵌入环境 focus 可能失败，忽略 */
          }
        }
      }
    })();
  }

  if (form) {
    form.addEventListener("submit", onSubmitForm, false);
  }

  if (mode) {
    mode.addEventListener("change", syncWorkflowSelectVisibility, false);
    syncWorkflowSelectVisibility();
  }

  if (input) {
    input.addEventListener(
      "keydown",
      function (e) {
        var isEnter = e.key === "Enter" || e.keyCode === 13;
        if (!isEnter) return;
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault();
          e.stopPropagation();
          onSubmitForm(e);
          return;
        }
        if (e.shiftKey) return;
        e.preventDefault();
        e.stopPropagation();
        onSubmitForm(e);
      },
      true
    );
  }

  /* VS Code 侧栏内嵌 iframe 时，type=submit 的默认行为常被宿主吞掉，须捕获阶段显式提交 */
  function wireSend() {
    if (!send) return;
    function go(ev) {
      if (ev) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      onSubmitForm(ev);
    }
    send.addEventListener("click", go, true);
  }
  wireSend();
})();
