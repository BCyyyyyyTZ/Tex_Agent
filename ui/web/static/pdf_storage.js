/**
 * 上传 PDF 至服务器 storage/pdfs，并展示列表与下载链
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

  function formatSize(n) {
    if (n == null || n < 0) return "—";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function setStatus(el, text, isErr) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "pdf-panel-status" + (isErr ? " pdf-panel-status--err" : "");
  }

  function downloadUrl(name) {
    return API + "storage/pdfs/" + encodeURIComponent(name) + "/raw";
  }

  function loadList(ul, status) {
    setStatus(status, "加载中…", false);
    return fetch(API + "storage/pdfs", { method: "GET" })
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (d) {
        var files = (d && d.files) || [];
        if (!ul) return;
        ul.innerHTML = "";
        if (files.length === 0) {
          var li0 = document.createElement("li");
          li0.className = "pdf-list-empty";
          li0.textContent = "尚无上传，请选择 PDF 后上传。";
          ul.appendChild(li0);
          setStatus(status, "", false);
          return;
        }
        files.forEach(function (f) {
          var li = document.createElement("li");
          li.className = "pdf-list-item";
          var a = document.createElement("a");
          a.href = downloadUrl(f.name);
          a.textContent = f.name;
          a.setAttribute("download", "");
          a.className = "pdf-list-link";
          a.target = "_blank";
          a.rel = "noopener noreferrer";
          var meta = document.createElement("span");
          meta.className = "pdf-list-meta";
          meta.textContent = formatSize(f.size) + " · " + (f.modified || "");
          li.appendChild(a);
          li.appendChild(meta);
          ul.appendChild(li);
        });
        setStatus(status, "共 " + files.length + " 个文件（存于项目 storage/pdfs/）", false);
      })
      .catch(function (e) {
        setStatus(status, (e && e.message) || String(e), true);
      });
  }

  function init() {
    var form = document.getElementById("pdf-upload-form");
    var input = document.getElementById("pdf-file");
    var ul = document.getElementById("pdf-list");
    var status = document.getElementById("pdf-panel-status");
    if (!form || !input || !ul) return;

    loadList(ul, status);

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = input.files && input.files[0];
      if (!f) {
        setStatus(status, "请选择 PDF 文件", true);
        return;
      }
      if (!/\.pdf$/i.test(f.name)) {
        setStatus(status, "仅支持 .pdf 扩展名", true);
        return;
      }
      setStatus(status, "上传中…", false);
      var fd = new FormData();
      fd.append("file", f, f.name);
      fetch(API + "storage/pdfs", {
        method: "POST",
        body: fd,
      })
        .then(function (r) {
          if (!r.ok) {
            return r.json().then(function (d) {
              var de = d.detail;
              if (typeof de === "string") throw new Error(de);
              throw new Error(r.statusText);
            });
          }
          return r.json();
        })
        .then(function () {
          input.value = "";
          return loadList(ul, status);
        })
        .catch(function (e) {
          setStatus(status, (e && e.message) || String(e), true);
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
