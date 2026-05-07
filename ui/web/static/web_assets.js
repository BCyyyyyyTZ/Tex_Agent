/**
 * storage：pdfs / documents（输入区旁统一上传）+ skills / checklists（右侧）；
 * 已上传的 PDF/文档合并列表在「已上传文件列表」。供 app.js 带上 active_*。
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

  var LS = {
    pdfs: "texagent.sel.pdfs",
    documents: "texagent.sel.documents",
    skills: "texagent.sel.skills",
    checklists: "texagent.sel.checklists",
  };

  function loadSel(key) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return [];
      var a = JSON.parse(raw);
      return Array.isArray(a) ? a.filter(function (x) {
        return typeof x === "string" && x.trim();
      }) : [];
    } catch (_e) {
      return [];
    }
  }

  function saveSel(key, names) {
    try {
      localStorage.setItem(key, JSON.stringify(names));
    } catch (_e) {
      /* ignore */
    }
  }

  function formatSize(n) {
    if (n == null || n < 0) return "—";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function setAssetStatus(el, text, isErr) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "asset-panel-status" + (isErr ? " asset-panel-status--err" : "");
  }

  function setComposerStatus(el, text, isErr) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "composer-upload-status" + (isErr ? " composer-upload-status--err" : "");
  }

  function downloadUrl(cat, name) {
    return API + "storage/" + cat + "/" + encodeURIComponent(name) + "/raw";
  }

  function routePdfsOrDocuments(filename) {
    var n = (filename || "").toLowerCase();
    if (n.endsWith(".pdf")) return "pdfs";
    return "documents";
  }

  function fetchList(cat) {
    return fetch(API + "storage/" + cat, { method: "GET" }).then(function (r) {
      if (!r.ok) throw new Error(r.statusText);
      return r.json();
    });
  }

  function renderSkillChecklistList(cat, ul, files, lsKey) {
    if (!ul) return;
    var selected = loadSel(lsKey);
    var names = {};
    files.forEach(function (f) {
      names[f.name] = true;
    });
    var nextSel = selected.filter(function (n) {
      return names[n];
    });

    ul.innerHTML = "";
    if (files.length === 0) {
      var li0 = document.createElement("li");
      li0.className = "asset-list-empty";
      li0.textContent = "尚无文件，请选择后上传。";
      ul.appendChild(li0);
      saveSel(lsKey, nextSel);
      return;
    }

    files.forEach(function (f) {
      var li = document.createElement("li");
      li.className = "asset-list-item";
      var row = document.createElement("label");
      row.className = "asset-row";
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "asset-cb";
      cb.dataset.cat = cat;
      cb.dataset.name = f.name;
      cb.checked = nextSel.indexOf(f.name) >= 0;
      cb.addEventListener("change", function () {
        var all = loadSel(lsKey);
        var i = all.indexOf(f.name);
        if (cb.checked && i < 0) all.push(f.name);
        if (!cb.checked && i >= 0) all.splice(i, 1);
        saveSel(lsKey, all);
      });
      var link = document.createElement("a");
      link.href = downloadUrl(cat, f.name);
      link.textContent = f.name;
      link.className = "asset-link";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      var meta = document.createElement("span");
      meta.className = "asset-meta";
      meta.textContent = formatSize(f.size) + " · " + (f.modified || "");
      row.appendChild(cb);
      row.appendChild(link);
      li.appendChild(row);
      li.appendChild(meta);
      ul.appendChild(li);
    });
    saveSel(lsKey, nextSel);
  }

  function wirePendingFileLabel(inputEl, labelEl, clearBtn, emptyText) {
    if (!inputEl || !labelEl) return;
    function sync() {
      var f = inputEl.files && inputEl.files[0];
      labelEl.textContent = f ? "已选：" + f.name : emptyText || "";
      labelEl.classList.toggle("file-pending--active", !!f);
      if (clearBtn) {
        clearBtn.style.display = f ? "inline-flex" : "none";
      }
    }
    inputEl.addEventListener("change", sync);
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        inputEl.value = "";
        try {
          inputEl.dispatchEvent(new Event("change", { bubbles: true }));
        } catch (_e) {
          /* empty */
        }
      });
    }
    sync();
  }

  function parseErrorResponse(r) {
    if (!r.ok) {
      return r
        .json()
        .then(function (d) {
          var de = d && d.detail;
          if (typeof de === "string" && de.trim()) throw new Error(de);
          throw new Error(r.statusText || "上传失败");
        })
        .catch(function (e) {
          if (e instanceof Error) throw e;
          throw new Error(r.statusText || "上传失败");
        });
    }
    return r.json();
  }

  function renderGlobalUploadedSummary(ul, status) {
    if (!ul) return;
    return Promise.all([
      fetchList("pdfs"),
      fetchList("documents"),
      fetchList("skills"),
      fetchList("checklists"),
    ])
      .then(function (res) {
        var pdfF = (res[0] && res[0].files) || [];
        var docF = (res[1] && res[1].files) || [];
        var skillF = (res[2] && res[2].files) || [];
        var checkF = (res[3] && res[3].files) || [];

        var merged = []
          .concat(
            pdfF.map(function (f) {
              return {
                cat: "pdfs",
                catLabel: "PDF",
                name: f.name,
                size: f.size,
                modified: f.modified,
              };
            })
          )
          .concat(
            docF.map(function (f) {
              return {
                cat: "documents",
                catLabel: "文档",
                name: f.name,
                size: f.size,
                modified: f.modified,
              };
            })
          )
          .concat(
            skillF.map(function (f) {
              return {
                cat: "skills",
                catLabel: "Skill",
                name: f.name,
                size: f.size,
                modified: f.modified,
              };
            })
          )
          .concat(
            checkF.map(function (f) {
              return {
                cat: "checklists",
                catLabel: "Checklist",
                name: f.name,
                size: f.size,
                modified: f.modified,
              };
            })
          );

        merged.sort(function (a, b) {
          return String(b.modified || "").localeCompare(String(a.modified || ""));
        });

        var selPdf = loadSel(LS.pdfs);
        var selDoc = loadSel(LS.documents);
        var selSkill = loadSel(LS.skills);
        var selCl = loadSel(LS.checklists);

        var namesP = {};
        pdfF.forEach(function (f) {
          namesP[f.name] = true;
        });
        var namesD = {};
        docF.forEach(function (f) {
          namesD[f.name] = true;
        });
        var namesS = {};
        skillF.forEach(function (f) {
          namesS[f.name] = true;
        });
        var namesC = {};
        checkF.forEach(function (f) {
          namesC[f.name] = true;
        });
        saveSel(
          LS.pdfs,
          selPdf.filter(function (n) {
            return namesP[n];
          })
        );
        saveSel(
          LS.documents,
          selDoc.filter(function (n) {
            return namesD[n];
          })
        );
        saveSel(
          LS.skills,
          selSkill.filter(function (n) {
            return namesS[n];
          })
        );
        saveSel(
          LS.checklists,
          selCl.filter(function (n) {
            return namesC[n];
          })
        );
        selPdf = loadSel(LS.pdfs);
        selDoc = loadSel(LS.documents);
        selSkill = loadSel(LS.skills);
        selCl = loadSel(LS.checklists);

        ul.innerHTML = "";
        if (merged.length === 0) {
          var li0 = document.createElement("li");
          li0.className = "asset-list-empty";
          li0.textContent = "暂无已上传文件。可在下方输入区旁或右侧各区块上传。";
          ul.appendChild(li0);
          setAssetStatus(status, "", false);
          return;
        }

        merged.forEach(function (item) {
          var li = document.createElement("li");
          li.className = "asset-list-item";
          var row = document.createElement("label");
          row.className = "asset-row";
          var cb = document.createElement("input");
          cb.type = "checkbox";
          cb.className = "asset-cb";
          var lsKey =
            item.cat === "pdfs"
              ? LS.pdfs
              : item.cat === "documents"
                ? LS.documents
                : item.cat === "skills"
                  ? LS.skills
                  : LS.checklists;
          var curSel =
            item.cat === "pdfs"
              ? selPdf
              : item.cat === "documents"
                ? selDoc
                : item.cat === "skills"
                  ? selSkill
                  : selCl;
          cb.checked = curSel.indexOf(item.name) >= 0;
          cb.addEventListener("change", function () {
            var all = loadSel(lsKey);
            var i = all.indexOf(item.name);
            if (cb.checked && i < 0) all.push(item.name);
            if (!cb.checked && i >= 0) all.splice(i, 1);
            saveSel(lsKey, all);
          });
          var badge = document.createElement("span");
          badge.className = "asset-badge";
          badge.textContent = item.catLabel;
          var link = document.createElement("a");
          link.href = downloadUrl(item.cat, item.name);
          link.textContent = item.name;
          link.className = "asset-link";
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          var meta = document.createElement("span");
          meta.className = "asset-meta";
          meta.textContent = formatSize(item.size) + " · " + (item.modified || "");
          row.appendChild(cb);
          row.appendChild(badge);
          row.appendChild(link);
          li.appendChild(row);
          li.appendChild(meta);
          ul.appendChild(li);
        });
        setAssetStatus(
          status,
          "共 " +
            merged.length +
            " 个文件（PDF / 文档 / Skill / Checklist）；勾选将附加到发送消息",
          false
        );
      })
      .catch(function (e) {
        setAssetStatus(status, (e && e.message) || String(e), true);
      });
  }

  function wireComposerUpload() {
    var input = document.getElementById("composer-file");
    var btn = document.getElementById("composer-upload-btn");
    var status = document.getElementById("composer-upload-status");
    var ul = document.getElementById("uploaded-files-list");
    var ustatus = document.getElementById("uploaded-files-status");
    if (!input || !btn) return;
    function afterUpload() {
      return renderGlobalUploadedSummary(ul, ustatus);
    }
    function doUpload() {
      var f = input.files && input.files[0];
      if (!f) {
        setComposerStatus(status, "请先选择文件", true);
        return;
      }
      var cat = routePdfsOrDocuments(f.name);
      setComposerStatus(status, "上传中…", false);
      var fd = new FormData();
      fd.append("file", f, f.name);
      fetch(API + "storage/" + cat, { method: "POST", body: fd })
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
          try {
            input.dispatchEvent(new Event("change", { bubbles: true }));
          } catch (_e) {
            /* empty */
          }
          setComposerStatus(status, "已上传", false);
          return afterUpload();
        })
        .catch(function (e) {
          setComposerStatus(status, (e && e.message) || String(e), true);
        });
    }
    btn.addEventListener("click", function () {
      doUpload();
    });
  }

  function getWebAssetSelection() {
    return {
      active_pdfs: loadSel(LS.pdfs),
      active_documents: loadSel(LS.documents),
      active_skills: loadSel(LS.skills),
      active_checklists: loadSel(LS.checklists),
    };
  }

  window.getWebAssetSelection = getWebAssetSelection;
  window.refreshWebUploadedList = function () {
    return renderGlobalUploadedSummary(
      document.getElementById("uploaded-files-list"),
      document.getElementById("uploaded-files-status")
    );
  };

  function init() {
    wireComposerUpload();

    wirePendingFileLabel(
      document.getElementById("composer-file"),
      document.getElementById("composer-pending-name"),
      document.getElementById("composer-clear-file-btn"),
      ""
    );
    wirePendingFileLabel(
      document.getElementById("skill-file"),
      document.getElementById("skill-pending-name"),
      document.getElementById("skill-clear-file-btn"),
      ""
    );
    wirePendingFileLabel(
      document.getElementById("checklist-file"),
      document.getElementById("checklist-pending-name"),
      document.getElementById("checklist-clear-file-btn"),
      ""
    );

    var skillForm = document.getElementById("skill-upload-form");
    var skillFile = document.getElementById("skill-file");
    var skillStatus = document.getElementById("skill-panel-status");
    var skillList = document.getElementById("skill-list");
    var skillSubmitBtn = skillForm
      ? skillForm.querySelector('button[type="submit"]')
      : null;
    if (skillForm && skillFile) {
      function doSkillUpload(ev) {
        if (ev) {
          ev.preventDefault();
          ev.stopPropagation();
        }
        var f = skillFile.files && skillFile.files[0];
        if (!f) {
          setAssetStatus(skillStatus, "请选择文件", true);
          return;
        }
        setAssetStatus(skillStatus, "上传中…", false);
        var fd = new FormData();
        fd.append("file", f, f.name);
        fetch(API + "storage/skills", { method: "POST", body: fd })
          .then(parseErrorResponse)
          .then(function () {
            skillFile.value = "";
            try {
              skillFile.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (_e) {
              /* empty */
            }
            return fetchList("skills");
          })
          .then(function (d) {
            var files = (d && d.files) || [];
            renderSkillChecklistList("skills", skillList, files, LS.skills);
            setAssetStatus(skillStatus, "共 " + files.length + " 个", false);
            if (typeof window.refreshWebUploadedList === "function") {
              window.refreshWebUploadedList();
            }
          })
          .catch(function (e) {
            setAssetStatus(skillStatus, (e && e.message) || String(e), true);
          });
      }
      skillForm.addEventListener("submit", doSkillUpload, false);
      if (skillSubmitBtn) {
        skillSubmitBtn.addEventListener("click", doSkillUpload, true);
      }
    }

    var cf = document.getElementById("checklist-upload-form");
    var cfile = document.getElementById("checklist-file");
    var cstatus = document.getElementById("checklist-panel-status");
    var clist = document.getElementById("checklist-list");
    var checklistSubmitBtn = cf ? cf.querySelector('button[type="submit"]') : null;
    if (cf && cfile) {
      function doChecklistUpload(ev) {
        if (ev) {
          ev.preventDefault();
          ev.stopPropagation();
        }
        var f2 = cfile.files && cfile.files[0];
        if (!f2) {
          setAssetStatus(cstatus, "请选择文件", true);
          return;
        }
        setAssetStatus(cstatus, "上传中…", false);
        var fd2 = new FormData();
        fd2.append("file", f2, f2.name);
        fetch(API + "storage/checklists", { method: "POST", body: fd2 })
          .then(parseErrorResponse)
          .then(function () {
            cfile.value = "";
            try {
              cfile.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (_e) {
              /* empty */
            }
            return fetchList("checklists");
          })
          .then(function (d) {
            var files = (d && d.files) || [];
            renderSkillChecklistList("checklists", clist, files, LS.checklists);
            setAssetStatus(cstatus, "共 " + files.length + " 个", false);
            if (typeof window.refreshWebUploadedList === "function") {
              window.refreshWebUploadedList();
            }
          })
          .catch(function (e) {
            setAssetStatus(cstatus, (e && e.message) || String(e), true);
          });
      }
      cf.addEventListener("submit", doChecklistUpload, false);
      if (checklistSubmitBtn) {
        checklistSubmitBtn.addEventListener("click", doChecklistUpload, true);
      }
    }

    return fetchList("skills")
      .then(function (d) {
        renderSkillChecklistList(
          "skills",
          document.getElementById("skill-list"),
          (d && d.files) || [],
          LS.skills
        );
        setAssetStatus(
          document.getElementById("skill-panel-status"),
          "共 " + ((d && d.files) || []).length + " 个",
          false
        );
      })
      .then(function () {
        return fetchList("checklists");
      })
      .then(function (d) {
        renderSkillChecklistList(
          "checklists",
          document.getElementById("checklist-list"),
          (d && d.files) || [],
          LS.checklists
        );
        setAssetStatus(
          document.getElementById("checklist-panel-status"),
          "共 " + ((d && d.files) || []).length + " 个",
          false
        );
      })
      .then(function () {
        return renderGlobalUploadedSummary(
          document.getElementById("uploaded-files-list"),
          document.getElementById("uploaded-files-status")
        );
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, false);
  } else {
    init();
  }
})();
