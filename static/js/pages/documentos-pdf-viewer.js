(function () {
  "use strict";

  const root = document.getElementById("documentos-pdf-viewer");
  if (!root) return;

  const pdfUrl = root.dataset.pdfUrl || "";
  const workerSrc = root.dataset.workerSrc || "";
  const filename = root.dataset.filename || "documento.pdf";
  const canvasWrap = document.getElementById("doc-pdf-canvas-wrap");
  const thumbsWrap = document.getElementById("doc-pdf-thumbs");
  const iframeFb = document.getElementById("doc-pdf-iframe-fallback");
  const errEl = document.getElementById("doc-pdf-error");
  const pageLabel = document.getElementById("doc-pdf-page-label");
  const btnBack = document.getElementById("doc-pdf-back");
  const btnPrev = document.getElementById("doc-pdf-prev");
  const btnNext = document.getElementById("doc-pdf-next");
  const btnPrint = document.getElementById("doc-pdf-print");
  const zoomInput = document.getElementById("doc-pdf-zoom");
  const btnShare = document.getElementById("doc-pdf-copy-share");

  let pdfDoc = null;
  let scale = 1;
  let currentPage = 1;
  const pageCanvases = [];
  const thumbEls = [];

  function showError(msg) {
    if (errEl) {
      errEl.textContent = msg;
      errEl.hidden = false;
    }
  }

  function activateNativeIframe() {
    if (!iframeFb || !pdfUrl) return;
    iframeFb.removeAttribute("hidden");
    if (canvasWrap) canvasWrap.setAttribute("hidden", "hidden");
    iframeFb.src = pdfUrl;
  }

  function scrollToPage(num) {
    const idx = num - 1;
    const cv = pageCanvases[idx];
    if (cv && typeof cv.scrollIntoView === "function") {
      cv.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    thumbEls.forEach(function (el, i) {
      el.classList.toggle("doc-pdf-thumb--active", i === idx);
    });
    currentPage = num;
    if (pageLabel && pdfDoc) {
      pageLabel.textContent = num + " / " + pdfDoc.numPages;
    }
  }

  function renderThumbnails() {
    if (!thumbsWrap || !pdfDoc) return;
    thumbsWrap.innerHTML = "";
    thumbEls.length = 0;
    const n = pdfDoc.numPages;
    const tasks = [];
    for (let i = 1; i <= n; i += 1) {
      tasks.push(
        pdfDoc.getPage(i).then(function (page) {
          const wrap = document.createElement("button");
          wrap.type = "button";
          wrap.className = "doc-pdf-thumb";
          wrap.setAttribute("aria-label", "Página " + i);
          const canvas = document.createElement("canvas");
          const vp = page.getViewport({ scale: 0.2 });
          canvas.width = vp.width;
          canvas.height = vp.height;
          wrap.appendChild(canvas);
          thumbsWrap.appendChild(wrap);
          thumbEls.push(wrap);
          wrap.addEventListener("click", function () {
            scrollToPage(i);
          });
          return page.render({ canvasContext: canvas.getContext("2d"), viewport: vp }).promise;
        }),
      );
    }
    return Promise.all(tasks);
  }

  function renderAllPages() {
    if (!canvasWrap || !pdfDoc) return Promise.resolve();
    canvasWrap.innerHTML = "";
    pageCanvases.length = 0;
    const n = pdfDoc.numPages;
    const tasks = [];
    for (let i = 1; i <= n; i += 1) {
      tasks.push(
        pdfDoc.getPage(i).then(function (page) {
          const canvas = document.createElement("canvas");
          const vp = page.getViewport({ scale: scale });
          canvas.width = vp.width;
          canvas.height = vp.height;
          canvasWrap.appendChild(canvas);
          pageCanvases.push(canvas);
          return page.render({ canvasContext: canvas.getContext("2d"), viewport: vp }).promise;
        }),
      );
    }
    return Promise.all(tasks).then(function () {
      scrollToPage(1);
    });
  }

  function loadPdfJs() {
    if (typeof pdfjsLib === "undefined") {
      activateNativeIframe();
      return;
    }
    if (workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
    }
    const loadingTask = pdfjsLib.getDocument({ url: pdfUrl, withCredentials: true });
    loadingTask.promise
      .then(function (pdf) {
        pdfDoc = pdf;
        return renderThumbnails().then(function () {
          return renderAllPages();
        });
      })
      .catch(function () {
        showError("Não foi possível carregar o PDF com o motor integrado. A usar o visualizador do navegador.");
        activateNativeIframe();
      });
  }

  if (btnBack) {
    btnBack.addEventListener("click", function () {
      if (window.history.length > 1) {
        window.history.back();
      } else {
        window.location.href = "/documentos/";
      }
    });
  }

  if (btnPrev) {
    btnPrev.addEventListener("click", function () {
      if (!pdfDoc) return;
      const next = Math.max(1, currentPage - 1);
      scrollToPage(next);
    });
  }

  if (btnNext) {
    btnNext.addEventListener("click", function () {
      if (!pdfDoc) return;
      const next = Math.min(pdfDoc.numPages, currentPage + 1);
      scrollToPage(next);
    });
  }

  if (btnPrint) {
    btnPrint.addEventListener("click", function () {
      window.print();
    });
  }

  if (zoomInput) {
    zoomInput.addEventListener("input", function () {
      const pct = parseInt(zoomInput.value, 10) || 100;
      scale = pct / 100;
      zoomInput.setAttribute("aria-valuenow", String(pct));
      if (pdfDoc) {
        const keep = currentPage;
        renderAllPages().then(function () {
          const n = pdfDoc ? pdfDoc.numPages : 1;
          scrollToPage(Math.min(Math.max(1, keep), n));
        });
      }
    });
  }

  if (btnShare && btnShare.dataset.shareUrl) {
    btnShare.addEventListener("click", function () {
      const u = btnShare.dataset.shareUrl;
      if (navigator.clipboard && u) {
        navigator.clipboard.writeText(u).then(
          function () {
            btnShare.textContent = "Copiado";
            window.setTimeout(function () {
              btnShare.textContent = "Copiar link temporário";
            }, 2000);
          },
          function () {
            window.prompt("Copie o link:", u);
          },
        );
      }
    });
  }

  loadPdfJs();
})();
