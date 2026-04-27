# TeX Agent Chat（VS Code / Cursor 扩展）

在侧栏与编辑器中嵌入与本仓库 `ui.web.server` 相同的聊天页，交互方式类似 Cursor 的聊天区（本扩展负责「壳 + iframe」，实际页面仍由本机 HTTP 服务提供）。

## 前置条件

1. 在仓库根已安装依赖并能启动 Web UI：
   - `python -m ui.web.server`（默认 <http://127.0.0.1:8765>）
2. 设置里 `texagent.webServerUrl` 与上述地址一致（默认已匹配）。

## 开发调试

1. 用 VS Code / Cursor 打开本仓库根目录 `Tex_Agent`。
2. 终端先启动 `python -m ui.web.server`（或调试用时也可后启动，再点扩展里的刷新）。
3. **运行和调试** 中选择 **Run Extension: TeX Agent Chat**，会打开 **Extension Development Host** 新窗口。
4. 在新窗口活动栏点 **TeX Agent** 图标，打开 **聊天** 视图。

## 正式安装到本机

在 `vscode-extension` 目录下：

```bash
npm i -g @vscode/vsce
vsce package
code --install-extension ./tex-agent-chat-0.1.0.vsix
```

（Cursor 用户可用 **Extensions: Install from VSIX** 选生成的 `.vsix`。）

## 最省事打开 Simple Browser（与 Cursor 里「有块聊天区」最接近）

- **状态栏**（已打开本仓库，且本扩展已安装/处于开发宿主）：点左下 **「TeX Agent 聊天」**。
- **快捷键**：**Ctrl+Alt+T**（Mac：**Cmd+Alt+T**）→ 直接在内置 Simple Browser 打开 `http://127.0.0.1:8765/`（地址可在设置里改）。
- **没装本扩展**时：在仓库里按 **Ctrl+Shift+B**（运行「默认 build 任务」）= 等效打开 Simple Browser（见根目录 `.vscode/tasks.json`）。

## 其他命令

| 命令 | 说明 |
|------|------|
| **TeX Agent: 在 Simple Browser 打开聊天** | 同上，命令面板可搜 |
| **TeX Agent: 在编辑器区域打开聊天** | 主区 Webview 大面板，可拖到第二窗口 |
| **TeX Agent: 在终端启动 Web 服务** | 在集成终端中执行 `python -m ui.web.server`（需已打开工作区根） |
| 侧栏标题上的 **刷新** | 重载侧栏 Webview 嵌入页 |

## 说明

- 扩展用 **Webview + iframe** 嵌入本地页面，与浏览器访问 `8765` 是同一套 UI。
- **侧栏报 `An error occurred while loading view` 或显示「侧栏内容加载失败」**：常见原因包括 (1) HTML 里自写 **`<meta http-equiv="Content-Security-Policy">`** 与编辑器注入的 CSP 冲突—**当前实现已去掉自写 CSP**；(2) 内联 `<script>` 被禁止—**不要加脚本**。若仍失败：看 **输出** 面板 → 渠道选 **「TeX Agent」** 见具体错误；或 **Ctrl+Alt+T** 用 Simple Browser。
- 若需完全离线内嵌（不跑 HTTP），需改为把 `ui/web/static` 打进扩展并用 `asWebviewUri` 提供资源，与当前架构不同，可另做一版。
