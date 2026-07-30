(function () {
  "use strict";

  var activeDownloads = 0;
  var overlay = null;
  var title = null;
  var detail = null;
  var errorTimer = null;

  function getOverlay() {
    if (overlay) return overlay;
    overlay = document.querySelector("[data-document-loading]");
    if (!overlay) return null;
    title = overlay.querySelector("[data-document-loading-title]");
    detail = overlay.querySelector("[data-document-loading-detail]");
    return overlay;
  }

  function showLoading(copy) {
    var element = getOverlay();
    if (!element) return;
    var message = copy || {};
    window.clearTimeout(errorTimer);
    element.classList.remove("is-error");
    if (title) title.textContent = message.title || "Gerando documento…";
    if (detail) detail.textContent = message.detail || "Você pode continuar navegando.";
    element.hidden = false;
  }

  function hideLoading() {
    if (activeDownloads > 0) return;
    var element = getOverlay();
    if (element) element.hidden = true;
  }

  function showError(message) {
    var element = getOverlay();
    if (!element) return;
    element.classList.add("is-error");
    if (title) title.textContent = "Não foi possível gerar o documento";
    if (detail) detail.textContent = message || "Tente novamente em instantes.";
    element.hidden = false;
    errorTimer = window.setTimeout(function () {
      element.hidden = true;
      element.classList.remove("is-error");
    }, 4000);
  }

  function begin(trigger, copy) {
    activeDownloads += 1;
    if (trigger) {
      trigger.setAttribute("aria-busy", "true");
      trigger.setAttribute("data-document-download-active", "");
    }
    showLoading(copy);
  }

  function finish(trigger) {
    activeDownloads = Math.max(0, activeDownloads - 1);
    if (trigger) {
      trigger.removeAttribute("aria-busy");
      trigger.removeAttribute("data-document-download-active");
    }
    hideLoading();
  }

  function fail(trigger, message) {
    activeDownloads = Math.max(0, activeDownloads - 1);
    if (trigger) {
      trigger.removeAttribute("aria-busy");
      trigger.removeAttribute("data-document-download-active");
    }
    showError(message);
  }

  function filenameFromDisposition(disposition) {
    if (!disposition) return "";
    var encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encoded) {
      try {
        return decodeURIComponent(encoded[1].replace(/^["']|["']$/g, ""));
      } catch (_error) {
        return encoded[1];
      }
    }
    var plain = disposition.match(/filename="?([^";]+)"?/i);
    return plain ? plain[1].trim() : "";
  }

  function fallbackFilename(response, trigger) {
    var explicit = trigger && trigger.getAttribute("download");
    if (explicit) return explicit;
    try {
      var pathname = new URL(response.url, window.location.href).pathname;
      return decodeURIComponent(pathname.split("/").filter(Boolean).pop() || "documento");
    } catch (_error) {
      return "documento";
    }
  }

  function saveBlob(blob, filename) {
    var objectUrl = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename || "documento";
    link.hidden = true;
    link.setAttribute("data-document-download-bypass", "");
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(objectUrl);
    }, 1000);
  }

  function responseIsHtml(response) {
    return (response.headers.get("Content-Type") || "").toLowerCase().includes("text/html");
  }

  function responseIsJson(response) {
    return (response.headers.get("Content-Type") || "").toLowerCase().includes("application/json");
  }

  function wait(milliseconds) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, milliseconds);
    });
  }

  async function waitForGeneration(response, trigger) {
    var data = await response.json();
    while (data.status !== "complete") {
      if (data.status === "error") {
        throw new Error(data.error || "Não foi possível gerar o documento.");
      }
      await wait(data.retry_after_ms || 1000);
      var statusResponse = await window.CV.http.request(data.status_url);
      if (!statusResponse.ok || !responseIsJson(statusResponse)) {
        throw new Error("Não foi possível consultar a geração do documento.");
      }
      data = await statusResponse.json();
    }
    var resultResponse = await window.CV.http.request(data.result_url);
    return consumeResponse(resultResponse, trigger);
  }

  async function consumeResponse(response, trigger) {
    if (response.status === 202 && responseIsJson(response)) {
      return waitForGeneration(response, trigger);
    }
    if (!response.ok) {
      if (responseIsJson(response)) {
        var errorPayload = await response.json();
        throw new Error(errorPayload.error || "O servidor retornou o erro " + response.status + ".");
      }
      throw new Error("O servidor retornou o erro " + response.status + ".");
    }
    if (responseIsHtml(response)) {
      if (response.redirected && response.url) {
        window.location.assign(response.url);
        return false;
      }
      var html = await response.text();
      if (response.url && window.history && window.history.replaceState) {
        window.history.replaceState(null, "", response.url);
      }
      document.open();
      document.write(html);
      document.close();
      return false;
    }
    var filename = filenameFromDisposition(response.headers.get("Content-Disposition"));
    var blob = await response.blob();
    saveBlob(blob, filename || fallbackFilename(response, trigger));
    return true;
  }

  async function downloadLink(trigger) {
    begin(trigger);
    try {
      var response = await window.CV.http.request(trigger.href);
      await consumeResponse(response, trigger);
      finish(trigger);
    } catch (error) {
      fail(trigger, error && error.message);
      document.dispatchEvent(new CustomEvent("cv:document-download-error", {
        detail: { message: error && error.message, url: trigger.href },
      }));
    }
  }

  function formDataWithSubmitter(form, submitter) {
    try {
      return new FormData(form, submitter);
    } catch (_error) {
      var data = new FormData(form);
      if (submitter && submitter.name) data.append(submitter.name, submitter.value);
      return data;
    }
  }

  async function downloadForm(form, submitter) {
    begin(submitter);
    try {
      var response = await window.CV.http.request(form.action || window.location.href, {
        method: (form.method || "post").toUpperCase(),
        body: formDataWithSubmitter(form, submitter),
        form: form,
      });
      await consumeResponse(response, submitter);
      finish(submitter);
    } catch (error) {
      fail(submitter, error && error.message);
      document.dispatchEvent(new CustomEvent("cv:document-download-error", {
        detail: { message: error && error.message, url: form.action },
      }));
    }
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest
      ? event.target.closest("a[download]:not([data-document-download-bypass])")
      : null;
    if (!trigger || trigger.target === "_blank" || trigger.getAttribute("aria-disabled") === "true") return;
    var url = new URL(trigger.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    event.preventDefault();
    downloadLink(trigger);
  });

  document.addEventListener("submit", function (event) {
    var submitter = event.submitter;
    if (!submitter || submitter.name !== "action" || !/^download_/.test(submitter.value || "")) return;
    event.preventDefault();
    downloadForm(event.target, submitter);
  });

  window.CV = window.CV || {};
  window.CV.documentProgress = {
    begin: begin,
    error: fail,
    finish: finish,
  };
}());
