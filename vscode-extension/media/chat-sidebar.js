/* global acquireVsCodeApi */
(function () {
  "use strict";
  // @ts-ignore
  var vscode;
  try {
    vscode = acquireVsCodeApi();
  } catch (e) {
    /* 非 webview 或重复 acquire 会失败，此时 Enter 会保持 textarea 默认换行 */
    return;
  }
  const chat = document.getElementById("chat");
  const input = document.getElementById("input");
  const send = document.getElementById("send");
  const mode = document.getElementById("mode");
  if (!input || !chat || !send) {
    return;
  }

  var inflight = false;
  var shiftForNextLine = false;
  var hasBeforeInput = typeof window.InputEvent === "function" && "inputType" in window.InputEvent.prototype;

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function appendLine(role, bodyHtml) {
    var w = document.createElement("div");
    w.className = "tmsg " + role;
    w.innerHTML = bodyHtml;
    chat.appendChild(w);
    chat.scrollTop = chat.scrollHeight;
    return w;
  }

  function doSend() {
    if (inflight) {
      return;
    }
    var t = (input.value || "").trim();
    if (!t) {
      return;
    }
    inflight = true;
    var rid = "p" + Date.now() + "-" + ((Math.random() * 1e6) | 0);
    var bodyId = "texagentB" + rid.replace(/[^a-zA-Z0-9]/g, "_");
    var modeVal = (mode && mode.value) || "task";
    input.value = "";
    appendLine("user", '<div class="who">你</div><div class="body pre">' + esc(t) + "</div>");
    appendLine(
      "asst",
      '<div class="who">TeX Agent</div><div id="' + bodyId + '" class="body pre th">思考中…</div>'
    );
    send.disabled = true;
    input.readOnly = true;
    vscode.postMessage({ type: "chat", id: rid, bodyId: bodyId, text: t, mode: modeVal });
  }

  window.addEventListener(
    "message",
    function (ev) {
      var m = ev.data;
      if (!m || m.type === "pong" || m.type === "ready") {
        return;
      }
      if (m.type !== "chatResult" && m.type !== "chatError") {
        return;
      }
      inflight = false;
      send.disabled = false;
      input.readOnly = false;
      var node = m.bodyId ? document.getElementById(m.bodyId) : null;
      if (node) {
        if (m.type === "chatError") {
          node.className = "body pre err";
          node.textContent = m.message || "错误";
        } else {
          var piece = m.error
            ? "[error] " + m.error + "\n\n" + (m.reply || "")
            : m.reply || "";
          node.className = "body pre";
          node.textContent = piece;
        }
      }
    },
    false
  );

  input.addEventListener(
    "keydown",
    function (e) {
      shiftForNextLine = !!e.shiftKey;
      if (e.isComposing || e.keyCode === 229) {
        return;
      }
      if (e.key !== "Enter" && e.keyCode !== 13) {
        return;
      }
      if (e.shiftKey) {
        return;
      }
      /* Ctrl+Enter / Cmd+Enter 常见「发送」快捷键，与宿主的 Enter 行为解耦 */
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        e.stopImmediatePropagation();
        doSend();
        return;
      }
      /* 部分宿主下 keydown 的 preventDefault 不拦得住换行，交给 beforeinput 兜底 */
      if (hasBeforeInput) {
        return;
      }
      e.preventDefault();
      e.stopImmediatePropagation();
      doSend();
    },
    true
  );

  if (hasBeforeInput) {
    input.addEventListener(
      "beforeinput",
      function (e) {
        if (e.isComposing) {
          return;
        }
        if (e.inputType !== "insertLineBreak" && e.inputType !== "insertParagraph") {
          return;
        }
        if (shiftForNextLine) {
          return;
        }
        e.preventDefault();
        e.stopImmediatePropagation();
        doSend();
      },
      true
    );
  }

  send.addEventListener(
    "click",
    function (e) {
      e.preventDefault();
      e.stopPropagation();
      doSend();
    },
    true
  );

  vscode.postMessage({ type: "ready" });
})();
