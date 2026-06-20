(function () {
  function csrfFromForm(form) {
    if (window.CV && window.CV.http && typeof window.CV.http.getCsrfToken === "function") {
      return window.CV.http.getCsrfToken(form);
    }
    var tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return tokenInput ? tokenInput.value : "";
  }

  function setState(form, state) {
    form.dataset.autosaveState = state;
  }

  function buildData(form, source) {
    var data = new FormData();
    var token = csrfFromForm(form);
    if (token) data.append("csrfmiddlewaretoken", token);
    var numero = form.querySelector('[name="numero_solicitacao"]');
    if (numero) data.append("numero_solicitacao", numero.value || "");
    if (source && source.type === "file" && source.files && source.files.length) {
      data.append(source.name, source.files[0]);
    }
    if (source && source.type === "checkbox" && source.checked) {
      data.append(source.name, "on");
    }
    return data;
  }

  function send(form, source) {
    var url = form.getAttribute("data-file-autosave-url") || "";
    if (!url) return;
    setState(form, "saving");
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfFromForm(form),
        "X-Requested-With": "XMLHttpRequest"
      },
      body: buildData(form, source)
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data || !data.ok) {
            throw new Error((data && data.message) || "Falha no autosave do arquivo.");
          }
          setState(form, "saved");
        });
      })
      .catch(function (error) {
        setState(form, "error");
        console.error("[autosave] arquivo", error);
      });
  }

  function init() {
    var forms = document.querySelectorAll("form[data-file-autosave-url]");
    Array.prototype.forEach.call(forms, function (form) {
      form.addEventListener("change", function (event) {
        var target = event.target;
        if (!target || !target.name) return;
        if (target.type === "file" || target.name.slice(-6) === "-clear") {
          send(form, target);
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
