(function () {
  "use strict";

  var API = (function () {
    try {
      return new URL("/api/", window.location.origin + "/").href;
    } catch (_e) {
      return "/api/";
    }
  })();

  function setStatus(el, text, isErr) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "asset-panel-status" + (isErr ? " asset-panel-status--err" : "");
  }

  function wirePendingFileLabel(inputEl, labelEl, emptyText) {
    if (!inputEl || !labelEl) return;
    function sync() {
      var f = inputEl.files && inputEl.files[0];
      labelEl.textContent = f ? "已选：" + f.name : emptyText || "";
      labelEl.classList.toggle("file-pending--active", !!f);
    }
    inputEl.addEventListener("change", sync);
    sync();
  }

  function safeJsonParse(raw) {
    var text = (raw || "").trim();
    if (!text) return {};
    var obj = JSON.parse(text);
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      throw new Error("metadata JSON 必须是对象");
    }
    return obj;
  }

  function esc(v) {
    return String(v == null ? "" : v)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function previewText(v, maxLen) {
    var s = String(v == null ? "" : v);
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen) + "...";
  }

  function renderEmpty(ul, text) {
    if (!ul) return;
    ul.innerHTML = "";
    var li = document.createElement("li");
    li.className = "asset-list-empty";
    li.textContent = text;
    ul.appendChild(li);
  }

  function renderQueryHits(ul, hits) {
    if (!ul) return;
    ul.innerHTML = "";
    if (!Array.isArray(hits) || hits.length === 0) {
      renderEmpty(ul, "暂无命中结果。");
      return;
    }
    hits.forEach(function (hit, idx) {
      var li = document.createElement("li");
      li.className = "asset-list-item";
      var source = hit && hit.source ? String(hit.source) : "未知来源";
      var score = hit && typeof hit.score === "number" ? hit.score.toFixed(4) : "—";
      var metaText = "";
      try {
        metaText = JSON.stringify((hit && hit.metadata) || {}, null, 2);
      } catch (_e) {
        metaText = "{}";
      }
      li.innerHTML =
        '<div class="rag-item-title">#' +
        (idx + 1) +
        " | source: " +
        esc(source) +
        " | score: " +
        esc(score) +
        "</div>" +
        '<div class="rag-item-meta">metadata: ' +
        esc(metaText) +
        "</div>" +
        '<div class="rag-item-content">' +
        esc(previewText(hit && hit.content ? hit.content : "", 600)) +
        "</div>";
      ul.appendChild(li);
    });
  }

  function renderRecords(ul, items, onDelete) {
    if (!ul) return;
    ul.innerHTML = "";
    if (!Array.isArray(items) || items.length === 0) {
      renderEmpty(ul, "暂无符合条件的记录。");
      return;
    }
    items.forEach(function (rec) {
      var li = document.createElement("li");
      li.className = "asset-list-item";
      var metaText = "";
      try {
        metaText = JSON.stringify((rec && rec.metadata) || {}, null, 2);
      } catch (_e) {
        metaText = "{}";
      }
      var doc = rec && rec.document ? String(rec.document) : "";
      li.innerHTML =
        '<div class="rag-item-title">id: ' +
        esc(rec && rec.id ? rec.id : "") +
        "</div>" +
        '<div class="rag-item-meta">metadata: ' +
        esc(metaText) +
        "</div>" +
        '<div class="rag-item-content">' +
        esc(previewText(doc, 320)) +
        "</div>" +
        '<div class="rag-item-actions"><button type="button" class="btn-tiny rag-delete-btn">删除</button></div>';
      var btn = li.querySelector(".rag-delete-btn");
      if (btn) {
        btn.addEventListener("click", function () {
          onDelete(rec);
        });
      }
      ul.appendChild(li);
    });
  }

  function init() {
    var uploadForm = document.getElementById("rag-upload-form");
    var ragFile = document.getElementById("rag-file");
    var ragSource = document.getElementById("rag-source");
    var ragMetadataJson = document.getElementById("rag-metadata-json");
    var ragPending = document.getElementById("rag-pending-name");
    var uploadStatus = document.getElementById("rag-upload-status");

    var queryForm = document.getElementById("rag-query-form");
    var queryMode = document.getElementById("rag-query-mode");
    var queryInput = document.getElementById("rag-query-input");
    var topKInput = document.getElementById("rag-top-k");
    var metaKeyInput = document.getElementById("rag-meta-key");
    var metaValueInput = document.getElementById("rag-meta-value");
    var recordLimitInput = document.getElementById("rag-record-limit");
    var queryStatus = document.getElementById("rag-query-status");
    var resultList = document.getElementById("rag-result-list");
    var queryTextWrap = document.getElementById("rag-query-text-wrap");
    var topKWrap = document.getElementById("rag-top-k-wrap");
    var metaKeyWrap = document.getElementById("rag-meta-key-wrap");
    var metaValueWrap = document.getElementById("rag-meta-value-wrap");
    var limitWrap = document.getElementById("rag-record-limit-wrap");

    if (!uploadForm || !queryForm || !queryMode) return;

    wirePendingFileLabel(ragFile, ragPending, "");
    renderEmpty(resultList, "请选择查询方式并执行查询。");

    function syncModeUI() {
      var mode = queryMode.value || "semantic";
      var semantic = mode === "semantic";
      if (queryTextWrap) queryTextWrap.style.display = semantic ? "" : "none";
      if (topKWrap) topKWrap.style.display = semantic ? "" : "none";
      if (metaKeyWrap) metaKeyWrap.style.display = semantic ? "none" : "";
      if (metaValueWrap) metaValueWrap.style.display = semantic ? "none" : "";
      if (limitWrap) limitWrap.style.display = semantic ? "none" : "";
      if (semantic) {
        setStatus(queryStatus, "语义查询：输入文本并设置 Top-K。", false);
      } else {
        setStatus(queryStatus, "Metadata 查询：输入字段名/字段值筛选。", false);
      }
    }

    function fetchRecordsByFilter() {
      var key = (metaKeyInput.value || "").trim();
      var value = (metaValueInput.value || "").trim();
      var limitVal = Number(recordLimitInput.value || 20);
      if (!Number.isFinite(limitVal)) limitVal = 20;
      limitVal = Math.max(1, Math.min(50, Math.floor(limitVal)));
      recordLimitInput.value = String(limitVal);

      setStatus(queryStatus, "查询中...", false);
      var params = new URLSearchParams();
      params.set("offset", "0");
      params.set("limit", String(limitVal));
      params.set("include_document", "true");
      if (key) params.set("metadata_key", key);
      if (value) params.set("metadata_value", value);

      return fetch(API + "rag/records?" + params.toString(), { method: "GET" })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (d) {
              throw new Error((d && d.detail) || r.statusText);
            });
          }
          return r.json();
        })
        .then(function (data) {
          var items = (data && data.items) || [];
          renderRecords(resultList, items, function (rec) {
            if (!rec || !rec.id) return;
            setStatus(queryStatus, "删除中...", false);
            fetch(API + "rag/records/" + encodeURIComponent(rec.id), {
              method: "DELETE",
            })
              .then(function (r) {
                if (!r.ok) {
                  return r.json().then(function (d) {
                    throw new Error((d && d.detail) || r.statusText);
                  });
                }
                return r.json();
              })
              .then(function (res) {
                setStatus(
                  queryStatus,
                  "已删除 1 条记录，当前总数 " + ((res && res.total) || 0),
                  false
                );
                return fetchRecordsByFilter();
              })
              .catch(function (e) {
                setStatus(queryStatus, (e && e.message) || String(e), true);
              });
          });
          var txt = "共 " + ((data && data.total) || 0) + " 条";
          if (data && data.has_next) txt += "（仅显示当前页）";
          setStatus(queryStatus, txt, false);
        })
        .catch(function (e) {
          setStatus(queryStatus, (e && e.message) || String(e), true);
        });
    }

    uploadForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = ragFile && ragFile.files && ragFile.files[0];
      if (!f) {
        setStatus(uploadStatus, "请先选择文件", true);
        return;
      }
      var mdObj;
      try {
        mdObj = safeJsonParse(ragMetadataJson && ragMetadataJson.value);
      } catch (e) {
        setStatus(uploadStatus, (e && e.message) || String(e), true);
        return;
      }
      var source = (ragSource && ragSource.value || "").trim();
      setStatus(uploadStatus, "上传并入库中...", false);

      var fd = new FormData();
      fd.append("file", f, f.name);
      if (source) fd.append("source", source);
      fd.append("metadata_json", JSON.stringify(mdObj));

      fetch(API + "rag/index-file", { method: "POST", body: fd })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (d) {
              throw new Error((d && d.detail) || r.statusText);
            });
          }
          return r.json();
        })
        .then(function (data) {
          ragFile.value = "";
          try {
            ragFile.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (_e) {
            /* empty */
          }
          setStatus(
            uploadStatus,
            "入库完成：新增 " +
              ((data && data.indexed_chunks) || 0) +
              " 条，库内总计 " +
              ((data && data.total_chunks) || 0) +
              " 条",
            false
          );
          if ((queryMode.value || "semantic") === "metadata") {
            return fetchRecordsByFilter();
          }
          return null;
        })
        .catch(function (e) {
          setStatus(uploadStatus, (e && e.message) || String(e), true);
        });
    });

    queryForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var mode = queryMode.value || "semantic";
      if (mode === "semantic") {
        var q = (queryInput.value || "").trim();
        if (!q) {
          setStatus(queryStatus, "请输入查询文本", true);
          return;
        }
        var topK = Number(topKInput.value || 5);
        if (!Number.isFinite(topK)) topK = 5;
        topK = Math.max(1, Math.min(20, Math.floor(topK)));
        topKInput.value = String(topK);

        setStatus(queryStatus, "检索中...", false);
        fetch(API + "rag/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: q,
            top_k: topK,
          }),
        })
          .then(function (r) {
            if (!r.ok) {
              return r.json().then(function (d) {
                throw new Error((d && d.detail) || r.statusText);
              });
            }
            return r.json();
          })
          .then(function (data) {
            var hits = (data && data.hits) || [];
            renderQueryHits(resultList, hits);
            setStatus(queryStatus, "命中 " + hits.length + " 条", false);
          })
          .catch(function (e) {
            setStatus(queryStatus, (e && e.message) || String(e), true);
            renderEmpty(resultList, "检索失败。");
          });
        return;
      }
      fetchRecordsByFilter();
    });

    queryMode.addEventListener("change", syncModeUI);
    syncModeUI();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
