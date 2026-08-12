/**
 * MaskEngine — máscaras por data-mask (idempotente, re-scan em DOM dinâmico).
 */
(function () {
  'use strict';

  var BOUND = 'data-mask-bound';

  function onlyDigits(value) {
    return String(value || '').replace(/\D/g, '');
  }

  function onlyAlnum(value) {
    return String(value || '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  function maskCpf(value) {
    var v = onlyDigits(value).slice(0, 11);
    if (v.length <= 3) return v;
    if (v.length <= 6) return v.slice(0, 3) + '.' + v.slice(3);
    if (v.length <= 9) return v.slice(0, 3) + '.' + v.slice(3, 6) + '.' + v.slice(6);
    return v.slice(0, 3) + '.' + v.slice(3, 6) + '.' + v.slice(6, 9) + '-' + v.slice(9);
  }

  function maskRg(value) {
    var v = onlyAlnum(value).slice(0, 9);
    if (v.length <= 1) return v;
    if (v.length <= 4) return v.slice(0, 1) + '.' + v.slice(1);
    if (v.length <= 7) return v.slice(0, 1) + '.' + v.slice(1, 4) + '.' + v.slice(4);
    if (v.length === 8) return v.slice(0, 1) + '.' + v.slice(1, 4) + '.' + v.slice(4, 7) + '-' + v.slice(7);
    return v.slice(0, 2) + '.' + v.slice(2, 5) + '.' + v.slice(5, 8) + '-' + v.slice(8);
  }

  function maskPlaca(value) {
    return onlyAlnum(value).slice(0, 7);
  }

  function maskCep(value) {
    var v = onlyDigits(value).slice(0, 8);
    if (v.length <= 5) return v;
    return v.slice(0, 5) + '-' + v.slice(5);
  }

  function maskDate(value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    var iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (iso) return iso[3] + '/' + iso[2] + '/' + iso[1];
    var v = onlyDigits(raw).slice(0, 8);
    if (v.length <= 2) return v;
    if (v.length <= 4) return v.slice(0, 2) + '/' + v.slice(2);
    return v.slice(0, 2) + '/' + v.slice(2, 4) + '/' + v.slice(4);
  }

  function maskTime(value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    var v = onlyDigits(raw).slice(0, 4);
    if (v.length <= 2) return v;
    return v.slice(0, 2) + ':' + v.slice(2);
  }

  function maskProtocolo(value) {
    var v = onlyDigits(value).slice(0, 9);
    if (v.length <= 2) return v;
    if (v.length <= 5) return v.slice(0, 2) + '.' + v.slice(2);
    if (v.length <= 8) return v.slice(0, 2) + '.' + v.slice(2, 5) + '.' + v.slice(5);
    return v.slice(0, 2) + '.' + v.slice(2, 5) + '.' + v.slice(5, 8) + '-' + v.slice(8);
  }

  function maskTelefone(value) {
    var v = onlyDigits(value).slice(0, 11);
    if (!v) return '';
    if (v.length <= 2) return '(' + v;
    if (v.length <= 6) return '(' + v.slice(0, 2) + ') ' + v.slice(2);
    if (v.length <= 10) return '(' + v.slice(0, 2) + ') ' + v.slice(2, 6) + '-' + v.slice(6);
    return '(' + v.slice(0, 2) + ') ' + v.slice(2, 7) + '-' + v.slice(7);
  }

  function maskUpper(value) {
    return String(value || '').toUpperCase();
  }

  function maskMilhar(value) {
    var v = onlyDigits(value).replace(/^0+(?=\d)/, '');
    if (!v) return '';
    return v.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  var formatters = {
    upper: maskUpper,
    cpf: maskCpf,
    rg: maskRg,
    placa: maskPlaca,
    cep: maskCep,
    date: maskDate,
    time: maskTime,
    telefone: maskTelefone,
    protocolo: maskProtocolo,
    milhar: maskMilhar,
  };

  function format(value, mask) {
    var fn = formatters[mask];
    if (!fn) return value == null ? '' : String(value);
    return fn(value);
  }

  function isMaskable(el) {
    if (!el || !el.dataset) return false;
    if (!el.dataset.mask) return false;
    if (el.disabled || el.readOnly) return false;
    var tag = (el.tagName || '').toLowerCase();
    return tag === 'input' || tag === 'textarea';
  }

  function apply(input) {
    if (!isMaskable(input)) return;
    var mask = input.dataset.mask;
    var next = format(input.value, mask);
    if (input.value !== next) {
      input.value = next;
    }
  }

  function bind(input) {
    if (!isMaskable(input)) return;
    if (input.getAttribute(BOUND) === 'true') return;
    input.setAttribute(BOUND, 'true');
    apply(input);
    input.addEventListener('input', function () {
      apply(input);
    });
  }

  function scan(root) {
    var scope = root && root.querySelectorAll ? root : document;
    if (!scope || !scope.querySelectorAll) return;
    if (scope.matches && scope.matches('input[data-mask], textarea[data-mask]')) bind(scope);
    scope.querySelectorAll('input[data-mask], textarea[data-mask]').forEach(bind);
  }

  var MaskEngine = {
    /* JS-11 — exportado porque tres consumidores reimplementavam esta funcao:
       era a unica de masks.js sem saida publica, ja que `format` so alcanca
       os formatadores nomeados no dict `formatters`. */
    onlyDigits: onlyDigits,
    scan: scan,
    apply: apply,
    format: format,
  };

  window.CV = window.CV || {};
  window.CV.masks = MaskEngine;

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('masks', scan);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { scan(document); });
  } else {
    scan(document);
  }
})();
