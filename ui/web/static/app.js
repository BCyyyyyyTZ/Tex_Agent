(function () {
  const chat = document.getElementById("chat-scroll") || document.getElementById("chat");
  const form = document.getElementById("form");
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  const mode = document.getElementById("mode");
  const workflowSelect = document.getElementById("workflow-select");

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
    ADD_ATTR: ["class", "id", "target", "rel", "open"],
    ADD_TAGS: ["details", "summary", "span"],
  };

  /* marked v12+ 已移除 highlight 回调；gfm / breaks 建议随 parse 传入 */
  var MARK_PARSE_OPTS = { gfm: true, breaks: true, async: false };

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

  function appendMessage(role, bodyHtml) {
    hideEmptyPlaceholder();
    const wrap = document.createElement("div");
    wrap.className = "msg " + role;
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
    return wrap;
  }

  function setBusy(b) {
    if (send) send.disabled = b;
    if (input) input.readOnly = b;
  }

  function onSubmitForm(e) {
    if (e) e.preventDefault();
    if (submitLock) return;
    if (!form || !input) return;

    const text = (input.value || "").trim();
    if (!text) return;
    submitLock = true;

    const modeVal = (mode && mode.value) || "task";
    /* eslint-disable no-console */
    console.debug("[TeX Agent UI] post", CHAT_URL, { mode: modeVal });

    let wrap;
    let contentEl;
    try {
      appendMessage("user", renderMd(text));
      input.value = "";
      setBusy(true);
      wrap = appendMessage("assistant", "<p>思考中…</p>");
      wrap.classList.add("loading");
      contentEl = wrap.querySelector(".md");
    } catch (err) {
      console.error(err);
      appendMessage("assistant", "<p class='error-banner'>页面渲染错误: " + String(err.message || err) + "</p>");
      submitLock = false;
      return;
    }

    const ac = new AbortController();
    const t = window.setTimeout(function () {
      ac.abort();
    }, FETCH_MS);
    const done = function () {
      window.clearTimeout(t);
    };

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
        const res = await fetch(CHAT_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: ac.signal,
        });
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
        if (wrap) wrap.classList.remove("loading");
        let html = "";
        if (err) {
          html +=
            '<div class="error-banner">' +
            (typeof err === "string" ? err : JSON.stringify(err)) +
            "</div>";
        }
        /* 接口已只返回单段终局文本，这里直接当 Markdown 渲染 */
        html += renderMd(reply);
        if (contentEl) contentEl.innerHTML = html;
      } catch (err) {
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
        done();
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
