(function () {
  'use strict';
  window.CV = window.CV || {};
  window.CV.autosaveSnapshots = window.CV.autosaveSnapshots || {};
  window.CV.autosaveValidators = window.CV.autosaveValidators || {};
  var DEBUG_AUTOSAVE = !!window.DEBUG_AUTOSAVE;
  function debug() {
    if (!DEBUG_AUTOSAVE) return;
    var args = Array.prototype.slice.call(arguments);
    args.unshift('autosave');
    window.CV.log.debug.apply(window.CV.log, args);
  }

  function fieldValue(input) {
    if (!input) return null;
    if (input.type === 'checkbox') return !!input.checked;
    if (input.type === 'radio') return !!input.checked ? input.value : null;
    if (input.tagName === 'SELECT' && input.multiple) {
      return Array.prototype.slice.call(input.selectedOptions).map(function (option) {
        return option.value;
      });
    }
    return input.value;
  }

  function createFormAutosave(form, options) {
    var model = (options && options.model) || form.dataset.autosaveModel || '';
    var statusElement = options && options.statusElement;
    var dirtyFields = new Set();
    var dirtySnapshots = new Set();
    var inputTimer = null;
    var paused = false;
    var submitting = false;
    var inFlight = null;
    var abortController = null;
    var queueAfterFlight = false;
    var readyToSubmit = false;

    function emit(name, detail) {
      form.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    }

    function setState(state) {
      form.dataset.autosaveState = state;
      if (statusElement) statusElement.dataset.state = state;
    }

    function objectId() {
      return String(form.dataset.autosaveObjectId || '');
    }

    function autosaveUrl() {
      return objectId() ? String(form.dataset.autosaveUrl || '') : String(form.dataset.autosaveCreateUrl || '');
    }

    function buildPayload() {
      var fields = {};
      dirtyFields.forEach(function (name) {
        var input = form.querySelector('[name="' + name + '"]');
        if (!input) return;
        var val = fieldValue(input);
        if (val === null) return;
        fields[name] = val;
      });

      var snapshots = {};
      var provider = (window.CV.autosaveSnapshots || {})[model];
      if (typeof provider === 'function') {
        snapshots = provider(form, { dirtySnapshots: Array.from(dirtySnapshots) }) || {};
      }
      return {
        object_id: objectId(),
        form_id: form.id || '',
        model: model,
        dirty_fields: Array.from(dirtyFields),
        fields: fields,
        snapshots: snapshots
      };
    }

    function shouldCreate(payload) {
      if (payload.object_id) return true;
      var validator = (window.CV.autosaveValidators || {})[model];
      if (typeof validator !== 'function') return true;
      return !!validator(payload, form);
    }

    function applyCreation(data) {
      if (!data || !data.created || !data.object_id) return;
      form.dataset.autosaveObjectId = String(data.object_id);
      var editUrl = form.dataset.autosaveEditUrlTemplate || '';
      if (editUrl.indexOf('__ID__') !== -1) {
        form.dataset.autosaveUrl = editUrl.replace('__ID__', String(data.object_id));
      }
      emit('autosave:created', data);
    }

    function send() {
      if (paused || submitting) return Promise.resolve(false);
      var url = autosaveUrl();
      if (!url) return Promise.resolve(false);

      var payload = buildPayload();
      debug('enviando payload', payload);
      if (!payload.dirty_fields.length && !dirtySnapshots.size) return Promise.resolve(false);
      if (!shouldCreate(payload)) return Promise.resolve(false);
      if (inFlight) {
        queueAfterFlight = true;
        return inFlight;
      }

      setState('saving');
      emit('autosave:before', payload);
      abortController = new AbortController();
      var request = window.CV.http.fetchJson(url, {
        method: 'POST',
        form: form,
        body: payload,
        signal: abortController.signal
      });

      inFlight = request.then(function (result) {
          var data = result.data;
          if (!result.ok || !data || !data.ok) {
            throw new Error((data && data.message) || 'Falha no autosave.');
          }
          dirtyFields.clear();
          dirtySnapshots.clear();
          applyCreation(data);
          setState('saved');
          debug('resposta sucesso', result.status, data);
          emit('autosave:success', data);
          return true;
        }).catch(function (error) {
        if (error && error.name === 'AbortError') return false;
        setState('error');
        window.CV.log.error('autosave', 'erro', error);
        emit('autosave:error', { message: error && error.message ? error.message : 'Falha no autosave.' });
        return false;
      }).finally(function () {
        inFlight = null;
        abortController = null;
        if (queueAfterFlight) {
          queueAfterFlight = false;
          schedule(450);
        }
      });
      return inFlight;
    }

    function schedule(delay) {
      if (paused || submitting) return;
      window.clearTimeout(inputTimer);
      debug('agendando save', {
        formId: form.id || '',
        dirtyFields: Array.from(dirtyFields),
        dirtySnapshots: Array.from(dirtySnapshots)
      });
      inputTimer = window.setTimeout(send, typeof delay === 'number' ? delay : 1200);
    }

    function markDirty(fieldName) {
      if (!fieldName) return;
      dirtyFields.add(String(fieldName));
    }

    function markSnapshotChanged(name) {
      dirtySnapshots.add(name || 'default');
    }

    function onInput(event) {
      var target = event.target;
      if (!target || !target.name || target.type === 'hidden') return;
      markDirty(target.name);
      debug('campo alterado', { name: target.name, id: target.id || '', value: fieldValue(target) });
      schedule(1200);
    }

    function onChange(event) {
      var target = event.target;
      if (!target || !target.name) return;
      markDirty(target.name);
      debug('campo alterado', { name: target.name, id: target.id || '', value: fieldValue(target) });
      schedule(900);
    }

    function onBlur(event) {
      var target = event.target;
      if (!target || !target.name) return;
      markDirty(target.name);
      schedule(350);
    }

    function onSubmit(event) {
      if (readyToSubmit || !inFlight) {
        submitting = true;
        window.clearTimeout(inputTimer);
        paused = true;
        return;
      }

      /* Um autosave anterior (com dados mais antigos, ex.: antes do usuário
         adicionar o último servidor) ainda está em voo. Abortar o fetch no
         cliente não impede o servidor de terminar de processá-lo — se essa
         resposta chegar e salvar depois do POST real do "Avançar", ela
         sobrescreve o M2M de servidores com o snapshot antigo, apagando quem
         foi adicionado por último. Em vez de abortar, espera o autosave
         pendente terminar (garantindo que o POST real seja sempre o último a
         gravar) e só então reenvia o formulário. */
      event.preventDefault();
      event.stopImmediatePropagation();
      window.clearTimeout(inputTimer);
      paused = true;
      var submitter = event.submitter;
      var settled = false;
      function resumeSubmit() {
        if (settled) return;
        settled = true;
        readyToSubmit = true;
        window.clearTimeout(inputTimer);
        /* requestSubmit preserva o submitter; click() em botão com ícone SVG
           pode falhar em alguns browsers se o alvo do evento for o ícone. */
        if (typeof form.requestSubmit === 'function') {
          try {
            form.requestSubmit(submitter || undefined);
            return;
          } catch (err) {
            /* fall through */
          }
        }
        if (submitter && typeof submitter.click === 'function') {
          submitter.click();
        } else {
          form.submit();
        }
      }
      /* Rede travada não pode segurar o "Avançar" para sempre. */
      var safety = window.setTimeout(resumeSubmit, 8000);
      inFlight.finally(function () {
        window.clearTimeout(safety);
        resumeSubmit();
      });
    }

    function prepareNavigation() {
      if (paused || submitting) return null;
      if (!inFlight && !inputTimer) return null;

      /* Mesma corrida do submit acima, só que aqui a navegação nem é um POST
         do próprio form — é um link comum (stepper, "Voltar", "Cadastrar novo
         viajante"...). Sem interceptar o clique, a navegação sai imediatamente
         e a única rede de proteção é o beforeunload/sendBeacon abaixo, que não
         espera nenhum autosave em voo terminar antes de mandar o snapshot
         atual: se o autosave mais antigo (ainda em voo) responder depois do
         sendBeacon, ele sobrescreve o M2M de servidores com o estado anterior.
         Aqui a gente cancela o debounce pendente, garante que o snapshot atual
         seja enviado e só troca de página depois que a gravação terminar.
         Escuta no `document` (não no `form`) porque o header com o link
         "Voltar" (page_header.html) fica fora da tag <form> em
         todos os wizards — um listener preso ao form nunca veria esse clique. */
      window.clearTimeout(inputTimer);
      /* `send()` desiste na hora se `paused` já estiver true, então só
         marcamos `paused` depois que o(s) envio(s) de fato saírem — nada mais
         dispara `schedule()` nesse meio-tempo, já que a navegação está prestes
         a acontecer e nenhum evento novo do form roda antes disso. */
      var pending = inFlight ? inFlight.then(function () { return send(); }) : send();
      return pending.finally(function () {
        paused = true;
      });
    }

    function sendBeacon() {
      if (!navigator.sendBeacon) return;
      if (paused || submitting) return;
      var url = autosaveUrl();
      if (!url) return;
      var payload = buildPayload();
      if (!payload.dirty_fields.length && !dirtySnapshots.size) return;
      if (!shouldCreate(payload)) return;
      /* sendBeacon não permite setar o cabeçalho CSRF. Um Blob
         JSON puro cai no CSRF do Django e o servidor rejeita com 403 sem
         nenhum aviso no cliente — o autosave "parecia" ter disparado mas
         nunca era persistido. Envia como FormData (multipart) com o token
         csrf como campo normal, que o middleware valida do jeito de sempre. */
      var formData = new FormData();
      formData.append('csrfmiddlewaretoken', window.CV.http.getCsrfToken(form));
      formData.append('payload', JSON.stringify(payload));
      navigator.sendBeacon(url, formData);
      debug('sendBeacon disparado');
    }

    form.addEventListener('input', onInput, true);
    form.addEventListener('change', onChange, true);
    form.addEventListener('blur', onBlur, true);
    form.addEventListener('submit', onSubmit, true);

    return {
      schedule: schedule,
      flush: function () {
        window.clearTimeout(inputTimer);
        return send();
      },
      pause: function () { paused = true; },
      resume: function () { paused = false; },
      markDirty: markDirty,
      markSnapshotChanged: markSnapshotChanged,
      prepareNavigation: prepareNavigation,
      sendBeacon: sendBeacon,
      destroy: function () {
        paused = true;
        window.clearTimeout(inputTimer);
        inputTimer = null;
        queueAfterFlight = false;
        if (abortController) abortController.abort();
        form.removeEventListener('input', onInput, true);
        form.removeEventListener('change', onChange, true);
        form.removeEventListener('blur', onBlur, true);
        form.removeEventListener('submit', onSubmit, true);
      }
    };
  }

  var forms = new WeakMap();
  var activeInstances = new Set();

  function registerInstance(form, options) {
    var instance = createFormAutosave(form, options || {});
    forms.set(form, instance);
    activeInstances.add(instance);
    return instance;
  }

  document.addEventListener('click', function (event) {
    var target = event.target;
    var link = target && target.closest ? target.closest('[data-autosave-link="1"]') : null;
    if (!link || !link.href) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== '_self') return;

    var pending = [];
    activeInstances.forEach(function (instance) {
      var operation = instance.prepareNavigation();
      if (operation) pending.push(operation);
    });
    if (!pending.length) return;

    event.preventDefault();
    var href = link.href;
    Promise.allSettled(pending).finally(function () {
      window.location.href = href;
    });
  }, true);

  window.addEventListener('beforeunload', function () {
    activeInstances.forEach(function (instance) {
      instance.sendBeacon();
    });
  });

  function findForms(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var nodes = Array.prototype.slice.call(
      scope.querySelectorAll('form[data-autosave="true"]')
    );
    if (scope.matches && scope.matches('form[data-autosave="true"]')) {
      nodes.unshift(scope);
    }
    return nodes;
  }

  function destroy(root) {
    findForms(root).forEach(function (form) {
      var instance = forms.get(form);
      if (!instance) return;
      instance.destroy();
      activeInstances.delete(instance);
      forms.delete(form);
    });
  }

  window.CV.autosave = {
    init: function (root) {
      debug('arquivo carregado');
      debug('init executado');
      var nodes = findForms(root);
      debug('forms encontrados', nodes.length);
      nodes.forEach(function (form) {
        if (forms.has(form)) return;
        debug('registrando form', {
          id: form.id || '',
          model: form.dataset.autosaveModel || '',
          objectId: form.dataset.autosaveObjectId || '',
          url: form.dataset.autosaveUrl || '',
          createUrl: form.dataset.autosaveCreateUrl || ''
        });
        registerInstance(form, {});
      });
    },
    registerForm: function (form, options) {
      if (!form) return null;
      if (forms.has(form)) return forms.get(form);
      return registerInstance(form, options);
    },
    flush: function (form) {
      var instance = forms.get(form);
      return instance ? instance.flush() : Promise.resolve(false);
    },
    pause: function (form) {
      var instance = forms.get(form);
      if (instance) instance.pause();
    },
    resume: function (form) {
      var instance = forms.get(form);
      if (instance) instance.resume();
    },
    markSnapshotChanged: function (form, name, delay) {
      var instance = forms.get(form);
      if (!instance) return;
      instance.markSnapshotChanged(name);
      instance.schedule(typeof delay === 'number' ? delay : 900);
    },
    markDirty: function (form, fieldName, delay) {
      var instance = forms.get(form);
      if (!instance) return;
      instance.markDirty(fieldName);
      instance.schedule(typeof delay === 'number' ? delay : 900);
    }
  };
  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('autosave', window.CV.autosave.init, destroy);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { window.CV.autosave.init(); });
  } else {
    window.CV.autosave.init();
  }
})();
