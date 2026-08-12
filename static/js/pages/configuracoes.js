(function () {
  const onlyDigits = window.CV.masks.onlyDigits;
  const maskCep = (valor) => window.CV.masks.format(valor, "cep");

  function setFieldError(input, message) {
    if (!input) return;
    input.setCustomValidity(message || "");
    input.classList.toggle("is-invalid", Boolean(message));
    if (message) input.reportValidity();
  }

  async function buscarCep(cepInput, fields) {
    const cepDigits = onlyDigits(cepInput.value);
    if (!cepDigits) {
      setFieldError(cepInput, "");
      return false;
    }
    if (cepDigits.length !== 8) {
      setFieldError(cepInput, "CEP deve conter 8 dígitos.");
      return false;
    }

    setFieldError(cepInput, "");
    const endpoint = cepInput.dataset.cepLookupUrlTemplate.replace("00000000", cepDigits);

    try {
      const result = await window.CV.http.fetchJson(endpoint);
      const payload = result.data || {};
      const ok = result.ok;
      const status = result.status;

      if (status === 401) {
        setFieldError(cepInput, "Sessão expirada. Atualize a página e tente novamente.");
        return false;
      }
      if (!ok) {
        setFieldError(cepInput, payload.erro || "CEP inválido.");
        return false;
      }
      if (!payload || typeof payload !== "object" || (!payload.logradouro && !payload.bairro && !payload.cidade && !payload.uf)) {
        setFieldError(cepInput, "Não foi possível consultar o CEP agora.");
        return false;
      }

      if (fields.logradouro) fields.logradouro.value = payload.logradouro || "";
      if (fields.bairro) fields.bairro.value = payload.bairro || "";
      if (fields.cidade) fields.cidade.value = (payload.cidade || "").toUpperCase();
      // UF: sigla vai no input hidden; o nome do estado é exibido no campo somente leitura.
      if (fields.uf) fields.uf.value = (payload.uf || "").toUpperCase();
      if (fields.ufNome) fields.ufNome.value = (payload.estado || payload.uf || "").toUpperCase();
      return true;
    } catch (_error) {
      setFieldError(cepInput, "Não foi possível consultar o CEP agora.");
      return false;
    }
  }

  function initConfiguracoesForm(form) {
    ["#id_unidade", "#id_logradouro", "#id_bairro", "#id_cidade_endereco"].forEach(
      (selector) => {
        const input = form.querySelector(selector);
        if (!input) return;
        input.addEventListener("input", () => {
          input.value = input.value.toUpperCase();
        });
      }
    );

    const cepInput = form.querySelector("#id_cep");
    const lookupUrlTemplate =
      cepInput?.dataset?.cepLookupUrlTemplate ||
      form.dataset.cepLookupUrlTemplate ||
      "/cadastros/api/cep/00000000/";
    if (!cepInput || !lookupUrlTemplate) return;
    cepInput.dataset.cepLookupUrlTemplate = lookupUrlTemplate;

    const fields = {
      logradouro: form.querySelector("#id_logradouro"),
      bairro: form.querySelector("#id_bairro"),
      cidade: form.querySelector("#id_cidade_endereco"),
      uf: form.querySelector("#id_uf"),
      ufNome: form.querySelector("#id_uf_nome"),
    };

    let lastCepLookup = "";
    const maybeLookup = async () => {
      cepInput.value = maskCep(cepInput.value);
      const cepDigits = onlyDigits(cepInput.value);
      if (cepDigits.length !== 8) return;
      if (cepDigits === lastCepLookup) return;
      const ok = await buscarCep(cepInput, fields);
      if (ok) {
        lastCepLookup = cepDigits;
      } else {
        lastCepLookup = "";
      }
    };

    cepInput.addEventListener("input", maybeLookup);
    cepInput.addEventListener("blur", maybeLookup);

    const telefoneInput = form.querySelector("#id_telefone");
    if (telefoneInput) {
      telefoneInput.addEventListener("input", () => {
        telefoneInput.value = telefoneInput.value.replace(/[^\d() -]/g, "");
      });
    }
  }

  function initDestinatarioForm(form) {
    const select = form.querySelector("#id_destinatario_oficio");
    const nomeHidden = form.querySelector("#id_destinatario_oficio_nome");
    const cargoInput = form.querySelector("#id_destinatario_oficio_cargo");
    const unidadeInput = form.querySelector("#id_destinatario_oficio_unidade");
    if (!select || !nomeHidden) return;

    const textInput = window.CV.picker.part(window.CV.picker.rootFor(select), "input");

    if (textInput) {
      textInput.addEventListener("input", () => {
        nomeHidden.value = textInput.value.trim();
      });
    }

    select.addEventListener("change", () => {
      const option = select.selectedOptions[0];
      if (!option || !option.value) return;
      const nome = (option.textContent || "").trim();
      nomeHidden.value = nome;
      if (textInput) textInput.value = nome;
      if (cargoInput) cargoInput.value = option.dataset.cargo || "";
      if (unidadeInput) unidadeInput.value = option.dataset.unidadeNome || option.dataset.unidade || "";
    });
  }

  function init() {
    document.querySelectorAll("[data-configuracoes-form]").forEach(initConfiguracoesForm);
    document.querySelectorAll("[data-destinatario-form]").forEach(initDestinatarioForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
