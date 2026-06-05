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
  let selectionSnapshot = null;

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
    closePolishFloatCard();
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

  function showSaveStatus(msg) {
    var el = document.getElementById("saveIndicator");
    if (!el) return;
    el.textContent = msg;
    el.className = "save-indicator saved";
    setTimeout(function() { el.textContent = ""; el.className = "save-indicator"; }, 2000);
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


  // --- Text selection polish (floating card) ---
  var editor = document.getElementById("codeEditor");
  var selBtn = document.getElementById("polishSelectionBtn");
  var polishFloatCard = null;

  function copyTextareaStyle(ta, el) {
    var computed = window.getComputedStyle(ta);
    var props = [
      "direction", "boxSizing", "overflowX", "overflowY",
      "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
      "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
      "fontStyle", "fontVariant", "fontWeight", "fontStretch", "fontSize",
      "lineHeight", "fontFamily", "textAlign", "textTransform",
      "textIndent", "textDecoration", "letterSpacing", "wordSpacing", "tabSize"
    ];
    el.style.whiteSpace = "pre-wrap";
    el.style.wordWrap = "break-word";
    el.style.position = "absolute";
    el.style.visibility = "hidden";
    el.style.overflow = "hidden";
    el.style.width = ta.clientWidth + "px";
    props.forEach(function(p) { el.style[p] = computed[p]; });
  }

  function getSelectionMirrorBox(ta, start, end) {
    var div = document.createElement("div");
    document.body.appendChild(div);
    copyTextareaStyle(ta, div);
    div.textContent = ta.value.substring(0, start);
    var mark = document.createElement("span");
    mark.textContent = ta.value.substring(start, end) || " ";
    div.appendChild(mark);

    var computed = window.getComputedStyle(ta);
    var borderTop = parseFloat(computed.borderTopWidth) || 0;
    var borderLeft = parseFloat(computed.borderLeftWidth) || 0;
    var padTop = parseFloat(computed.paddingTop) || 0;
    var padLeft = parseFloat(computed.paddingLeft) || 0;

    var top = mark.offsetTop + borderTop + padTop - ta.scrollTop;
    var left = mark.offsetLeft + borderLeft + padLeft - ta.scrollLeft;
    var width = mark.offsetWidth;
    var height = mark.offsetHeight;

    document.body.removeChild(div);

    var wrap = document.querySelector(".editor-wrap");
    var taRect = ta.getBoundingClientRect();
    return {
      wrapTop: ta.offsetTop + top,
      wrapLeft: ta.offsetLeft + left,
      wrapRight: ta.offsetLeft + left + width,
      wrapBottom: ta.offsetTop + top + height,
      width: width,
      height: height,
      viewportTop: taRect.top + top,
      viewportLeft: taRect.left + left,
      viewportRight: taRect.left + left + width,
      viewportBottom: taRect.top + top + height
    };
  }
  function hideSelectionButton() {
    selBtn.style.display = "none";
  }

  function clearSelectionRange() {
    selectionRange = null;
  }

  function closePolishFloatCard() {
    if (polishFloatCard) {
      polishFloatCard.remove();
      polishFloatCard = null;
    }
    selectionSnapshot = null;
  }

  function activeSelection() {
    return selectionSnapshot || selectionRange;
  }

  function setupPolishCardDrag(card, head) {
    head.addEventListener("mousedown", function(e) {
      if (e.button !== 0 || e.target.closest(".card-close")) return;
      e.preventDefault();
      e.stopPropagation();
      card.classList.add("is-dragging");
      var rect = card.getBoundingClientRect();
      var offsetX = e.clientX - rect.left;
      var offsetY = e.clientY - rect.top;

      function onMove(ev) {
        var x = ev.clientX - offsetX;
        var y = ev.clientY - offsetY;
        x = Math.max(8, Math.min(x, window.innerWidth - card.offsetWidth - 8));
        y = Math.max(8, Math.min(y, window.innerHeight - card.offsetHeight - 8));
        card.style.left = x + "px";
        card.style.top = y + "px";
        card.style.transform = "none";
      }

      function onUp() {
        card.classList.remove("is-dragging");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  function openPolishFloatCard(rect) {
    var sel = activeSelection();
    if (!sel || !rect) return;

    closePolishFloatCard();
    hideSelectionButton();
    selectionSnapshot = { start: sel.start, end: sel.end, text: sel.text };

    var cardW = 360;
    var cardH = 320;
    var top = rect.bottom + 8;
    var left = rect.left;
    if (left + cardW > window.innerWidth - 12) left = window.innerWidth - cardW - 12;
    if (left < 12) left = 12;
    if (top + cardH > window.innerHeight - 12) top = rect.top - cardH - 8;
    if (top < 12) top = 12;

    var card = document.createElement("div");
    card.className = "polish-float-card";
    card.style.top = top + "px";
    card.style.left = left + "px";
    card.innerHTML =
      "<div class=\"card-head\">" +
        "<span class=\"card-drag\" title=\"拖动\">⠿</span>" +
        "<span class=\"card-title\">润色</span>" +
        "<button type=\"button\" class=\"card-close\" title=\"关闭\">✕</button>" +
      "</div>" +
      "<div class=\"card-body\">" +
        "<div class=\"field\"><span class=\"field-label\">选中内容</span>" +
          "<div class=\"selected-preview polish-card-preview\"></div></div>" +
        "<div class=\"field\"><span class=\"field-label\">润色要求</span>" +
          "<input type=\"text\" class=\"query-input polish-card-query\" placeholder=\"留空则默认：润色下面这段文字\" /></div>" +
        "<button type=\"button\" class=\"btn-generate polish-card-generate\">生成建议</button>" +
        "<div class=\"card-status polish-card-status\"></div>" +
        "<div class=\"result-block polish-card-result\">" +
          "<div class=\"field\"><span class=\"field-label\">意见</span>" +
            "<div class=\"advice-text polish-card-advice\"></div></div>" +
          "<div class=\"field\"><span class=\"field-label\">建议润色结果（可编辑）</span>" +
            "<textarea class=\"result-textarea polish-card-edited\"></textarea></div>" +
        "</div>" +
      "</div>" +
      "<div class=\"card-actions\">" +
        "<button type=\"button\" class=\"primary polish-card-apply\" disabled>一键应用</button>" +
        "<button type=\"button\" class=\"polish-card-cancel\">关闭</button>" +
      "</div>";

    document.body.appendChild(card);
    polishFloatCard = card;

    card.querySelector(".polish-card-preview").textContent = selectionSnapshot.text;

    setupPolishCardDrag(card, card.querySelector(".card-head"));

    card.querySelector(".card-close").addEventListener("click", closePolishFloatCard);
    card.querySelector(".polish-card-cancel").addEventListener("click", closePolishFloatCard);
    card.querySelector(".polish-card-generate").addEventListener("click", submitPolishFloatCard);
    card.querySelector(".polish-card-apply").addEventListener("click", applyPolishFloatCard);

    var queryInput = card.querySelector(".polish-card-query");
    queryInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") { e.preventDefault(); submitPolishFloatCard(); }
    });
    card.querySelector(".polish-card-edited").addEventListener("input", function() {
      card.querySelector(".polish-card-apply").disabled = !(this.value.trim());
    });

    queryInput.focus();
    card.addEventListener("mousedown", function(e) { e.stopPropagation(); });
  }

  function submitPolishFloatCard() {
    var sel = activeSelection();
    if (!polishFloatCard || !sel) return;
    var queryInput = polishFloatCard.querySelector(".polish-card-query");
    var statusEl = polishFloatCard.querySelector(".polish-card-status");
    var resultBlock = polishFloatCard.querySelector(".polish-card-result");
    var adviceEl = polishFloatCard.querySelector(".polish-card-advice");
    var editedEl = polishFloatCard.querySelector(".polish-card-edited");
    var applyBtn = polishFloatCard.querySelector(".polish-card-apply");
    var genBtn = polishFloatCard.querySelector(".polish-card-generate");
    var query = (queryInput.value || "").trim();

    genBtn.disabled = true;
    applyBtn.disabled = true;
    resultBlock.classList.remove("visible");
    statusEl.textContent = "正在请求 AI 润色…";

    api("/api/projects/" + projectId + "/polish", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        target_file: currentFile,
        query: query,
        selected_text: sel.text
      })
    }).then(function(result) {
      polishResult = result;
      var advice = [];
      if (result.problem_zh) advice.push(result.problem_zh);
      if (result.advice_zh) advice.push(result.advice_zh);
      adviceEl.textContent = advice.length ? advice.join("\n\n") : "（无说明）";
      editedEl.value = result.polished_text || "";
      resultBlock.classList.add("visible");
      applyBtn.disabled = !(editedEl.value.trim());
      statusEl.textContent = "润色建议已生成，可编辑后一键应用";
      genBtn.disabled = false;
    }).catch(function(e) {
      statusEl.textContent = "润色失败: " + e.message;
      genBtn.disabled = false;
    });
  }

  function applyPolishFloatCard() {
    var sel = activeSelection();
    if (!polishFloatCard || !sel) return;
    var editedEl = polishFloatCard.querySelector(".polish-card-edited");
    var polished = (editedEl.value || "").trim();
    if (!polished) return;

    var ed = document.getElementById("codeEditor");
    ed.value = ed.value.substring(0, sel.start) + polished + ed.value.substring(sel.end);
    currentContent = ed.value;
    saveFile(currentFile, currentContent).then(function() {
      polishFloatCard.querySelector(".polish-card-status").textContent = "已应用润色";
      showSaveStatus("已保存");
      setTimeout(closePolishFloatCard, 600);
      clearSelectionRange();
    }).catch(function() {
      polishFloatCard.querySelector(".polish-card-status").textContent = "已替换文本，但自动保存失败，请 Ctrl+S";
    });
  }

  function positionSelectionButton() {
    var start = editor.selectionStart;
    var end = editor.selectionEnd;
    if (start === end) {
      hideSelectionButton();
      if (!polishFloatCard) clearSelectionRange();
      return;
    }
    var selText = editor.value.substring(start, end).trim();
    if (!selText) {
      hideSelectionButton();
      if (!polishFloatCard) clearSelectionRange();
      return;
    }

    selectionRange = { start: start, end: end, text: selText };
    selBtn.dataset.selectedText = selText;

    var box = getSelectionMirrorBox(editor, start, end);
    if (!box) return;

    var wrap = document.querySelector(".editor-wrap");
    var btnW = 72;
    var btnH = 28;
    var top = box.wrapBottom + 6;
    var left = box.wrapLeft;

    if (left + btnW > wrap.clientWidth - 8) left = box.wrapRight - btnW;
    if (top + btnH > wrap.clientHeight - 8) top = box.wrapTop - btnH - 6;
    top = Math.max(4, top);
    left = Math.max(4, Math.min(left, wrap.clientWidth - btnW - 4));

    selBtn.style.top = top + "px";
    selBtn.style.left = left + "px";
    selBtn.style.display = "block";
  }

  editor.addEventListener("mouseup", positionSelectionButton);
  editor.addEventListener("keyup", function(e) {
    if (e.key === "Escape") {
      hideSelectionButton();
      if (polishFloatCard) closePolishFloatCard();
      else clearSelectionRange();
    }
    else if (e.shiftKey || e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === "ArrowUp" || e.key === "ArrowDown") {
      positionSelectionButton();
    }
  });
  editor.addEventListener("scroll", function() {
    if (selBtn.style.display === "block") positionSelectionButton();
  });
  document.addEventListener("mousedown", function(e) {
    if (editor.contains(e.target) || selBtn.contains(e.target)) return;
    if (polishFloatCard && polishFloatCard.contains(e.target)) return;
    hideSelectionButton();
    if (!polishFloatCard) clearSelectionRange();
  });

  selBtn.addEventListener("mousedown", function(e) {
    e.preventDefault();
    e.stopPropagation();
  });

  selBtn.addEventListener("click", function(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!selectionRange) return;
    var box = getSelectionMirrorBox(editor, selectionRange.start, selectionRange.end);
    if (!box) return;
    openPolishFloatCard({
      top: box.viewportTop,
      left: box.viewportLeft,
      right: box.viewportRight,
      bottom: box.viewportBottom
    });
  });

  window.hidePolishPanel = function() {
    document.getElementById("polishOverlay").style.display = "none";
    document.getElementById("polishSlide").classList.remove("open");
  };

  window.runPolish = function() {
    var file = document.getElementById("polishFile").value || currentFile;
    var query = document.getElementById("polishQuery").value.trim();
    if (!query) {
      document.getElementById("polishStatus").textContent = "请输入润色需求";
      return;
    }
    var btn = document.getElementById("polishBtn"); btn.disabled = true; btn.textContent = "生成中...";
    document.getElementById("polishResult").style.display = "none";
    document.getElementById("polishStatus").textContent = "正在请求 AI 润色...";
    api("/api/projects/" + projectId + "/polish", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_file: file, query: query, selected_text: ""})
    }).then(function(result) {
      document.getElementById("polishStatus").textContent = "润色建议已生成";
      polishResult = result;
      var advice = [];
      if (result.problem_zh) advice.push(result.problem_zh);
      if (result.advice_zh) advice.push(result.advice_zh);
      document.getElementById("polishProblem").textContent = advice.length ? advice.join("\n\n") : "（无说明）";
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
    if (orig && ed.value.includes(orig)) {
      ed.value = ed.value.replace(orig, polished);
      currentContent = ed.value;
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
      if (pdfDocCache) rerenderPdfZoom();
    }
  });


  // --- Full document polish ---
  window.fullDocumentPolish = function() {
    closePolishFloatCard();
    showPolishPanel();
    document.getElementById("polishQuery").value = "";
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
