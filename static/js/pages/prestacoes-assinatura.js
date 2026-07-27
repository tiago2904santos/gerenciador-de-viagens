(function () {
  "use strict";

  const app = document.getElementById("asgn-app");
  if (!app) return;

  const pdfUrl = app.dataset.pdfUrl || "";
  const nomePadrao = app.dataset.nome || "";

  const canvas = document.getElementById("asgn-canvas");
  const stage = document.getElementById("asgn-stage");
  const viewer = document.getElementById("asgn-viewer");
  const drag = document.getElementById("asgn-drag");
  const dragImg = document.getElementById("asgn-drag-img");
  const resizeHandle = document.getElementById("asgn-resize");
  const pageLabel = document.getElementById("asgn-page-label");
  const btnPrev = document.getElementById("asgn-prev");
  const btnNext = document.getElementById("asgn-next");
  const btnSubmit = document.getElementById("asgn-submit");
  const hint = document.getElementById("asgn-hint");

  const fPng = document.getElementById("f-png");
  const fModo = document.getElementById("f-modo");
  const fFonte = document.getElementById("f-fonte");
  const fPagina = document.getElementById("f-pagina");
  const fX = document.getElementById("f-x");
  const fY = document.getElementById("f-y");
  const fW = document.getElementById("f-w");
  const fH = document.getElementById("f-h");

  // Builder (bottom-sheet)
  const sheet = document.getElementById("asgn-sheet");
  const openBuilder = document.getElementById("asgn-open-builder");
  const sheetCancel = document.getElementById("asgn-sheet-cancel");
  const sheetApply = document.getElementById("asgn-sheet-apply");
  const sheetBackdrop = document.getElementById("asgn-sheet-backdrop");
  const tabs = Array.prototype.slice.call(document.querySelectorAll(".asgn-tab"));
  const panes = Array.prototype.slice.call(document.querySelectorAll(".asgn-tabpane"));
  const nameInput = document.getElementById("asgn-name-input");
  const fontChips = Array.prototype.slice.call(document.querySelectorAll(".asgn-fontchip"));
  const drawCanvas = document.getElementById("asgn-draw");
  const drawClear = document.getElementById("asgn-draw-clear");

  let pdfDoc = null;
  let currentPage = 1;
  let totalPages = 1;
  let signatureReady = false;
  let signatureAspect = 4; // largura/altura do PNG
  let pendingPng = null; // dataURL preparado no builder, ainda não aplicado
  let pendingModo = "";
  let pendingFonte = "";

  // ── PDF.js ─────────────────────────────────────────────────────
  function renderPage(num) {
    if (!pdfDoc) return;
    pdfDoc.getPage(num).then(function (page) {
      const dpr = window.devicePixelRatio || 1;
      const containerW = viewer.clientWidth || 320;
      const base = page.getViewport({ scale: 1 });
      const scale = containerW / base.width;
      const vp = page.getViewport({ scale: scale });
      canvas.width = Math.floor(vp.width * dpr);
      canvas.height = Math.floor(vp.height * dpr);
      canvas.style.width = vp.width + "px";
      canvas.style.height = vp.height + "px";
      stage.style.width = vp.width + "px";
      stage.style.height = vp.height + "px";
      const ctx = canvas.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      page.render({ canvasContext: ctx, viewport: vp });
      currentPage = num;
      fPagina.value = String(num - 1);
      if (pageLabel) pageLabel.textContent = num + " / " + totalPages;
      btnPrev.disabled = num <= 1;
      btnNext.disabled = num >= totalPages;
    });
  }

  function loadPdf() {
    if (typeof pdfjsLib === "undefined") return;
    if (app.dataset.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = app.dataset.workerSrc;
    }
    pdfjsLib
      .getDocument({ url: pdfUrl, withCredentials: true })
      .promise.then(function (doc) {
        pdfDoc = doc;
        totalPages = doc.numPages;
        renderPage(1);
      })
      .catch(function () {
        if (hint) hint.textContent = "Não foi possível carregar o documento. Recarregue a página.";
      });
  }

  btnPrev.addEventListener("click", function () {
    if (currentPage > 1) renderPage(currentPage - 1);
  });
  btnNext.addEventListener("click", function () {
    if (currentPage < totalPages) renderPage(currentPage + 1);
  });
  window.addEventListener("resize", debounce(function () {
    if (pdfDoc) renderPage(currentPage);
  }, 200));

  // ── Builder: abas ──────────────────────────────────────────────
  function precarregarFontes() {
    if (!document.fonts || !document.fonts.load) return;
    fontChips.forEach(function (chip) {
      document.fonts.load("64px '" + familyName(chip.dataset.family) + "'");
    });
  }
  precarregarFontes();

  function showSheet(show) {
    sheet.hidden = !show;
    document.body.style.overflow = show ? "hidden" : "";
  }
  openBuilder.addEventListener("click", function () { showSheet(true); resizeDrawCanvas(); });
  sheetCancel.addEventListener("click", function () { showSheet(false); });
  sheetBackdrop.addEventListener("click", function () { showSheet(false); });

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      const target = tab.dataset.tab;
      tabs.forEach(function (t) { t.classList.toggle("is-active", t === tab); });
      panes.forEach(function (p) { p.hidden = p.dataset.pane !== target; });
      if (target === "desenho") resizeDrawCanvas();
      updateApplyState();
    });
  });

  // ── Builder: fonte ─────────────────────────────────────────────
  let chipSelecionado = null;

  function nomeAtual() {
    return (nameInput.value || nomePadrao || "Assinatura").trim() || "Assinatura";
  }

  function atualizarChips() {
    fontChips.forEach(function (chip) { chip.textContent = nomeAtual(); });
  }
  nameInput.addEventListener("input", function () {
    atualizarChips();
    if (chipSelecionado) prepararDaFonte(chipSelecionado);
  });

  fontChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      fontChips.forEach(function (c) { c.classList.toggle("is-selected", c === chip); });
      chipSelecionado = chip;
      prepararDaFonte(chip);
    });
  });

  function familyName(family) {
    const m = (family || "").match(/'([^']+)'/);
    return m ? m[1] : (family || "sans-serif");
  }

  function prepararDaFonte(chip) {
    const family = chip.dataset.family;
    const fam = familyName(family);
    const texto = nomeAtual();
    const render = function () {
      const png = textoParaPng(texto, family);
      pendingPng = png.dataUrl;
      pendingModo = "fonte";
      pendingFonte = chip.dataset.key || fam;
      signatureAspect = png.aspect;
      updateApplyState();
    };
    if (document.fonts && document.fonts.load) {
      document.fonts.load("64px '" + fam + "'").then(render, render);
    } else {
      render();
    }
  }

  function textoParaPng(texto, family) {
    const dpr = 2;
    const fontPx = 96;
    const measure = document.createElement("canvas").getContext("2d");
    measure.font = fontPx + "px " + family;
    const w = Math.max(40, Math.ceil(measure.measureText(texto).width)) + 40;
    const h = Math.ceil(fontPx * 1.6);
    const c = document.createElement("canvas");
    c.width = w * dpr;
    c.height = h * dpr;
    const ctx = c.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.font = fontPx + "px " + family;
    ctx.fillStyle = "#0b1f33";
    ctx.textBaseline = "middle";
    ctx.fillText(texto, 20, h / 2);
    return trimCanvas(c);
  }

  // ── Builder: desenho ───────────────────────────────────────────
  let drawing = false;
  let drawDirty = false;
  let drawCtx = null;
  let lastPt = null;

  function resizeDrawCanvas() {
    if (!drawCanvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = drawCanvas.getBoundingClientRect();
    const w = rect.width || drawCanvas.parentElement.clientWidth || 300;
    const h = 180;
    drawCanvas.width = w * dpr;
    drawCanvas.height = h * dpr;
    drawCanvas.style.height = h + "px";
    drawCtx = drawCanvas.getContext("2d");
    drawCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawCtx.lineWidth = 2.5;
    drawCtx.lineCap = "round";
    drawCtx.lineJoin = "round";
    drawCtx.strokeStyle = "#0b1f33";
    drawDirty = false;
  }

  function drawPos(e) {
    const rect = drawCanvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - rect.left, y: t.clientY - rect.top };
  }
  function drawStart(e) {
    e.preventDefault();
    drawing = true;
    lastPt = drawPos(e);
  }
  function drawMove(e) {
    if (!drawing) return;
    e.preventDefault();
    const p = drawPos(e);
    drawCtx.beginPath();
    drawCtx.moveTo(lastPt.x, lastPt.y);
    drawCtx.lineTo(p.x, p.y);
    drawCtx.stroke();
    lastPt = p;
    drawDirty = true;
  }
  function drawEnd() {
    if (!drawing) return;
    drawing = false;
    if (drawDirty) prepararDoDesenho();
  }
  if (drawCanvas) {
    drawCanvas.addEventListener("mousedown", drawStart);
    drawCanvas.addEventListener("mousemove", drawMove);
    window.addEventListener("mouseup", drawEnd);
    drawCanvas.addEventListener("touchstart", drawStart, { passive: false });
    drawCanvas.addEventListener("touchmove", drawMove, { passive: false });
    drawCanvas.addEventListener("touchend", drawEnd);
    drawClear.addEventListener("click", function () {
      resizeDrawCanvas();
      pendingPng = null;
      pendingModo = "";
      updateApplyState();
    });
  }

  function prepararDoDesenho() {
    const png = trimCanvas(drawCanvas);
    pendingPng = png.dataUrl;
    pendingModo = "desenho";
    pendingFonte = "";
    signatureAspect = png.aspect;
    updateApplyState();
  }

  function updateApplyState() {
    sheetApply.disabled = !pendingPng;
  }

  // ── Aplicar assinatura (do builder para o documento) ───────────
  sheetApply.addEventListener("click", function () {
    if (!pendingPng) return;
    dragImg.src = pendingPng;
    fPng.value = pendingPng;
    fModo.value = pendingModo;
    fFonte.value = pendingFonte;
    signatureReady = true;
    showSheet(false);
    posicionarCaixaInicial();
    btnSubmit.disabled = false;
    if (hint) hint.textContent = "Arraste a assinatura para a posição correta e toque em Enviar.";
  });

  function posicionarCaixaInicial() {
    const sw = stage.clientWidth || 300;
    const sh = stage.clientHeight || 400;
    const w = Math.min(sw * 0.42, 220);
    const h = w / signatureAspect;
    drag.hidden = false;
    setBox((sw - w) / 2, sh * 0.7, w, h);
  }

  function setBox(left, top, w, h) {
    const sw = stage.clientWidth;
    const sh = stage.clientHeight;
    left = clamp(left, 0, Math.max(0, sw - w));
    top = clamp(top, 0, Math.max(0, sh - h));
    drag.style.left = left + "px";
    drag.style.top = top + "px";
    drag.style.width = w + "px";
    drag.style.height = h + "px";
  }

  // ── Drag & resize da caixa ─────────────────────────────────────
  let mode = null; // 'move' | 'resize'
  let start = null;

  function pointer(e) {
    const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX, y: t.clientY };
  }
  function onDown(e, m) {
    if (drag.hidden) return;
    e.preventDefault();
    mode = m;
    const p = pointer(e);
    start = {
      px: p.x,
      py: p.y,
      left: drag.offsetLeft,
      top: drag.offsetTop,
      w: drag.offsetWidth,
      h: drag.offsetHeight,
    };
  }
  function onMove(e) {
    if (!mode) return;
    e.preventDefault();
    const p = pointer(e);
    const dx = p.x - start.px;
    const dy = p.y - start.py;
    if (mode === "move") {
      setBox(start.left + dx, start.top + dy, start.w, start.h);
    } else {
      const w = clamp(start.w + dx, 60, stage.clientWidth);
      setBox(start.left, start.top, w, w / signatureAspect);
    }
  }
  function onUp() { mode = null; start = null; }

  drag.addEventListener("mousedown", function (e) {
    if (e.target === resizeHandle) return;
    onDown(e, "move");
  });
  drag.addEventListener("touchstart", function (e) {
    if (e.target === resizeHandle) return;
    onDown(e, "move");
  }, { passive: false });
  resizeHandle.addEventListener("mousedown", function (e) { onDown(e, "resize"); });
  resizeHandle.addEventListener("touchstart", function (e) { onDown(e, "resize"); }, { passive: false });
  window.addEventListener("mousemove", onMove);
  window.addEventListener("touchmove", onMove, { passive: false });
  window.addEventListener("mouseup", onUp);
  window.addEventListener("touchend", onUp);

  // ── Submit ─────────────────────────────────────────────────────
  document.getElementById("asgn-form").addEventListener("submit", function (e) {
    if (!signatureReady || drag.hidden) {
      e.preventDefault();
      if (hint) hint.textContent = "Crie e posicione sua assinatura antes de enviar.";
      return;
    }
    const cw = canvas.clientWidth || stage.clientWidth;
    const ch = canvas.clientHeight || stage.clientHeight;
    fX.value = clamp(drag.offsetLeft / cw, 0, 1).toFixed(5);
    fY.value = clamp(drag.offsetTop / ch, 0, 1).toFixed(5);
    fW.value = clamp(drag.offsetWidth / cw, 0, 1).toFixed(5);
    fH.value = clamp(drag.offsetHeight / ch, 0, 1).toFixed(5);
    btnSubmit.disabled = true;
    btnSubmit.textContent = "Enviando…";
  });

  // ── Utils ──────────────────────────────────────────────────────
  function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

  function debounce(fn, ms) {
    let t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, ms);
    };
  }

  function trimCanvas(src) {
    const ctx = src.getContext("2d");
    const w = src.width;
    const h = src.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    let top = h, left = w, right = 0, bottom = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        if (data[(y * w + x) * 4 + 3] > 8) {
          if (x < left) left = x;
          if (x > right) right = x;
          if (y < top) top = y;
          if (y > bottom) bottom = y;
        }
      }
    }
    if (right < left || bottom < top) {
      return { dataUrl: src.toDataURL("image/png"), aspect: w / h };
    }
    const pad = 6;
    left = Math.max(0, left - pad);
    top = Math.max(0, top - pad);
    right = Math.min(w - 1, right + pad);
    bottom = Math.min(h - 1, bottom + pad);
    const tw = right - left + 1;
    const th = bottom - top + 1;
    const out = document.createElement("canvas");
    out.width = tw;
    out.height = th;
    out.getContext("2d").drawImage(src, left, top, tw, th, 0, 0, tw, th);
    return { dataUrl: out.toDataURL("image/png"), aspect: tw / th };
  }

  // ── Init ───────────────────────────────────────────────────────
  atualizarChips();
  loadPdf();
})();
