/**
 * HTTP helpers — Central de Viagens
 * CSRF, fetch JSON e leitura padronizada de respostas.
 */
(function () {
  'use strict';

  window.CV = window.CV || {};

  function getCookie(name) {
    var prefix = name + '=';
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].trim();
      if (p.indexOf(prefix) === 0) {
        return decodeURIComponent(p.slice(prefix.length));
      }
    }
    return '';
  }

  function getCsrfToken(form) {
    if (form && form.querySelector) {
      var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
      if (input && input.value) {
        return input.value;
      }
    }
    return getCookie('csrftoken') || '';
  }

  function readJsonResponse(response) {
    var contentType = (response.headers && response.headers.get('content-type')) || '';
    if (contentType.indexOf('application/json') !== -1) {
      return response.json().then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      });
    }
    return response.text().then(function () {
      return {
        ok: false,
        status: response.status,
        data: {
          ok: false,
          error:
            response.status === 401
              ? 'Sessão expirada. Faça login novamente.'
              : 'O servidor retornou uma resposta inválida.',
        },
      };
    });
  }

  function prepareBody(body, headers) {
    if (body == null) {
      return { body: undefined, headers: headers };
    }
    if (body instanceof FormData || typeof body === 'string' || body instanceof Blob) {
      return { body: body, headers: headers };
    }
    var nextHeaders = Object.assign({}, headers);
    if (!nextHeaders['Content-Type'] && !nextHeaders['content-type']) {
      nextHeaders['Content-Type'] = 'application/json';
    }
    return { body: JSON.stringify(body), headers: nextHeaders };
  }

  function fetchJson(url, options) {
    options = options || {};
    var headers = Object.assign(
      { 'X-Requested-With': 'XMLHttpRequest' },
      options.headers || {}
    );
    var token = getCsrfToken(options.form || null);
    if (token) {
      headers['X-CSRFToken'] = token;
    }
    var prepared = prepareBody(options.body, headers);
    return fetch(url, {
      method: options.method || 'GET',
      credentials: 'same-origin',
      headers: prepared.headers,
      body: prepared.body,
      signal: options.signal,
    }).then(function (response) {
      if (options.rawResponse) {
        return response;
      }
      return readJsonResponse(response);
    });
  }

  window.CV.http = {
    getCookie: getCookie,
    getCsrfToken: getCsrfToken,
    readJsonResponse: readJsonResponse,
    fetchJson: fetchJson,
  };
})();
