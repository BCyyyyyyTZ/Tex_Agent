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
  let compiling = false;
  let pdfRenderToken = 0;
  let pdfFetchController = null;
  let pdfDocCache = null;
  let pdfZoomPercent = 100;
  let pdfFitMode = "height";
  let selectionRange = null;

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
    if (compiling) return;
    if (currentFile && currentContent !== originalContent) {
      saveFile(currentFile, currentContent).then(doCompile).catch(doCompile);
    } else {
      doCompile();
    }
  };

  function doCompile() {
    if (compiling) return;
    compiling = true;
    var btn = document.getElementById("compileBtn");
    btn.disabled = true; btn.textContent = "编译中...";
    document.getElementById("compileStatus").textContent = "正在编译...";
    var compileFile = (project && project.main_tex) || currentFile;
    api("/api/projects/" + projectId + "/compile?file=" + encodeURIComponent(compileFile), { method: "POST" }).then(function(result) {
      if (result.success) {
        document.getElementById("compileStatus").textContent = "编译成功";
        if (result.pdf_base64) {
          showPdfFromBase64(result.pdf_base64);
        } else if (result.pdf_size > 0) {
          showPdfFromUrl();
        } else {
          document.getElementById("compileStatus").textContent = "编译成功，但未生成 PDF";
        }
      } else {
        document.getElementById("compileStatus").textContent = "编译失败 (" + (result.issues ? result.issues.length + " 问题" : "未知错误") + ")";
      }
      btn.disabled = false; btn.textContent = "▶ 编译";
      compiling = false;
      if (result.issues && result.issues.length) showDiagnostics(result.issues);
    }).catch(function(e) {
      document.getElementById("compileStatus").textContent = "编译失败: " + e.message;
      btn.disabled = false; btn.textContent = "▶ 编译";
      compiling = false;
    });
  }

  if (typeof pdfjsLib !== "undefined") {
    pdfjsLib.GlobalWorkerOptions.workerSrc = "/static/vendor/pdf.worker.min.js";
  }

  function decodeBase64Pdf(b64) {
    var binary = atob(b64);
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function getPdfViewerSize() {
    var viewer = document.getElementById("pdfViewer");
    return {
      width: Math.max(viewer.clientWidth - 16, 120),
      height: Math.max(viewer.clientHeight - 16, 120),
    };
  }

  function computeFitHeightScale(page) {
    var size = getPdfViewerSize();
    var base = page.getViewport({ scale: 1 });
    return size.height / base.height;
  }

  function getPageRenderScale(page) {
    var fitScale = computeFitHeightScale(page);
    if (pdfFitMode === "height") {
      return fitScale * (pdfZoomPercent / 100);
    }
    return fitScale * (pdfZoomPercent / 100);
  }

  function updatePdfZoomLabel() {
    var label = document.getElementById("pdfZoomLabel");
    if (label) label.textContent = pdfZoomPercent + "%";
    var slider = document.getElementById("pdfZoomSlider");
    if (slider) slider.value = String(pdfZoomPercent);
  }

  function renderPdfDocument(pdf, token) {
    var container = document.getElementById("pdfPages");
    container.innerHTML = "";

    function renderPage(pageNum) {
      if (token !== pdfRenderToken) return Promise.resolve();
      if (pageNum > pdf.numPages) return Promise.resolve();
      return pdf.getPage(pageNum).then(function(page) {
        var scale = getPageRenderScale(page);
        var viewport = page.getViewport({ scale: scale });
        var canvas = document.createElement("canvas");
        canvas.className = "pdf-page";
        canvas.dataset.page = String(pageNum);
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        container.appendChild(canvas);
        return page.render({ canvasContext: canvas.getContext("2d"), viewport: viewport }).promise
          .then(function() { return renderPage(pageNum + 1); });
      });
    }

    return renderPage(1);
  }

  function rerenderPdfZoom() {
    if (!pdfDocCache) return;
    pdfRenderToken += 1;
    var token = pdfRenderToken;
    updatePdfZoomLabel();
    renderPdfDocument(pdfDocCache, token).catch(function(e) {
      if (token !== pdfRenderToken) return;
      failPdfPreview(e.message);
    });
  }

  function bindPdfZoomControls() {
    var slider = document.getElementById("pdfZoomSlider");
    var zoomOut = document.getElementById("pdfZoomOut");
    var zoomIn = document.getElementById("pdfZoomIn");
    var fitHeight = document.getElementById("pdfFitHeight");
    if (!slider || slider.dataset.bound) return;
    slider.dataset.bound = "1";

    slider.addEventListener("input", function() {
      pdfZoomPercent = parseInt(slider.value, 10) || 100;
      pdfFitMode = "custom";
      rerenderPdfZoom();
    });
    zoomOut.addEventListener("click", function() {
      pdfZoomPercent = Math.max(50, pdfZoomPercent - 10);
      pdfFitMode = "custom";
      rerenderPdfZoom();
    });
    zoomIn.addEventListener("click", function() {
      pdfZoomPercent = Math.min(200, pdfZoomPercent + 10);
      pdfFitMode = "custom";
      rerenderPdfZoom();
    });
    fitHeight.addEventListener("click", function() {
      pdfZoomPercent = 100;
      pdfFitMode = "height";
      rerenderPdfZoom();
    });
  }

  function renderPdfBytes(bytes, token) {
    var viewer = document.getElementById("pdfViewer");
    var placeholder = document.getElementById("pdfPlaceholder");

    if (!bytes || bytes.byteLength === 0) {
      throw new Error("PDF 文件为空，请重新编译");
    }
    if (typeof pdfjsLib === "undefined") {
      throw new Error("PDF.js 未加载");
    }

    placeholder.style.display = "none";
    viewer.style.display = "block";
    document.getElementById("pdfPages").innerHTML = "<p style=\"padding:12px;color:#ccc;text-align:center\">渲染 PDF...</p>";
    bindPdfZoomControls();

    return pdfjsLib.getDocument({ data: bytes }).promise.then(function(pdf) {
      if (token !== pdfRenderToken) return;
      pdfDocCache = pdf;
      pdfZoomPercent = 100;
      pdfFitMode = "height";
      updatePdfZoomLabel();
      return renderPdfDocument(pdf, token);
    });
  }

  function showPdfFromBase64(b64) {
    pdfRenderToken += 1;
    var token = pdfRenderToken;
    if (pdfFetchController) {
      pdfFetchController.abort();
      pdfFetchController = null;
    }
    renderPdfBytes(decodeBase64Pdf(b64), token).catch(function(e) {
      if (token !== pdfRenderToken) return;
      failPdfPreview(e.message);
    });
  }

  function showPdfFromUrl() {
    pdfRenderToken += 1;
    var token = pdfRenderToken;
    if (pdfFetchController) pdfFetchController.abort();
    pdfFetchController = new AbortController();

    var viewer = document.getElementById("pdfViewer");
    var container = document.getElementById("pdfPages");
    var placeholder = document.getElementById("pdfPlaceholder");
    var url = "/api/projects/" + projectId + "/pdf?t=" + Date.now();

    placeholder.style.display = "none";
    viewer.style.display = "block";
    container.innerHTML = "<p style=\"padding:12px;color:#ccc;text-align:center\">加载 PDF...</p>";

    fetch(url, { signal: pdfFetchController.signal, cache: "no-store" }).then(function(r) {
      if (token !== pdfRenderToken) return null;
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.arrayBuffer();
    }).then(function(data) {
      if (!data || token !== pdfRenderToken) return;
      return renderPdfBytes(new Uint8Array(data), token);
    }).catch(function(e) {
      if (token !== pdfRenderToken || e.name === "AbortError") return;
      failPdfPreview(e.message);
    });
  }

  function failPdfPreview(message) {
    document.getElementById("pdfViewer").style.display = "none";
    document.getElementById("pdfPlaceholder").style.display = "flex";
    document.getElementById("compileStatus").textContent = "PDF 预览失败: " + message;
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

  function hideSelectionButton() {
    selBtn.style.display = "none";
  }

  function clearSelectionRange() {
    selectionRange = null;
    document.getElementById("polishBtn").dataset.selectedText = "";
  }

  function positionSelectionButton() {
    var start = editor.selectionStart;
    var end = editor.selectionEnd;
    if (start === end) {
      hideSelectionButton();
      clearSelectionRange();
      return;
    }
    var selText = editor.value.substring(start, end).trim();
    if (!selText) {
      hideSelectionButton();
      clearSelectionRange();
      return;
    }

    selectionRange = { start: start, end: end, text: selText };
    selBtn.dataset.selectedText = selText;

    var textBefore = editor.value.substring(0, end);
    var lineNo = textBefore.split("\n").length - 1;
    var style = window.getComputedStyle(editor);
    var lineHeight = parseFloat(style.lineHeight) || 20;
    var paddingTop = parseFloat(style.paddingTop) || 12;
    var charInLine = textBefore.split("\n").pop().length;
    var charWidth = 7.2;

    var top = paddingTop + lineNo * lineHeight - editor.scrollTop + 4;
    var left = parseFloat(style.paddingLeft) + charInLine * charWidth;

    top = Math.max(8, Math.min(top, editor.clientHeight - 36));
    left = Math.max(8, Math.min(left, editor.clientWidth - 64));

    selBtn.style.top = top + "px";
    selBtn.style.left = left + "px";
    selBtn.style.display = "block";
  }

  editor.addEventListener("mouseup", positionSelectionButton);
  editor.addEventListener("keyup", function(e) {
    if (e.key === "Escape") { hideSelectionButton(); clearSelectionRange(); }
    else if (e.shiftKey || e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "ArrowUp" || e.key === "ArrowDown") {
      positionSelectionButton();
    }
  });
  editor.addEventListener("scroll", function() {
    if (selBtn.style.display === "block") positionSelectionButton();
  });
  document.addEventListener("mousedown", function(e) {
    if (e.target !== selBtn && !editor.contains(e.target)) {
      hideSelectionButton();
      clearSelectionRange();
    }
  });

  selBtn.addEventListener("click", function(e) {
    e.preventDefault();
    e.stopPropagation();
    var selText = selBtn.dataset.selectedText || "";
    if (!selText || !selectionRange) return;

    showPolishPanel();
    document.getElementById("polishFile").value = currentFile;
    document.getElementById("polishQuery").value = "";
    document.getElementById("polishBtn").dataset.selectedText = selText;
    document.getElementById("polishResult").style.display = "none";
    document.getElementById("polishStatus").textContent = "正在润色选中文本...";
    hideSelectionButton();
    runPolish();
  });

  window.hidePolishPanel = function() {
    document.getElementById("polishOverlay").style.display = "none";
    document.getElementById("polishSlide").classList.remove("open");
  };

  window.runPolish = function() {
    var file = document.getElementById("polishFile").value || currentFile;
    var query = document.getElementById("polishQuery").value.trim();
    var selectedText = document.getElementById("polishBtn").dataset.selectedText || "";
    if (!query && !selectedText) {
      document.getElementById("polishStatus").textContent = "请输入润色需求或选中文本";
      return;
    }
    var btn = document.getElementById("polishBtn"); btn.disabled = true; btn.textContent = "生成中...";
    document.getElementById("polishResult").style.display = "none";
    document.getElementById("polishStatus").textContent = "正在请求 AI 润色...";
    api("/api/projects/" + projectId + "/polish", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_file: file, query: query, selected_text: selectedText})
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
    var ed = document.getElementById("codeEditor");
    var orig = polishResult.original_text || "";
    var polished = polishResult.polished_text || "";
    var applied = false;

    if (selectionRange && ed.value.substring(selectionRange.start, selectionRange.end).trim() === orig.trim()) {
      ed.value = ed.value.substring(0, selectionRange.start) + polished + ed.value.substring(selectionRange.end);
      applied = true;
    } else if (orig && ed.value.includes(orig)) {
      ed.value = ed.value.replace(orig, polished);
      applied = true;
    }

    if (applied) {
      currentContent = ed.value;
      saveFile(currentFile, currentContent);
      document.getElementById("polishStatus").textContent = "已应用润色";
      clearSelectionRange();
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
      if (pdfDocCache) rerenderPdfZoom();
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
      if (!compiling) compileProject();
    }
    if (e.ctrlKey && e.key === "s") {
      e.preventDefault();
      if (currentFile) saveFile(currentFile, currentContent);
    }
  });

  if (window.ResizeObserver) {
    var pdfViewerEl = document.getElementById("pdfViewer");
    if (pdfViewerEl) {
      new ResizeObserver(debounce(function() {
        if (pdfDocCache && pdfFitMode === "height" && pdfZoomPercent === 100) rerenderPdfZoom();
      }, 150)).observe(pdfViewerEl);
    }
  }

})();
