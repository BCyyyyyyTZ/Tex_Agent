"use strict";
// @ts-check
const fs = require("fs");
const path = require("path");
const vscode = require("vscode");

const VIEW_ID_SIDEBAR = "texagent.chatView";

const LOG = "TeX Agent";

/** @type {Set<vscode.Webview>} */
const activeWebviews = new Set();

/**
 * 仅用于 iframe src；勿再自行注入 &lt;meta CSP&gt;，会与 VS Code / Cursor 内置策略冲突并导致 webview.html 赋值抛错。
 * @param {string} serverUrl
 */
function getFrameHtml(serverUrl) {
  let u = String(serverUrl).trim() || "http://127.0.0.1:8765";
  if (!/^https?:\/\//i.test(u)) u = "http://" + u;
  if (!u.endsWith("/")) u += "/";
  /* 查询串：供页面识别 VS Code 嵌入 + 去掉侧栏 iframe 强缓存的旧 JS */
  const sep = u.indexOf("?") >= 0 ? "&" : "?";
  u = u + sep + "_vscode_embed=1&_t=" + Date.now();
  const href = u.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <style>
    html, body { margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden;
      background: var(--vscode-sideBar-background, var(--vscode-panel-background));
    }
    body { display: flex; flex-direction: column; min-height: 0; }
    .hint {
      flex: 0 0 auto; font: 12px/1.4 var(--vscode-font-family);
      color: var(--vscode-descriptionForeground);
      padding: 4px 8px; border-bottom: 1px solid var(--vscode-widget-border, rgba(128,128,128,0.35));
    }
    .frame-wrap { flex: 1 1 auto; min-height: 200px; display: flex; flex-direction: column; min-width: 0; }
    iframe {
      flex: 1 1 auto; min-height: 0; width: 100%; border: 0; pointer-events: auto;
    }
  </style>
</head>
<body>
  <div class="hint">内嵌在侧栏时若点「发送」无反应，请 <strong>Ctrl+Alt+T</strong> 用 Simple Browser 打开同一页。需先 <code>python -m ui.web.server</code></div>
  <div class="frame-wrap">
  <iframe
    src="${href}"
    title="TeX Agent"
    allow="clipboard-read; clipboard-write; fullscreen; display-capture"
  ></iframe>
  </div>
</body>
</html>`;
}

function getServerUrl() {
  try {
    const c = vscode.workspace.getConfiguration("texagent");
    const u = c.get("webServerUrl");
    if (u && String(u).trim()) return String(u).trim();
  } catch (e) {
    console.error(LOG, "getServerUrl", e);
  }
  return "http://127.0.0.1:8765";
}

/** 与 Simple Browser / 任务用同一串 URL，保证末尾有 / */
function getChatPageUrl() {
  let u = String(getServerUrl()).trim() || "http://127.0.0.1:8765";
  if (!u.endsWith("/")) u += "/";
  return u;
}

function isTexAgentWorkspace() {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return false;
  for (const f of folders) {
    const marker = path.join(f.uri.fsPath, "ui", "web", "server.py");
    try {
      if (fs.existsSync(marker)) return true;
    } catch (_e) {
      /* empty */
    }
  }
  return false;
}

/**
 * 默认 proxy：侧栏不嵌 iframe，由主进程调 FastAPI，避免 Enter/点击被侧栏吃掉
 */
function getSidebarMode() {
  try {
    const c = vscode.workspace.getConfiguration("texagent");
    return c.get("sidebarMode") || "proxy";
  } catch (_e) {
    return "proxy";
  }
}

/**
 * @param {string} text
 * @param {string} [mode]
 */
async function postChatToServer(text, mode) {
  const base0 = getServerUrl().trim();
  const base = /^https?:\/\//i.test(base0) ? base0 : "http://" + base0;
  const u = new URL("api/chat", base.endsWith("/") ? base : base + "/");
  const res = await fetch(u, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ message: String(text), mode: mode || "task" }),
  });
  const data = await res.json().catch(function () {
    return {};
  });
  if (!res.ok) {
    const d = data.detail;
    const msg =
      d != null
        ? typeof d === "string"
          ? d
          : JSON.stringify(d)
        : res.status + " " + res.statusText;
    throw new Error(msg);
  }
  return { reply: data.reply || "", error: data.error != null ? data.error : null };
}

/**
 * 侧栏「代理模式」：轻量 UI + 扩展内 fetch
 * @param {vscode.Webview} webview
 * @param {vscode.Uri} extensionUri
 */
function getProxySidebarHtml(webview, extensionUri) {
  const script = webview.asWebviewUri(
    vscode.Uri.joinPath(extensionUri, "media", "chat-sidebar.js")
  );
  const sc = String(script);
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <style>
    html, body { margin:0; height:100%; background: var(--vscode-sideBar-background);
      color: var(--vscode-foreground); font: 13px/1.45 var(--vscode-font-family, sans-serif);
      display:flex; flex-direction:column; }
    h1 { font-size: 13px; margin: 8px; font-weight: 600; }
    p.hi { font-size: 11px; color: var(--vscode-descriptionForeground); margin: 0 8px 8px; }
    #chat { flex:1; overflow-y:auto; padding: 8px; min-height:0; }
    .tmsg { margin-bottom: 10px; }
    .tmsg .who { font-size: 11px; color: var(--vscode-descriptionForeground); margin-bottom: 4px; }
    .tmsg .pre { border-radius: 6px; padding: 8px; }
    .tmsg.user .pre { background: var(--vscode-input-background); }
    .tmsg.asst .pre { background: var(--vscode-editor-inactiveSelectionBackground, rgba(100,100,100,0.2)); }
    .pre { white-space: pre-wrap; word-break: break-word; }
    .th { opacity: 0.85; }
    .err { color: var(--vscode-errorForeground); }
    .bar { display:flex; flex-direction: column; padding: 8px; gap:6px; flex:0 0 auto; }
    #input { width: 100%; min-height: 64px; resize: vertical;
      background: var(--vscode-input-background); color: var(--vscode-input-foreground);
      border: 1px solid var(--vscode-input-border, var(--vscode-widget-border));
      border-radius: 4px; padding: 6px; box-sizing: border-box; }
    .row { display:flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    #send { align-self: flex-end; padding: 6px 14px; cursor: pointer;
      background: var(--vscode-button-background); color: var(--vscode-button-foreground);
      border: none; border-radius: 4px; }
    #send:disabled { opacity: 0.5; }
  </style>
</head>
<body>
  <h1>TeX Agent</h1>
  <p class="hi">侧栏 <strong>代理模式</strong>：Enter 发送、Shift+Enter 换行。需先运行 <code>python -m ui.web.server</code>。完整 Web UI 请 <strong>Ctrl+Alt+T</strong> 用 Simple Browser。</p>
  <div id="chat"></div>
  <div class="bar">
    <div class="row">
      <label>模式
        <select id="mode">
          <option value="task" selected>task</option>
          <option value="plan">plan</option>
        </select>
      </label>
    </div>
    <textarea id="input" rows="3" placeholder="输入；Enter 发送、Shift+Enter 换行；也可 Ctrl+Enter 发送。输出里若有「侧栏 webview 已就绪」则脚本已加载。"></textarea>
    <button type="button" id="send">发送</button>
  </div>
  <script src="${sc}"></script>
</body>
</html>`;
}

/**
 * @param {vscode.Webview} webview
 * @param {vscode.OutputChannel} logCh
 */
function attachChatBridge(webview, logCh) {
  if (/** @type {Record<string, unknown>} */ (webview).__texagentBridge) {
    return;
  }
  /** @type {Record<string, unknown>} */ (webview).__texagentBridge = true;
  webview.onDidReceiveMessage(function (msg) {
    if (!msg) {
      return;
    }
    if (msg.type === "ready") {
      logCh.appendLine("侧栏 webview 已就绪（代理模式可发消息）");
      return;
    }
    if (msg.type === "pong") {
      return;
    }
    if (msg.type === "chat") {
      const id = msg.id;
      const bodyId = msg.bodyId;
      void (async function () {
        try {
          const r = await postChatToServer(msg.text, msg.mode);
          webview.postMessage({
            type: "chatResult",
            id: id,
            bodyId: bodyId,
            reply: r.reply,
            error: r.error,
          });
        } catch (e) {
          const m = e && e.message ? e.message : String(e);
          logCh.appendLine("chat: " + m);
          webview.postMessage({
            type: "chatError",
            id: id,
            bodyId: bodyId,
            message: m,
          });
        }
      })();
    }
  });
}

/**
 * @param {vscode.Webview} webview
 * @param {vscode.Uri} extensionUri
 * @param {vscode.OutputChannel} logCh
 */
function applyWebviewContent(webview, extensionUri, logCh) {
  const mode = getSidebarMode();
  if (mode === "iframe") {
    webview.options = {
      enableScripts: false,
      retainContextWhenHidden: true,
      localResourceRoots: [extensionUri],
    };
    webview.html = getFrameHtml(getServerUrl());
  } else {
    webview.options = {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [extensionUri],
    };
    webview.html = getProxySidebarHtml(webview, extensionUri);
    attachChatBridge(webview, logCh);
  }
}

/**
 * 远程 vscode-server 等环境下 `webview.onDidDispose` 可能不存在，应优先用 WebviewView / WebviewPanel 的 `onDidDispose`。
 * @param {vscode.Webview} webview
 * @param {{ onDidDispose?: (cb: () => void) => vscode.Disposable }} owner
 */
function trackWebview(webview, owner) {
  activeWebviews.add(webview);
  const hook =
    owner && typeof owner.onDidDispose === "function" ? owner : webview;
  if (hook && typeof hook.onDidDispose === "function") {
    hook.onDidDispose(function () {
      activeWebviews.delete(webview);
    });
  }
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("texagent.openSimpleBrowser", function () {
      const url = getChatPageUrl();
      return vscode.commands.executeCommand("simpleBrowser.show", url);
    })
  );

  if (isTexAgentWorkspace()) {
    const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 99);
    status.text = "$(browser) TeX Agent 聊天";
    status.tooltip = "在 Simple Browser 打开聊天；快捷键 Alt+Ctrl+T（Mac：Alt+Cmd+T）";
    status.command = "texagent.openSimpleBrowser";
    status.show();
    context.subscriptions.push(status);
  }

  const extensionUri = context.extensionUri;
  const logCh = vscode.window.createOutputChannel(LOG);
  context.subscriptions.push(logCh);

  const provider = {
    /**
     * @param {import('vscode').WebviewView} webviewView
     */
    resolveWebviewView(webviewView) {
      const wv = webviewView.webview;
      try {
        applyWebviewContent(wv, extensionUri, logCh);
        trackWebview(wv, webviewView);
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        const stack = err && err.stack ? err.stack : "";
        logCh.appendLine("resolveWebviewView: " + msg);
        if (stack) logCh.appendLine(stack);
        void logCh.show();
        void vscode.window.showErrorMessage("TeX Agent 侧栏加载失败: " + msg);
        try {
          wv.html =
            "<!DOCTYPE html><html><body><p>若仍失败，请用 <strong>TeX Agent: 在 Simple Browser 打开聊天</strong>（Ctrl+Alt+T），并查看「输出」面板中「TeX Agent」的日志。</p></body></html>";
        } catch (_e) {
          /* empty */
        }
      }
    },
  };

  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(VIEW_ID_SIDEBAR, provider)
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("texagent.openChatPanel", function () {
      const panel = vscode.window.createWebviewPanel(
        "texagent.chatPanel",
        "TeX Agent",
        { viewColumn: vscode.ViewColumn.Beside, preserveFocus: false },
        {
          enableScripts: true,
          retainContextWhenHidden: true,
          localResourceRoots: [context.extensionUri],
        }
      );
      applyWebviewContent(panel.webview, context.extensionUri, logCh);
      trackWebview(panel.webview, panel);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("texagent.refreshWebview", function () {
      activeWebviews.forEach(function (w) {
        applyWebviewContent(w, extensionUri, logCh);
      });
      if (activeWebviews.size === 0) {
        vscode.window.showInformationMessage("尚无打开的 TeX Agent 聊天视图，请先从活动栏打开。");
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("texagent.startServerInTerminal", function () {
      const root =
        vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
      if (!root) {
        vscode.window.showWarningMessage("请先打开 TeX_Agent 项目根目录为工作区。");
        return;
      }
      const t = vscode.window.createTerminal({ name: "TeX Agent Web", cwd: root.uri });
      t.show();
      t.sendText("python scripts/start_texagent_web.py --no-browser");
      var openSb = true;
      try {
        openSb = !!vscode.workspace
          .getConfiguration("texagent")
          .get("openSimpleBrowserAfterStartServer");
      } catch (_e) {
        /* 默认 true */
      }
      if (openSb) {
        const url = getChatPageUrl();
        setTimeout(function () {
          void vscode.commands.executeCommand("simpleBrowser.show", url).then(
            undefined,
            function () {
              void vscode.window.showWarningMessage(
                "Simple Browser 未能自动打开，请按 Ctrl+Alt+T 或命令面板「TeX Agent: 在 Simple Browser 打开聊天」。"
              );
            }
          );
        }, 2200);
      }
      void vscode.window.showInformationMessage(
        openSb
          ? "已用单脚本启动服务（scripts/start_texagent_web.py --no-browser），即将在本窗口 Simple Browser 打开聊天页。"
          : "已用单脚本启动服务。可手动按 Ctrl+Alt+T 打开 Simple Browser。"
      );
    })
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(function (e) {
      if (
        e.affectsConfiguration("texagent.webServerUrl") ||
        e.affectsConfiguration("texagent.sidebarMode")
      ) {
        activeWebviews.forEach(function (w) {
          applyWebviewContent(w, extensionUri, logCh);
        });
      }
    })
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
