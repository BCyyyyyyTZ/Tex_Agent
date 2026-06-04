(function() {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  const projectId = params.get("project");
  if (!projectId) { document.body.innerHTML = "<div style='padding:40px;text-align:center'>缺少项目 ID</div>"; return; }

  let project = null;
  let currentFile = "";
  let currentContent = "";
  let originalContent = "";
  let polishResult = null;

  const $ = id => document.getElementById(id);

  function api(url, opts) {
    return fetch(url, opts).then(r => { if (!r.ok) return r.text().then(text => { try { var e = JSON.parse(text); var msg = typeof e.detail === "string" ? e.detail : (e.detail ? JSON.stringify(e.detail) : r.statusText); throw new Error(msg) } catch(pe) { throw new Error(text || r.statusText) } }); return r.json() });
  }

  function escapeHtml(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  // Load project
  api("/api/projects/" + projectId).then(data => {
    project = data;
    document.getElementById("projectName").textContent = data.name;
    document.getElementById("mainFile").textContent = data.main_tex || "";
    renderFileTree(data.files || []);
    if (data.main_tex) { openFile(data.main_tex); }
    else if (data.files && data.files.length) { openFile(data.files[0].path); }
  }).catch(e => {
    document.body.innerHTML = "<div style='padding:40px;text-align:center'>加载项目失败: " + escapeHtml(e.message) + "</div>";
  });

  // File tree
  function renderFileTree(files) {
    var list = document.getElementById("fileList");
    list.innerHTML = files.map(function(f) {
      var cls = "file-item" + (f.path === currentFile ? " active" : "");
      var icon = f.is_tex ? "T" : "F";
      return "<div class=\"" + cls + "\" onclick=\"openFile('" + f.path + "')\"><span class=\"icon" + (f.is_tex ? " tex" : "") + "\">" + icon + "</span>" + escapeHtml(f.name) + "</div>";
    }).join("");
  }

  // Open file
  window.openFile = function(path) {
    if (path === currentFile) return;
    if (currentFile && currentContent !== originalContent) {
      saveFile(currentFile, currentContent).then(function() {
        loadFile(path);
      }).catch(function() {
        if (confirm("保存失败，确定丢弃修改吗？")) loadFile(path);
      });
    } else {
      loadFile(path);
    }
  };

  function loadFile(path) {
    currentFile = path;
    document.getElementById("currentFileTab").textContent = path.split("/").pop();
    api("/api/projects/" + projectId + "/file?path=" + encodeURIComponent(path)).then(function(data) {
      currentContent = data.content;
      originalContent = data.content;
      document.getElementById("codeEditor").value = data.content;
      renderFileTree(project.files || []);
      // Auto-save on edit
      var editor = document.getElementById("codeEditor");
      editor.oninput = debounce(function() {
        currentContent = this.value;
        saveFile(currentFile, currentContent).then(function() { showSaveStatus("\u5df2\u4fdd\u5b58"); }).catch(function(e) { showSaveStatus("\u4fdd\u5b58\u5931\u8d25"); console.error("Auto-save failed:", e); });
      }, 2000);
    }).catch(function(e) {
      document.getElementById("codeEditor").value = "// Error: " + e.message;
    });
  }

  function saveFile(path, content) {
    return api("/api/projects/" + projectId + "/file?path=" + encodeURIComponent(path), {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({content: content})
    }).then(function() {
      originalContent = content;
    });
  }

  function debounce(fn, ms) {
    var timer;
    return function() {
      clearTimeout(timer);
      var ctx = this, args = arguments;
      timer = setTimeout(function() { fn.apply(ctx, args); }, ms);
    };
  }

  // Compile
  window.compileProject = function() {
    if (currentFile && currentContent !== originalContent) {
      saveFile(currentFile, currentContent).then(doCompile).catch(doCompile);
    } else {
      doCompile();
    }
  };

  function doCompile() {
    var btn = document.getElementById("compileBtn");
    btn.disabled = true; btn.textContent = "编译中...";
    document.getElementById("compileStatus").textContent = "正在编译...";
    api("/api/projects/" + projectId + "/compile?file=" + encodeURIComponent(currentFile), { method: "POST" }).then(function(result) {
      if (result.success) {
        document.getElementById("compileStatus").textContent = "编译成功";
        showPdf();
      } else {
        document.getElementById("compileStatus").textContent = "编译失败 (" + (result.issues ? result.issues.length + " 问题" : "未知错误") + ")";
      }
      btn.disabled = false; btn.textContent = "▶ 编译";
      if (result.issues && result.issues.length) showDiagnostics(result.issues);
    }).catch(function(e) {
      document.getElementById("compileStatus").textContent = "编译失败: " + e.message;
      btn.disabled = false; btn.textContent = "▶ 编译";
    });
  }

  function showPdf() {
    var iframe = document.getElementById("pdfViewer");
    document.getElementById("pdfPlaceholder").style.display = "none";
    iframe.src = "/api/projects/" + projectId + "/pdf?t=" + Date.now();
    iframe.style.display = "block";
  }

  window.togglePdfPanel = function() {
    var panel = document.getElementById("pdfPanel");
    panel.style.display = panel.style.display === "none" ? "flex" : "none";
  };

  // Polish
  window.showPolishPanel = function() {
    document.getElementById("polishOverlay").style.display = "block";
    document.getElementById("polishSlide").classList.add("open");
    if (project && project.files) {
      var sel = document.getElementById("polishFile");
      sel.innerHTML = project.files.filter(function(f) { return f.is_tex; }).map(function(f) {
        var selAttr = f.path === currentFile ? " selected" : "";
        return "<option value=\"" + f.path + "\"" + selAttr + ">" + escapeHtml(f.path) + "</option>";
      }).join("");
    }
  };


  // --- Text selection polish ---
  var editor = document.getElementById("codeEditor");
  var selBtn = document.getElementById("polishSelectionBtn");

  editor.addEventListener("mouseup", function() {
    var start = editor.selectionStart;
    var end = editor.selectionEnd;
    if (start !== end) {
      var selText = editor.value.substring(start, end).trim();
      if (selText.length > 0) {
        // Position the button near the selection
        selBtn.style.display = "block";
        selBtn.dataset.selectedText = selText;
        // Position near the top of the textarea
        selBtn.style.top = "auto";
        selBtn.style.bottom = "40px";
        selBtn.style.right = "10px";
        selBtn.style.left = "auto";
        return;
      }
    }
    selBtn.style.display = "none";
  });

  editor.addEventListener("keyup", function(e) {
    if (e.key === "Escape") {
      selBtn.style.display = "none";
    }
  });

  selBtn.addEventListener("click", function() {
    var selText = selBtn.dataset.selectedText || "";
    if (!selText) return;
    // Open polish panel with the selected text
    showPolishPanel();
    var queryBox = document.getElementById("polishQuery");
    queryBox.value = "????????????????\n\n" + selText;
    // Store the selected text for the API call
    var btn = document.getElementById("polishBtn");
    btn.dataset.selectedText = selText;
    // Auto-trigger polish after a short delay
    setTimeout(function() { runPolish(); }, 300);
    selBtn.style.display = "none";
  });

  window.hidePolishPanel = function() {
    document.getElementById("polishOverlay").style.display = "none";
    document.getElementById("polishSlide").classList.remove("open");
  };

  window.runPolish = function() {
    var file = document.getElementById("polishFile").value;
    var query = document.getElementById("polishQuery").value.trim();
    if (!query) { document.getElementById("polishStatus").textContent = "请输入润色需求"; return; }
    var btn = document.getElementById("polishBtn"); btn.disabled = true; btn.textContent = "生成中...";
    document.getElementById("polishResult").style.display = "none";
    document.getElementById("polishStatus").textContent = "正在请求 AI 润色...";
    api("/api/projects/" + projectId + "/polish", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_file: file, query: query, selected_text: document.getElementById("polishBtn").dataset.selectedText || ""})
    }).then(function(result) {
      document.getElementById("polishStatus").textContent = "润色建议已生成";
      polishResult = result;
      document.getElementById("polishProblem").textContent = result.problem_zh || "（无说明）";
      document.getElementById("polishOriginal").textContent = result.original_text || "（无原文）";
      document.getElementById("polishPolished").textContent = result.polished_text || "（无修改文本）";
      document.getElementById("polishResult").style.display = "block";
      btn.disabled = false; btn.textContent = "生成润色建议";
    }).catch(function(e) {
      document.getElementById("polishStatus").textContent = "润色失败: " + e.message;
      btn.disabled = false; btn.textContent = "生成润色建议";
    });
  };

  window.applyPolish = function() {
    if (!polishResult || !polishResult.polished_text) return;
    var editor = document.getElementById("codeEditor");
    var orig = polishResult.original_text || "";
    var polished = polishResult.polished_text || "";
    if (orig && editor.value.includes(orig)) {
      editor.value = editor.value.replace(orig, polished);
      currentContent = editor.value;
      saveFile(currentFile, currentContent);
      document.getElementById("polishStatus").textContent = "已应用润色";
    } else {
      document.getElementById("polishStatus").textContent = "找不到匹配的原文版本，请手动复制";
    }
  };

  // Diagnostics
  window.diagnoseProject = function() {
    api("/api/projects/" + projectId + "/diagnose").then(function(result) {
      showDiagnostics(result.issues || []);
    }).catch(function(e) {
      document.getElementById("diagnosticList").innerHTML = "<div class=\"diag-item error\">检测失败: " + escapeHtml(e.message) + "</div>";
      document.getElementById("diagnosticBar").style.display = "block";
    });
  };

  function showDiagnostics(issues) {
    var list = document.getElementById("diagnosticList");
    if (!issues.length) {
      list.innerHTML = "<div class=\"diag-item\" style=\"color:#4caf50\">✓ 无问题</div>";
    } else {
      list.innerHTML = issues.map(function(i) {
        return "<div class=\"diag-item " + (i.severity === "error" ? "error" : "warning") + "\">" +
          "<span class=\"file\">" + escapeHtml(i.file) + ":" + i.line + "</span>" +
          "<span>" + escapeHtml(i.message) + "</span></div>";
      }).join("");
    }
    document.getElementById("diagnosticBar").style.display = "block";
  }

  window.hideDiagnostics = function() {
    document.getElementById("diagnosticBar").style.display = "none";
  };


  // --- Draggable divider ---
  var divider = document.getElementById("panelDivider");
  var editorPanel = document.querySelector(".editor-panel");
  var pdfPanel = document.getElementById("pdfPanel");
  var isDragging = false;

  divider.addEventListener("mousedown", function(e) {
    isDragging = true;
    divider.classList.add("active");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  });

  document.addEventListener("mousemove", function(e) {
    if (!isDragging) return;
    var container = document.querySelector(".main-layout");
    var rect = container.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width * 100;
    if (pct < 20) pct = 20;
    if (pct > 80) pct = 80;
    editorPanel.style.flex = "0 0 " + pct + "%";
    pdfPanel.style.flex = "0 0 " + (100 - pct) + "%";
  });

  document.addEventListener("mouseup", function() {
    if (isDragging) {
      isDragging = false;
      divider.classList.remove("active");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
  });


  // --- Full document polish ---
  window.fullDocumentPolish = function() {
    showPolishPanel();
    // Clear any selected text
    document.getElementById("polishBtn").dataset.selectedText = "";
    document.getElementById("polishQuery").value = "Improve the overall academic quality, clarity, and flow of this document. Fix any grammar issues and enhance the writing style.";
    document.getElementById("polishQuery").focus();
  };

  // Keyboard shortcuts
  document.addEventListener("keydown", function(e) {
    if (e.ctrlKey && e.key === "Enter") {
      e.preventDefault();
      compileProject();
    }
    if (e.ctrlKey && e.key === "s") {
      e.preventDefault();
      if (currentFile) saveFile(currentFile, currentContent);
    }
  });

})();
