import {
  createTrechosModule,
  getTrechosEmptyHtml,
  TRECHO_CARD_SELECTOR,
  buildTrechoCard,
  initTrechosFields,
  setTrechoDateValue,
  queryTrechoCards,
} from './trechos.js';
import { createMapaModule } from './mapa.js';

export function initRoteirosEditor() {
  const modules = {
    trechos: createTrechosModule(),
    mapa: createMapaModule(),
  };
  window.CV = window.CV || {};
  window.CV.roteiros = window.CV.roteiros || {};
  window.CV.roteiros.modules = modules;

  (function () {
  'use strict';
  var form = document.getElementById('roteiro-editor-form');
  if (!form || form.dataset.ready === '1') return;
  form.dataset.ready = '1';
  var isOficio = !!document.querySelector('.roteiro-editor--oficio');
  function $(id) { return document.getElementById(id); }
  var initialRoteiroState = JSON.parse($('roteiro-editor-state-data').textContent || '{}');
  var routes = JSON.parse($('roteiro-editor-routes-data').textContent || '[]');
  var rawInitialRoteiroDiarias = JSON.parse($('roteiro-editor-diarias-data').textContent || 'null');
  var initialRoteiroDiarias = rawInitialRoteiroDiarias && typeof rawInitialRoteiroDiarias === 'object' ? rawInitialRoteiroDiarias : null;
  var routeMap = {};
  routes.forEach(function(item) { routeMap[String(item.id)] = item; });
  var apiCidades = form.dataset.apiCidadesUrl || '';
  var apiDiarias = form.dataset.apiDiariasUrl || '';
  var urlTrechosEstimar = form.dataset.urlTrechosEstimar || '';
  var urlCalcularRotaPreview = form.dataset.apiCalcularRotaPreviewUrl || '';
  var autosaveIdInput = $('id_autosave_obj_id');
  var autosaveStatus = $('roteiro-autosave-status');
  window.CV = window.CV || {};
  window.CV.autosaveSnapshots = window.CV.autosaveSnapshots || {};
  window.CV.autosaveValidators = window.CV.autosaveValidators || {};
  window.CV.autosaveSnapshots.roteiro = function() {
    return {
      roteiro_editor_state: captureCurrentState(),
      roteiro_mapa: {
        geometry_json: (($('id_map_route_geometry_json') || {}).value || ''),
        points_json: (($('id_map_route_points_json') || {}).value || ''),
        distance_km: (($('id_map_route_distance_km') || {}).value || ''),
        duration_minutes: (($('id_map_route_duration_minutes') || {}).value || ''),
        provider: (($('id_map_route_provider') || {}).value || ''),
        calculated_at: (($('id_map_route_calculated_at') || {}).value || '')
      },
      roteiro_diarias: {
        quantidade_diarias: (($('id_quantidade_diarias') || {}).value || ''),
        valor_diarias: (($('id_valor_diarias') || {}).value || ''),
        valor_diarias_extenso: (($('id_valor_diarias_extenso') || {}).value || '')
      }
    };
  };
  window.CV.autosaveValidators.roteiro = function(payload) {
    if (payload.object_id) return true;
    var fields = payload.fields || {};
    var state = ((payload.snapshots || {}).roteiro_editor_state) || {};
    var trechos = state.trechos || [];
    return !!(
      String(fields.observacoes || '').trim() ||
      String(fields.origem_cidade || '').trim() ||
      String(fields.origem_estado || '').trim() ||
      trechos.length
    );
  };
  var autosave = window.CV.autosave ? window.CV.autosave.registerForm(form, {
    model: 'roteiro',
    statusElement: autosaveStatus
  }) : null;
  var destinoEstadoDefaultId = form.dataset.destinoEstadoDefaultId || '';
  var applyingState = false;
  var diariasTimer = null;
  var diariasInFlight = false;
  var diariasNeedsRerun = false;
  var routeSearchTimer = null;
  var loopRenderTimer = null;
  var autoEstimarTimer = null;
  var citiesCache = {};
  var lastTrechosSignature = null;
  function getTrechoCards() {
    return queryTrechoCards($('trechos-gerados-container'));
  }
  function parkTrechosDatePicker() {
    var picker = getTrechosDatePicker();
    var park = $('trechos-date-picker-park');
    if (!picker || !park) return;
    if (picker.parentNode !== park) park.appendChild(picker);
  }
  function placeTrechosDatePickerInFirstHeader() {
    var picker = getTrechosDatePicker();
    var park = $('trechos-date-picker-park');
    if (!picker || !park) return;
    var slot = document.querySelector(
      '#trechos-gerados-container [data-trechos-date-picker-slot]'
    );
    if (slot) {
      slot.appendChild(picker);
      return;
    }
    if (picker.parentNode !== park) park.appendChild(picker);
  }
  function mountTrechosHtml(html) {
    var container = $('trechos-gerados-container');
    if (!container) return;
    // Preserva #trechos-date-picker fora do container antes do innerHTML.
    parkTrechosDatePicker();
    container.innerHTML = html;
    initTrechosFields(container);
    placeTrechosDatePickerInFirstHeader();
  }
  function refreshSelectPickers(root) {
    if (window.CV.roteiros.wizard && typeof window.CV.roteiros.wizard.refreshSelectPickers === 'function') {
      window.CV.roteiros.wizard.refreshSelectPickers(root || form);
    }
  }
  function scheduleAutosave() {
    if (autosave) {
      autosave.markSnapshotChanged('roteiro_editor_state');
      autosave.markSnapshotChanged('roteiro_mapa');
      autosave.markSnapshotChanged('roteiro_diarias');
      autosave.schedule(1000);
    }
  }
  function notifyRouteStateChanged() {
    try {
      window.dispatchEvent(new CustomEvent('roteiros:route-state-changed'));
    } catch (e) {
      /* ignore */
    }
  }
  function cidadesUrl(estadoId) { return apiCidades.replace(/\/0\/?$/, '/' + estadoId + '/'); }
  function pad(v) { return v < 10 ? '0' + v : String(v); }
  function hhmm(min) { min = parseInt(min || 0, 10) || 0; if (!min) return '-'; return pad(Math.floor(min / 60)) + ':' + pad(min % 60); }
  function formatDurationInput(min) { min = parseInt(min || 0, 10); if (Number.isNaN(min) || min <= 0) return ''; return pad(Math.floor(min / 60)) + ':' + pad(min % 60); }
  function normalizeDurationInput(value) {
    var raw = String(value || '').trim(); if (!raw) return '';
    if (raw.indexOf(':') !== -1) {
      var parts = raw.split(':');
      var hours = (parts[0] || '').replace(/\D/g, '').slice(0, 2);
      var minutes = parts.slice(1).join('').replace(/\D/g, '').slice(0, 2);
      if (!hours && !minutes) return '';
      return minutes ? (hours + ':' + minutes) : (hours + ':');
    }
    var digits = raw.replace(/\D/g, '').slice(0, 4); if (!digits) return '';
    if (digits.length <= 2) return digits;
    if (digits.length === 3) return digits.slice(0, 2) + ':' + digits.slice(2);
    return digits.slice(0, 2) + ':' + digits.slice(2, 4);
  }
  function applyHhmmInputMask(el) {
    if (!el || applyingState) return;
    var norm = normalizeDurationInput(el.value);
    if (norm === el.value) return;
    var pos = norm.length;
    el.value = norm;
    try {
      el.setSelectionRange(pos, pos);
    } catch (e) {
      /* ignore */
    }
  }
  function parseDurationInput(value) {
    var text = String(value || '').trim(); if (!text) return null;
    var norm = text.indexOf(':') !== -1 ? text : normalizeDurationInput(text);
    var parts = norm.split(':'); if (parts.length !== 2) return null;
    var hours = parseInt(parts[0], 10); var minutes = parseInt(parts[1], 10);
    if (Number.isNaN(hours) || Number.isNaN(minutes) || minutes < 0 || minutes > 59) return null;
    return (hours * 60) + minutes;
  }
  function parseMinutesValue(value) {
    if (value == null || String(value).trim() === '') return null;
    var parsed = parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  function pad2(v) { v = parseInt(v, 10); return v < 10 ? '0' + v : String(v); }
  function currentYearString() {
    return String(new Date().getFullYear());
  }
  function normalizeDateInput(value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    var iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (iso) return iso[3] + '/' + iso[2];
    var digits = raw.replace(/\D/g, '').slice(0, 4);
    if (!digits) return '';
    if (digits.length <= 2) return digits;
    return digits.slice(0, 2) + '/' + digits.slice(2, 4);
  }
  function parseDateInput(value) {
    var raw = String(value || '').trim();
    if (!raw) return '';
    var iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (iso) return iso[1] + '-' + iso[2] + '-' + iso[3];
    var normalized = normalizeDateInput(raw);
    if (!normalized) return '';
    var parts = normalized.split('/');
    if (parts.length < 2) return '';
    var day = pad2(parts[0]);
    var month = pad2(parts[1]);
    var year = parts[2] ? String(parts[2]).replace(/\D/g, '').slice(0, 4) : currentYearString();
    if (!year || year.length < 4) year = currentYearString();
    return year + '-' + month + '-' + day;
  }
  function syncBateVoltaDatePair(textEl, nativeEl) {
    if (!textEl || !nativeEl) return;
    if (document.activeElement === nativeEl) {
      textEl.value = normalizeDateInput(nativeEl.value);
      return;
    }
    textEl.value = normalizeDateInput(textEl.value || nativeEl.value);
    nativeEl.value = parseDateInput(textEl.value) || '';
  }
  function normalizeLocationLabel(value) {
    return String(value || '').trim().toUpperCase();
  }
  function isLoopModeActive(state) {
    if (state && state.bate_volta_diario && state.bate_volta_diario.ativo) return true;
    var input = $('id_bate_volta_diario_ativo');
    if (!input) return false;
    if (input.type === 'checkbox') return !!input.checked;
    return String(input.value || '').toLowerCase() === 'true';
  }
  function toggleBateVoltaPanel() {
    var active = isLoopModeActive();
    var body = $('bate-volta-body');
    var panel = $('bate-volta-panel');
    var status = $('bate-volta-status-text');
    var chip = $('bate-volta-status-chip');
    if (body) {
      body.hidden = !active;
    }
    if (panel) {
      panel.classList.toggle('is-muted', !active);
    }
    if (chip) {
      chip.textContent = active ? 'Ativo' : 'Inativo';
      chip.classList.toggle('is-on', active);
    }
    if (status) {
      status.textContent = active
        ? 'Modo ativo. O editor abaixo passa a refletir o loop diário gerado.'
        : 'Modo inativo.';
    }
  }
  function syncBateVoltaDurationInputs() {
    var idaHidden = $('id_bate_volta_ida_tempo_min');
    var idaText = $('id_bate_volta_ida_tempo_hhmm');
    var voltaHidden = $('id_bate_volta_volta_tempo_min');
    var voltaText = $('id_bate_volta_volta_tempo_hhmm');
    if (idaText && idaHidden && document.activeElement !== idaText) {
      idaText.value = formatDurationInput(parseMinutesValue(idaHidden.value));
    }
    if (voltaText && voltaHidden && document.activeElement !== voltaText) {
      voltaText.value = formatDurationInput(parseMinutesValue(voltaHidden.value));
    }
  }
  function syncBateVoltaReturnDurationFromOutbound(normalized, parsed) {
    var voltaHidden = $('id_bate_volta_volta_tempo_min');
    var voltaText = $('id_bate_volta_volta_tempo_hhmm');
    if (!voltaHidden || !voltaText) return;
    voltaHidden.value = parsed != null ? String(parsed) : '';
    voltaText.value = normalized || '';
  }
  function stateHasReturnToSede(state) {
    var sedeId = String((state && state.sede_cidade_id) || ($('id_origem_cidade') || {}).value || '');
    var sedeNome = normalizeLocationLabel(selectedText($('id_origem_cidade')));
    return ((state && state.trechos) || []).some(function(trecho) {
      var destinoId = String(trecho.destino_cidade_id || '');
      var destinoNome = normalizeLocationLabel(trecho.destino_nome || '');
      return (sedeId && destinoId && sedeId === destinoId) || (sedeNome && destinoNome && sedeNome === destinoNome);
    });
  }
  function shouldUseExactTrechos(state) {
    return isLoopModeActive(state) || stateHasReturnToSede(state);
  }
  function formatDateInputValue(dateObj) {
    return dateObj.getFullYear() + '-' + pad(dateObj.getMonth() + 1) + '-' + pad(dateObj.getDate());
  }
  function addMinutes(dateValue, timeValue, totalMinutes) {
    var start = new Date(dateValue + 'T' + timeValue);
    if (Number.isNaN(start.getTime())) return null;
    var end = new Date(start.getTime() + (totalMinutes * 60000));
    return {
      data: formatDateInputValue(end),
      hora: pad(end.getHours()) + ':' + pad(end.getMinutes())
    };
  }
  /** chegada = saída + tempo_viagem + tempo_adicional (cruza meia-noite conforme Date). */
  function calcularChegada(saidaData, saidaHora, tempoViagemMin, tempoAdicionalMin) {
    var cru = parseInt(tempoViagemMin || 0, 10) || 0;
    var add = parseInt(tempoAdicionalMin || 0, 10);
    if (Number.isNaN(add) || add < 0) add = 0;
    var total = cru + add;
    if (!saidaData || !saidaHora || total <= 0) return null;
    return addMinutes(saidaData, saidaHora, total);
  }
  function buildLoopTrechosFromInputs() {
    if (!isLoopModeActive()) return [];
    var destinosValidos = getDestinos().filter(function(destino) { return destino.estado_id && destino.cidade_id; });
    if (!destinosValidos.length) return [];
    var destino = destinosValidos[0];
    var dataInicio = ($('id_bate_volta_data_inicio_native') || {}).value || '';
    var dataFim = ($('id_bate_volta_data_fim_native') || {}).value || '';
    var idaHora = $('id_bate_volta_ida_saida_hora').value || '';
    var voltaHora = $('id_bate_volta_volta_saida_hora').value || '';
    var idaMin = parseMinutesValue($('id_bate_volta_ida_tempo_min').value);
    var voltaMin = parseMinutesValue($('id_bate_volta_volta_tempo_min').value);
    var sedeEstadoId = $('id_origem_estado').value || '';
    var sedeCidadeId = $('id_origem_cidade').value || '';
    var sedeNome = selectedText($('id_origem_cidade'));
    if (!dataInicio || !dataFim || !idaHora || !voltaHora || !idaMin || !voltaMin || !sedeEstadoId || !sedeCidadeId || !sedeNome) {
      return [];
    }
    var current = new Date(dataInicio + 'T00:00');
    var end = new Date(dataFim + 'T00:00');
    if (Number.isNaN(current.getTime()) || Number.isNaN(end.getTime()) || current.getTime() > end.getTime()) {
      return [];
    }
    var trechos = [];
    var ordem = 0;
    while (current.getTime() <= end.getTime()) {
      var dataBase = formatDateInputValue(current);
      var idaChegada = addMinutes(dataBase, idaHora, idaMin);
      var voltaChegada = addMinutes(dataBase, voltaHora, voltaMin);
      if (!idaChegada || !voltaChegada) return [];
      trechos.push({
        ordem: ordem++,
        origem_nome: sedeNome,
        destino_nome: destino.cidade_nome || '',
        origem_estado_id: sedeEstadoId,
        origem_cidade_id: sedeCidadeId,
        destino_estado_id: destino.estado_id,
        destino_cidade_id: destino.cidade_id,
        saida_data: dataBase,
        saida_hora: idaHora,
        chegada_data: idaChegada.data,
        chegada_hora: idaChegada.hora,
        distancia_km: '',
        tempo_cru_estimado_min: String(idaMin),
        tempo_adicional_min: '0',
        duracao_estimada_min: String(idaMin),
        rota_fonte: ''
      });
      trechos.push({
        ordem: ordem++,
        origem_nome: destino.cidade_nome || '',
        destino_nome: sedeNome,
        origem_estado_id: destino.estado_id,
        origem_cidade_id: destino.cidade_id,
        destino_estado_id: sedeEstadoId,
        destino_cidade_id: sedeCidadeId,
        saida_data: dataBase,
        saida_hora: voltaHora,
        chegada_data: voltaChegada.data,
        chegada_hora: voltaChegada.hora,
        distancia_km: '',
        tempo_cru_estimado_min: String(voltaMin),
        tempo_adicional_min: '0',
        duracao_estimada_min: String(voltaMin),
        rota_fonte: ''
      });
      current.setDate(current.getDate() + 1);
    }
    return trechos;
  }
  function syncRetornoFromLoopTrechos(trechos, fallbackRetorno) {
    var last = trechos && trechos.length ? trechos[trechos.length - 1] : null;
    if (!last && !fallbackRetorno) return;
    last = last || fallbackRetorno || {};
    $('id_retorno_saida_cidade').value = last.origem_nome || (fallbackRetorno && fallbackRetorno.saida_cidade) || '';
    $('id_retorno_chegada_cidade').value = last.destino_nome || (fallbackRetorno && fallbackRetorno.chegada_cidade) || '';
    setRoteiroDatePickerValue('id_retorno_saida_data', 'id_retorno_saida_data_display', last.saida_data || (fallbackRetorno && fallbackRetorno.saida_data) || '');
    $('id_retorno_saida_hora').value = last.saida_hora || (fallbackRetorno && fallbackRetorno.saida_hora) || '';
    setRoteiroDatePickerValue('id_retorno_chegada_data', 'id_retorno_chegada_data_display', last.chegada_data || (fallbackRetorno && fallbackRetorno.chegada_data) || '');
    $('id_retorno_chegada_hora').value = last.chegada_hora || (fallbackRetorno && fallbackRetorno.chegada_hora) || '';
    $('id_retorno_tempo_cru_estimado_min').value = last.tempo_cru_estimado_min || '';
    $('id_retorno_tempo_adicional_min').value = last.tempo_adicional_min || '0';
    var raHx = $('id_retorno_tempo_adicional_hhmm');
    if (raHx) {
      var am0 = parseInt($('id_retorno_tempo_adicional_min').value || 0, 10) || 0;
      raHx.value = am0 ? formatDurationInput(am0) : '';
    }
    $('id_retorno_duracao_estimada_min').value = last.duracao_estimada_min || '';
  }
  function splitLoopTrechosAndRetorno(trechos) {
    // No bate-volta diario, o ultimo deslocamento gerado representa o retorno final.
    // Ele alimenta o bloco proprio de Retorno e nao deve renderizar como trecho comum.
    var items = Array.isArray(trechos) ? trechos.slice() : [];
    if (!items.length) return { trechos: [], retorno: null };
    return { trechos: items.slice(0, -1), retorno: items[items.length - 1] };
  }
  function computeTrechosSignature(seedState) {
    var destinos = getDestinos().map(function(destino) {
      return [destino.estado_id || '', destino.cidade_id || ''].join(':');
    }).join('|');
    if (isLoopModeActive(seedState)) {
      return [
        'loop',
        $('id_origem_estado').value || '',
        $('id_origem_cidade').value || '',
        destinos,
        ($('id_bate_volta_data_inicio_native') || {}).value || '',
        ($('id_bate_volta_data_fim_native') || {}).value || '',
        $('id_bate_volta_ida_saida_hora').value || '',
        $('id_bate_volta_ida_tempo_min').value || '',
        $('id_bate_volta_volta_saida_hora').value || '',
        $('id_bate_volta_volta_tempo_min').value || ''
      ].join('::');
    }
    return [
      'normal',
      $('id_origem_estado').value || '',
      $('id_origem_cidade').value || '',
      destinos
    ].join('::');
  }
  function scheduleLoopTrechosRender(options) {
    clearTimeout(loopRenderTimer);
    loopRenderTimer = setTimeout(function() {
      renderTrechos(captureCurrentState(), options || { preferSeed: true, force: true });
      scheduleRealtimeDiarias();
    }, 160);
  }
  function clearLoopGeneratedTrechos() {
    // Ao sair do bate-volta, remove os trechos/retorno gerados pelo loop
    // e remonta a partir de sede+destinos (modo normal).
    mountTrechosHtml(getTrechosEmptyHtml());
    [
      'id_retorno_saida_data',
      'id_retorno_saida_hora',
      'id_retorno_chegada_data',
      'id_retorno_chegada_hora',
      'id_retorno_distancia_km',
      'id_retorno_tempo_cru_estimado_min',
      'id_retorno_duracao_estimada_min',
      'id_retorno_tempo_viagem_hhmm',
      'id_retorno_tempo_adicional_hhmm'
    ].forEach(function(id) {
      if ($(id)) $(id).value = '';
    });
    if ($('id_retorno_tempo_adicional_min')) $('id_retorno_tempo_adicional_min').value = '0';
    if ($('id_retorno_rota_fonte')) $('id_retorno_rota_fonte').value = '';
    lastTrechosSignature = '';
    renderTrechos(captureCurrentState(), { preferSeed: false, force: true });
    scheduleRealtimeDiarias();
    notifyRouteStateChanged();
  }
  function selectedText(el) { return el && el.selectedIndex >= 0 && el.options[el.selectedIndex] ? String(el.options[el.selectedIndex].text || '').trim() : ''; }
  function makeStableKey(prefix) {
    if (window.crypto && window.crypto.randomUUID) return prefix + '-' + window.crypto.randomUUID();
    return prefix + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }
  function loadCities(select, estadoId, selectedId) {
    return window.CV.locationRows.loadCities({
      citySelect: select,
      stateId: estadoId,
      selectedId: selectedId,
      cache: citiesCache,
      scope: select ? select.parentNode : form,
      requestAttr: 'roteiroCitiesRequest',
      urlForState: function(stateId) { return cidadesUrl(stateId); }
    });
  }
  function currentTrechosMap() {
    // Preserva campos manuais usando a chave estavel do trecho; a ordem visual pode mudar.
    var map = {};
    getTrechoCards().forEach(function(card) {
      var o = card.dataset.ordem;
      map[card.dataset.key] = { id: card.dataset.trechoId || '', ordem: parseInt(o, 10) || 0, origem_nome: card.dataset.origemNome || '', destino_nome: card.dataset.destinoNome || '',
        origem_estado_id: card.dataset.origemEstadoId || '', origem_cidade_id: card.dataset.origemCidadeId || '',
        destino_estado_id: card.dataset.destinoEstadoId || '', destino_cidade_id: card.dataset.destinoCidadeId || '',
        saida_data: (card.querySelector('[name="trecho_' + o + '_saida_data"]') || {}).value || '',
        saida_hora: (card.querySelector('[name="trecho_' + o + '_saida_hora"]') || {}).value || '',
        chegada_data: (card.querySelector('[name="trecho_' + o + '_chegada_data"]') || {}).value || '',
        chegada_hora: (card.querySelector('[name="trecho_' + o + '_chegada_hora"]') || {}).value || '',
        distancia_km: (card.querySelector('[name="trecho_' + o + '_distancia_km"]') || {}).value || '',
        tempo_cru_estimado_min: (card.querySelector('[name="trecho_' + o + '_tempo_cru_estimado_min"]') || {}).value || '',
        tempo_adicional_min: (card.querySelector('[name="trecho_' + o + '_tempo_adicional_min"]') || {}).value || '0',
        duracao_estimada_min: (card.querySelector('[name="trecho_' + o + '_duracao_estimada_min"]') || {}).value || '',
        rota_fonte: (card.querySelector('[name="trecho_' + o + '_rota_fonte"]') || {}).value || '' };
    }); return map;
  }
  function stateTrechosMap(state) {
    // Compatibilidade: dados antigos podem chegar indexados por id/cidade,
    // mas a chave estavel continua tendo prioridade quando existir.
    var map = {};
    ((state && state.trechos) || []).forEach(function(t) {
      var keys = [
        t.key,
        t.destino_key,
        t.id,
        t.destino_cidade_id,
        String(t.origem_cidade_id || '') + '->' + String(t.destino_cidade_id || '')
      ];
      keys.forEach(function(key) { if (key != null && String(key) !== '') map[String(key)] = t; });
    });
    return map;
  }
  function recalcCard(card, suggestArrival) {
    var o = card.dataset.ordem;
    var cruInput = card.querySelector('[name="trecho_' + o + '_tempo_cru_estimado_min"]');
    var tvInput = card.querySelector('.trecho-tempo-viagem-hhmm');
    var addInput = card.querySelector('[name="trecho_' + o + '_tempo_adicional_min"]');
    var durInput = card.querySelector('[name="trecho_' + o + '_duracao_estimada_min"]');
    if (tvInput) {
      var norm = normalizeDurationInput(tvInput.value);
      var parsed = parseDurationInput(norm);
      var cruAtual = parseInt((cruInput || {}).value || 0, 10) || 0;
      if (document.activeElement === tvInput) {
        if (norm !== tvInput.value) tvInput.value = norm;
        if (cruInput) cruInput.value = parsed != null ? String(parsed) : '';
      } else if (cruAtual > 0) {
        tvInput.value = formatDurationInput(cruAtual);
      } else if (parsed != null && parsed > 0) {
        if (cruInput) cruInput.value = String(parsed);
      } else {
        tvInput.value = '';
      }
    }
    var addHhmm = card.querySelector('.trecho-tempo-adicional-hhmm');
    var add = 0;
    if (addHhmm && document.activeElement === addHhmm) {
      var na = normalizeDurationInput(addHhmm.value);
      var pa = parseDurationInput(na);
      if (na !== addHhmm.value) addHhmm.value = na;
      add = pa != null ? pa : 0;
      if (addInput) {
        addInput.value = String(add);
        addInput.dataset.manual = '1';
      }
    } else if (addInput) {
      add = parseInt(addInput.value || 0, 10);
      if (Number.isNaN(add) || add < 0) add = 0;
      addInput.value = String(add);
      if (addHhmm && document.activeElement !== addHhmm) {
        addHhmm.value = add ? formatDurationInput(add) : '';
      }
    }
    var cru = parseInt((cruInput || {}).value || 0, 10) || 0;
    var total = cru + add;
    card.dataset.tempoCruMin = cru ? String(cru) : ''; card.dataset.tempoTotalMin = total ? String(total) : '';
    if (durInput) durInput.value = total ? String(total) : '';
    if (tvInput && document.activeElement !== tvInput) tvInput.value = cru > 0 ? formatDurationInput(cru) : '';
    var totEl = card.querySelector('.trecho-tempo-total');     if (totEl) totEl.value = total ? hhmm(total) : '';
    var sdEl = card.querySelector('[name="trecho_' + o + '_saida_data"]');
    var shEl = card.querySelector('[name="trecho_' + o + '_saida_hora"]');
    var chEl = card.querySelector('[name="trecho_' + o + '_chegada_hora"]');
    if (suggestArrival && sdEl && shEl) {
      // `silent` é obrigatório aqui: o `change` do hidden de chegada sobe até o
      // listener do container, que chama `recalcCard` de novo — e a recursão só
      // termina quando a pilha estoura. Quem chama `recalcCard` já dispara
      // `updateResumo`/`scheduleRealtimeDiarias`/`scheduleAutosave` por conta.
      if (!sdEl.value || !shEl.value) {
        setTrechoDateValue(card, 'chegada', '', { silent: true });
        if (chEl) chEl.value = '';
      } else if (total > 0) {
        var cheg = calcularChegada(sdEl.value, shEl.value, cru, add);
        if (cheg) {
          setTrechoDateValue(card, 'chegada', cheg.data, { silent: true });
          if (chEl) chEl.value = cheg.hora;
        }
      } else {
        setTrechoDateValue(card, 'chegada', '', { silent: true });
        if (chEl) chEl.value = '';
      }
    }
  }
  function recalcRetorno(suggestArrival) {
    var cruI = $('id_retorno_tempo_cru_estimado_min'); var tvI = $('id_retorno_tempo_viagem_hhmm');
    var addI = $('id_retorno_tempo_adicional_min'); var durI = $('id_retorno_duracao_estimada_min');
    if (tvI) {
      var n2 = normalizeDurationInput(tvI.value);
      var p2 = parseDurationInput(n2);
      var cruAtual2 = parseInt((cruI || {}).value || 0, 10) || 0;
      if (document.activeElement === tvI) {
        if (n2 !== tvI.value) tvI.value = n2;
        if (cruI) cruI.value = p2 != null ? String(p2) : '';
      } else if (cruAtual2 > 0) {
        tvI.value = formatDurationInput(cruAtual2);
      } else if (p2 != null && p2 > 0) {
        if (cruI) cruI.value = String(p2);
      } else {
        tvI.value = '';
      }
    }
    var addH = $('id_retorno_tempo_adicional_hhmm');
    var add2 = 0;
    if (addH && document.activeElement === addH) {
      var n3 = normalizeDurationInput(addH.value);
      var p3 = parseDurationInput(n3);
      if (n3 !== addH.value) addH.value = n3;
      add2 = p3 != null ? p3 : 0;
      if (addI) {
        addI.value = String(add2);
        addI.dataset.manual = '1';
      }
    } else if (addI) {
      add2 = parseInt(addI.value || 0, 10);
      if (Number.isNaN(add2) || add2 < 0) add2 = 0;
      addI.value = String(add2);
      if (addH && document.activeElement !== addH) {
        addH.value = add2 ? formatDurationInput(add2) : '';
      }
    }
    if (cruI && String(cruI.value || '').trim() === '') {
      var sd = $('id_retorno_saida_data').value || ''; var sh = $('id_retorno_saida_hora').value || '';
      var cd = $('id_retorno_chegada_data').value || ''; var ch = $('id_retorno_chegada_hora').value || '';
      if (sd && sh && cd && ch) { var sD = new Date(sd+'T'+sh); var eD = new Date(cd+'T'+ch); if (!Number.isNaN(sD.getTime()) && !Number.isNaN(eD.getTime()) && eD >= sD) { var dc = Math.round((eD - sD) / 60000); if (cruI) cruI.value = dc > 0 ? String(dc) : ''; } }
    }
    var cru2 = parseInt((cruI || {}).value || 0, 10) || 0;
    if (addI) {
      add2 = parseInt(addI.value || 0, 10);
      if (Number.isNaN(add2) || add2 < 0) add2 = 0;
      addI.value = String(add2);
    }
    if (addH && document.activeElement !== addH) {
      addH.value = add2 ? formatDurationInput(add2) : '';
    }
    var tot2 = cru2 + add2; if (durI) durI.value = tot2 ? String(tot2) : '';
    if (tvI && document.activeElement !== tvI) tvI.value = cru2 > 0 ? formatDurationInput(cru2) : '';
    if ($('id_retorno_tempo_total')) $('id_retorno_tempo_total').value = tot2 ? hhmm(tot2) : '';
    if (suggestArrival && $('id_retorno_saida_data') && $('id_retorno_saida_hora') && $('id_retorno_chegada_data') && $('id_retorno_chegada_hora')) {
      var rsd = $('id_retorno_saida_data').value;
      var rsh = $('id_retorno_saida_hora').value;
      if (!rsd || !rsh || tot2 <= 0) {
        $('id_retorno_chegada_data').value = '';
        $('id_retorno_chegada_hora').value = '';
      } else {
        var rCheg = calcularChegada(rsd, rsh, cru2, add2);
        if (rCheg) {
          $('id_retorno_chegada_data').value = rCheg.data;
          $('id_retorno_chegada_hora').value = rCheg.hora;
        }
      }
    }
  }
  function canCalculateRoutePreview() {
    if (isLoopModeActive()) return false;
    var sedeCidade = ($('id_origem_cidade') || {}).value || '';
    var destinos = getDestinos().filter(function(d) { return d && d.cidade_id; });
    return !!(sedeCidade && destinos.length);
  }
  function buildRoutePreviewPayload() {
    var origemCidadeId = parseInt((($('id_origem_cidade') || {}).value || ''), 10);
    if (!origemCidadeId) return null;
    var destinos = getDestinos()
      .filter(function(d) { return d && d.cidade_id; })
      .map(function(d, idx) {
        return {
          uuid: String(d.key || ('tmp-' + (idx + 1))),
          cidade_id: parseInt(d.cidade_id, 10),
        };
      });
    if (!destinos.length) return null;
    var retornoCard = $('retorno-card');
    var retornoCidadeId = NaN;
    if (retornoCard && retornoCard.dataset.destinoCidadeId) {
      retornoCidadeId = parseInt(retornoCard.dataset.destinoCidadeId, 10);
    } else {
      retornoCidadeId = origemCidadeId;
    }
    var incluirRetorno = !!(
      origemCidadeId &&
      destinos.length &&
      !Number.isNaN(retornoCidadeId)
    );
    return {
      origem_cidade_id: origemCidadeId,
      destinos: destinos,
      retorno_cidade_id: Number.isNaN(retornoCidadeId) ? null : retornoCidadeId,
      incluir_retorno: incluirRetorno,
      modo: isLoopModeActive() ? 'bate_volta' : 'normal',
    };
  }
  function applyRoutePreviewResult(result, options) {
    var opts = options || {};
    var overwriteAdditional = !!opts.overwriteAdditional;
    var legs = (result && result.legs) || [];
    legs.forEach(function(leg) {
      var travelMinutes = parseInt(leg.travel_minutes, 10);
      if (Number.isNaN(travelMinutes)) {
        travelMinutes = parseDurationInput(leg.travel_hhmm || '') || 0;
      }
      var additionalMinutes = parseInt(leg.additional_minutes, 10);
      if (Number.isNaN(additionalMinutes)) additionalMinutes = 0;
      var totalMinutes = parseInt(leg.total_minutes, 10);
      if (Number.isNaN(totalMinutes)) totalMinutes = travelMinutes + additionalMinutes;
      if (leg.kind === 'retorno') {
        if ($('id_retorno_distancia_km') && leg.distance_km != null) $('id_retorno_distancia_km').value = String(leg.distance_km);
        if ($('id_retorno_tempo_cru_estimado_min') && travelMinutes > 0) $('id_retorno_tempo_cru_estimado_min').value = String(travelMinutes);
        if ($('id_retorno_tempo_viagem_hhmm') && travelMinutes > 0 && document.activeElement !== $('id_retorno_tempo_viagem_hhmm')) {
          $('id_retorno_tempo_viagem_hhmm').value = leg.travel_hhmm || formatDurationInput(travelMinutes);
        }
        if ($('id_retorno_rota_fonte') && leg.provider) $('id_retorno_rota_fonte').value = leg.provider;
        if ($('id_retorno_duracao_estimada_min') && totalMinutes > 0) $('id_retorno_duracao_estimada_min').value = String(totalMinutes);
        if ($('id_retorno_tempo_total') && totalMinutes > 0) $('id_retorno_tempo_total').value = leg.total_hhmm || hhmm(totalMinutes);
        var addRet = $('id_retorno_tempo_adicional_min');
        if (addRet && (overwriteAdditional || String(addRet.value || '').trim() === '' || addRet.dataset.manual !== '1')) {
          addRet.value = String(additionalMinutes);
          if (overwriteAdditional) addRet.dataset.manual = '0';
        }
        recalcRetorno(true);
        return;
      }
      var card = $('trechos-gerados-container').querySelector(
        '.roteiro-trecho-card[data-key="' + String(leg.uuid || '') + '"]'
      );
      if (!card) {
        card = getTrechoCards().find(function(c) {
          return String(c.dataset.origemCidadeId || '') === String(leg.from_cidade_id || '') &&
            String(c.dataset.destinoCidadeId || '') === String(leg.to_cidade_id || '');
        });
      }
      if (!card && Number.isInteger(leg.index)) {
        card = $('trechos-gerados-container').querySelector(
          '.roteiro-trecho-card[data-ordem="' + String(leg.index) + '"]'
        );
      }
      if (!card) return;
      var ord = card.dataset.ordem;
      var distInp = card.querySelector('[name="trecho_' + ord + '_distancia_km"]');
      var cruInp = card.querySelector('[name="trecho_' + ord + '_tempo_cru_estimado_min"]');
      var tvInp = card.querySelector('.trecho-tempo-viagem-hhmm');
      var fonteInp = card.querySelector('[name="trecho_' + ord + '_rota_fonte"]');
      var durInp = card.querySelector('[name="trecho_' + ord + '_duracao_estimada_min"]');
      var addInp = card.querySelector('[name="trecho_' + ord + '_tempo_adicional_min"]');
      var totalInp = card.querySelector('.trecho-tempo-total');
      if (distInp && leg.distance_km != null) distInp.value = String(leg.distance_km);
      if (cruInp && travelMinutes > 0) cruInp.value = String(travelMinutes);
      if (tvInp && travelMinutes > 0 && document.activeElement !== tvInp) {
        tvInp.value = leg.travel_hhmm || formatDurationInput(travelMinutes);
      }
      if (fonteInp && leg.provider) fonteInp.value = leg.provider;
      if (durInp && totalMinutes > 0) durInp.value = String(totalMinutes);
      if (totalInp && totalMinutes > 0) totalInp.value = leg.total_hhmm || hhmm(totalMinutes);
      if (addInp && (overwriteAdditional || String(addInp.value || '').trim() === '' || addInp.dataset.manual !== '1')) {
        addInp.value = String(additionalMinutes);
        if (overwriteAdditional) addInp.dataset.manual = '0';
      }
      recalcCard(card, true);
    });
    updateResumo();
    scheduleRealtimeDiarias();
    scheduleAutosave();
    notifyRouteStateChanged();
  }
  function applyEstimarPayloadToRetorno(data) {
    if ($('id_retorno_distancia_km') && data.distancia_km != null) $('id_retorno_distancia_km').value = String(data.distancia_km);
    if ($('id_retorno_tempo_cru_estimado_min') && data.tempo_cru_estimado_min != null) {
      $('id_retorno_tempo_cru_estimado_min').value = String(data.tempo_cru_estimado_min);
    }
    if ($('id_retorno_duracao_estimada_min') && data.duracao_estimada_min != null) {
      $('id_retorno_duracao_estimada_min').value = String(data.duracao_estimada_min);
    }
    if ($('id_retorno_rota_fonte') && data.rota_fonte) $('id_retorno_rota_fonte').value = data.rota_fonte;
    var addI = $('id_retorno_tempo_adicional_min');
    if (addI && data.tempo_adicional_sugerido_min != null && String(addI.value || '').trim() === '') {
      addI.value = String(data.tempo_adicional_sugerido_min);
    }
    recalcRetorno(true);
  }
  function applyEstimarPayloadToTrechoCard(card, data) {
    var ord = card.dataset.ordem;
    var distInp = card.querySelector('[name="trecho_' + ord + '_distancia_km"]');
    if (distInp && data.distancia_km != null) distInp.value = String(data.distancia_km);
    var cruInp = card.querySelector('[name="trecho_' + ord + '_tempo_cru_estimado_min"]');
    if (cruInp && data.tempo_cru_estimado_min != null) cruInp.value = String(data.tempo_cru_estimado_min);
    var fonteInp = card.querySelector('[name="trecho_' + ord + '_rota_fonte"]');
    if (fonteInp && data.rota_fonte) fonteInp.value = data.rota_fonte;
    var durInp = card.querySelector('[name="trecho_' + ord + '_duracao_estimada_min"]');
    if (durInp && data.duracao_estimada_min != null) durInp.value = String(data.duracao_estimada_min);
    var addInp = card.querySelector('[name="trecho_' + ord + '_tempo_adicional_min"]');
    if (addInp && data.tempo_adicional_sugerido_min != null && String(addInp.value || '').trim() === '') {
      addInp.value = String(data.tempo_adicional_sugerido_min);
    }
    recalcCard(card, true);
  }
  /* JS-04 — a faixa de erro dos trechos. Mesmo par de `roteiros-map.js`, que é
     o idioma da casa para erro assíncrono: texto inline, não modal. */
  function clearTrechosError() {
    var box = $('trechos-error');
    if (!box) return;
    box.textContent = '';
    box.hidden = true;
  }
  function showTrechosError(msg) {
    var box = $('trechos-error');
    if (!box) return;
    box.textContent = msg;
    box.hidden = false;
  }
  function scheduleAutoEstimarTrechos() {
    clearTimeout(autoEstimarTimer);
    autoEstimarTimer = setTimeout(runAutoEstimarTrechos, 450);
  }
  function runAutoEstimarTrechos() {
    if (!urlTrechosEstimar || applyingState || isLoopModeActive()) return Promise.resolve();
    var cards = getTrechoCards();
    var pending = cards.filter(function(card) {
      var distInp = card.querySelector('[name^="trecho_"][name$="_distancia_km"]');
      var cruInp = card.querySelector('[name^="trecho_"][name$="_tempo_cru_estimado_min"]');
      if (distInp && String(distInp.value || '').trim() !== '') return false;
      if (cruInp && String(cruInp.value || '').trim() !== '') return false;
      var ocid = card.dataset.origemCidadeId;
      var dcid = card.dataset.destinoCidadeId;
      return !!(ocid && dcid);
    });
    if (!pending.length) return Promise.resolve();
    clearTrechosError();
    var falhas = 0;
    return pending.reduce(function(seq, card) {
      return seq.then(function() {
        var ocid = card.dataset.origemCidadeId;
        var dcid = card.dataset.destinoCidadeId;
        return window.CV.http.fetchJson(urlTrechosEstimar, {
          method: 'POST',
          form: form,
          body: { origem_cidade_id: parseInt(ocid, 10), destino_cidade_id: parseInt(dcid, 10) }
        }).then(function(result) {
          /* Normaliza por `throw`, como `calculateDiarias`: status HTTP e o
             `ok` do payload viram o mesmo erro, com a mensagem do servidor.
             Antes só `data.ok` era lido, e `data.error` ia para o lixo — 500,
             401 de sessão expirada e resposta não-JSON saíam todos calados. */
          var data = result && result.data;
          if (!result.ok || !data || !data.ok) {
            throw new Error((data && data.error) || 'Não foi possível estimar este trecho.');
          }
          applyEstimarPayloadToTrechoCard(card, data);
          updateResumo();
          scheduleRealtimeDiarias();
          scheduleAutosave();
        }).catch(function(err) {
          /* O `.catch` fica DENTRO do elo de propósito. Antes não havia nenhum:
             a rejeição de um card propagava pelo `reduce` e cancelava todos os
             trechos seguintes da fila, não só o que falhou. */
          falhas += 1;
          window.CV.log.error('roteiro-trechos', 'falha ao estimar trecho', err);
        });
      });
    }, Promise.resolve()).then(function() {
      if (!falhas) return;
      showTrechosError(
        (falhas === 1
          ? 'Não foi possível estimar a distância de um trecho.'
          : 'Não foi possível estimar a distância de ' + falhas + ' trechos.')
        + ' Preencha a distância e o tempo à mão, ou tente de novo alterando o destino.'
      );
    }).catch(function(err) {
      window.CV.log.error('roteiro-trechos', 'falha na fila de estimativa', err);
    });
  }
  function getDestinoRows() {
    var container = $('destinos-container');
    return container ? Array.from(container.querySelectorAll('[data-location-row]')) : [];
  }
  function syncDestinoRowChrome(row, idx) {
    if (!row) return;
    var ord = row.querySelector('[data-location-order]');
    if (ord) ord.textContent = String(idx + 1);
    var es = row.querySelector('[data-location-state]');
    var ci = row.querySelector('[data-location-city]');
    var esId = 'destino_estado_' + idx;
    var ciId = 'destino_cidade_' + idx;
    if (es) {
      es.name = esId;
      es.id = esId;
    }
    if (ci) {
      ci.name = ciId;
      ci.id = ciId;
    }
    var esLabel = row.querySelector('label[for^="destino_estado_"]');
    var ciLabel = row.querySelector('label[for^="destino_cidade_"]');
    if (esLabel) esLabel.setAttribute('for', esId);
    if (ciLabel) ciLabel.setAttribute('for', ciId);
  }
  function reindexDestinoRows() {
    window.CV.locationRows.reindexRows($('destinos-container'), {
      rowSelector: '[data-location-row]',
      indexAttr: 'locationIndex',
      onRow: function(row, idx) {
        syncDestinoRowChrome(row, idx);
      }
    });
  }
  function refreshDestinoButtons() {
    var container = $('destinos-container');
    window.CV.locationRows.updateSingleRowState(container, {
      rowSelector: '[data-location-row]',
      removeSelector: '[data-location-remove]'
    });
    var rows = getDestinoRows();
    rows.forEach(function (row, index) {
      var addBtn = row.querySelector('[data-location-add]');
      if (!addBtn) return;
      addBtn.hidden = false;
      if (index === 0 && !addBtn.id) addBtn.id = 'btn-adicionar-destino';
      if (index !== 0 && addBtn.id === 'btn-adicionar-destino') addBtn.removeAttribute('id');
    });
  }
  function addDestinoRow(destino, options) {
    var container = $('destinos-container');
    if (!container) return Promise.resolve(null);
    options = options || {};
    var insertAfter = options.insertAfter || null;
    var idx = getDestinoRows().length;
    var estadoId = destino && destino.estado_id ? destino.estado_id : (destinoEstadoDefaultId || '');
    var cidadeId = destino && destino.cidade_id ? destino.cidade_id : null;
    var stableKey = (destino && (destino.key || destino.destino_key || destino.id))
      ? String(destino.key || destino.destino_key || destino.id)
      : makeStableKey('destino');
    var row = window.CV.locationRows.appendTemplateRow({
      list: container,
      template: $('tmpl-destino-roteiro'),
      index: idx,
      rowSelector: '[data-location-row]',
      removeSelector: '[data-location-remove]',
      indexAttr: 'locationIndex',
      insertAfter: insertAfter,
      beforeAppend: function (newRow) {
        if (!newRow) return;
        newRow.dataset.key = stableKey;
        var state = newRow.querySelector('[data-location-state]');
        if (state) state.value = String(estadoId || '');
      },
    });
    if (!row) return Promise.resolve(null);
    row.draggable = false;
    row.dataset.key = stableKey;
    var cidade = row.querySelector('[data-location-city]');
    refreshSelectPickers(row);
    var promise = estadoId ? loadCities(cidade, estadoId, cidadeId) : Promise.resolve();
    return promise.then(function() {
      reindexDestinoRows();
      refreshDestinoButtons();
      return row;
    });
  }
  function renderDestinos(destinos) {
    var container = $('destinos-container');
    if (!container) return Promise.resolve([]);
    container.innerHTML = '';
    var items = Array.isArray(destinos) && destinos.length ? destinos : [{ estado_id: destinoEstadoDefaultId || null, cidade_id: null }];
    var chain = Promise.resolve();
    items.forEach(function(item) {
      chain = chain.then(function() { return addDestinoRow(item || {}); });
    });
    return chain.then(function() {
      refreshDestinoButtons();
      return items;
    });
  }
  function getDestinos() {
    return getDestinoRows().map(function(row) {
      var es = row.querySelector('[data-location-state]');
      var ci = row.querySelector('[data-location-city]');
      return {
        key: row.dataset.key || '',
        estado_id: es ? es.value || null : null,
        cidade_id: ci ? ci.value || null : null,
        cidade_nome: selectedText(ci)
      };
    });
  }

  function renderDestinosTrechosPreview() {
    if (!window.CV || !window.CV.locationRows || typeof window.CV.locationRows.renderTrechosPreview !== "function") {
      return;
    }
    window.CV.locationRows.renderTrechosPreview({
      section: document.querySelector("#sec-destinos") || document.querySelector(".route-destinos-block"),
      getOriginLabel: function () {
        return selectedText($("id_origem_cidade"));
      },
      originFallback: "Sede",
    });
  }

  function updateRetornoCities() {
    var cards = getTrechoCards();
    var sede = selectedText($('id_origem_cidade'));
    var sedeId = ($('id_origem_cidade') || {}).value || '';
    var ultima = cards.length ? (cards[cards.length-1].dataset.destinoNome||'') : '';
    var lastDestId = cards.length ? (cards[cards.length-1].dataset.destinoCidadeId||'') : '';
    if ($('id_retorno_saida_cidade')) $('id_retorno_saida_cidade').value = ultima;
    if ($('id_retorno_chegada_cidade')) $('id_retorno_chegada_cidade').value = sede;
    var rc = $('retorno-card');
    if (rc) {
      rc.dataset.origemCidadeId = lastDestId || '';
      rc.dataset.destinoCidadeId = sedeId || '';
    }
  }
  function getTrechosDatePicker() {
    return $('trechos-date-picker');
  }
  function formatIsoDateToDisplay(isoDate) {
    var raw = String(isoDate || '').trim();
    if (!raw) return '';
    var match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return raw;
    return match[3] + '/' + match[2] + '/' + match[1];
  }
  function setRoteiroDatePickerValue(hiddenId, displayId, isoDate) {
    var hidden = $(hiddenId);
    var display = $(displayId);
    var picker = null;
    if (hidden && hidden.closest) {
      picker = hidden.closest('[data-cv-date-picker]');
    }
    if (!picker && display && display.closest) {
      picker = display.closest('[data-cv-date-picker]');
    }
    if (picker && picker._cvDatePicker && typeof picker._cvDatePicker.setSingle === 'function') {
      picker._cvDatePicker.setSingle(isoDate || '');
      return;
    }
    if (hidden) hidden.value = isoDate || '';
    if (display) display.value = formatIsoDateToDisplay(isoDate);
  }
  function syncTrechosDatePickerLimit() {
    var picker = getTrechosDatePicker();
    if (!picker) return;
    var cards = getTrechoCards();
    var expected = cards.length ? (cards.length + 1) : 0;
    picker.dataset.maxDates = String(expected);
    picker.dataset.routeSteps = JSON.stringify(buildTrechosRouteSteps(cards));
  }
  function buildTrechosRouteSteps(cards) {
    var items = Array.isArray(cards) ? cards : getTrechoCards();
    var origin = selectedText($('id_origem_cidade')) || (items[0] && items[0].dataset.origemNome) || '';
    if (!origin || !items.length) return [];
    var steps = [];
    var from = origin;
    items.forEach(function(card) {
      var to = String(card.dataset.destinoNome || '').trim();
      steps.push({
        from: from,
        to: to,
        label: (from || '') + ' > ' + (to || ''),
      });
      from = to || from;
    });
    steps.push({
      from: from,
      to: origin,
      label: (from || '') + ' > ' + origin,
      is_return: true,
    });
    return steps.filter(function(step) {
      return !!String(step.from || '').trim() && !!String(step.to || '').trim();
    });
  }
  function applyTrechosDateSelection(dates) {
    var cards = getTrechoCards();
    var expected = cards.length ? (cards.length + 1) : 0;
    var selectedDates = Array.isArray(dates)
      ? dates.map(function(date) { return String(date || '').trim(); }).filter(function(date) { return !!date; })
      : [];
    if (!expected || selectedDates.length !== expected) {
      return false;
    }
    var prevApplyingState = applyingState;
    applyingState = true;
    try {
      cards.forEach(function(card, idx) {
        setTrechoDateValue(card, 'saida', selectedDates[idx], { silent: true });
        recalcCard(card, true);
        setTrechoDateValue(card, 'chegada', selectedDates[idx], { silent: true });
      });
      updateRetornoCities();
      setRoteiroDatePickerValue('id_retorno_saida_data', 'id_retorno_saida_data_display', selectedDates[cards.length] || '');
      setRoteiroDatePickerValue('id_retorno_chegada_data', 'id_retorno_chegada_data_display', selectedDates[cards.length] || '');
      recalcRetorno(false);
    } finally {
      applyingState = prevApplyingState;
    }
    updateResumo();
    scheduleRealtimeDiarias();
    scheduleAutosave();
    notifyRouteStateChanged();
    return true;
  }
  function renderTrechos(seedState, options) {
    renderDestinosTrechosPreview();
    // Re-renderizar trechos nao pode sobrescrever data/hora/tempo manual com vazio/default.
    // Por isso os valores atuais da tela sao combinados com o seed antes de montar os cards.
    var opts = options || {};
    var preferSeed = !!opts.preferSeed;
    var force = !!opts.force;
    toggleBateVoltaPanel();
    syncBateVoltaDurationInputs();
    var signature = computeTrechosSignature(seedState);
    if (!force && !preferSeed && signature === lastTrechosSignature) {
      updateResumo();
      renderDestinosTrechosPreview();
      return;
    }

    if (shouldUseExactTrechos(seedState)) {
      var explicitTrechos = isLoopModeActive(seedState) ? buildLoopTrechosFromInputs() : [];
      var loopRetorno = null;
      if (isLoopModeActive(seedState) && explicitTrechos.length) {
        var splitLoop = splitLoopTrechosAndRetorno(explicitTrechos);
        explicitTrechos = splitLoop.trechos;
        loopRetorno = splitLoop.retorno;
      }
      if (!explicitTrechos.length) {
        explicitTrechos = ((seedState && seedState.trechos) || []).map(function(trecho, idx) {
          var copy = Object.assign({}, trecho);
          copy.ordem = idx;
          return copy;
        });
      }
      if (!explicitTrechos.length) {
        mountTrechosHtml(getTrechosEmptyHtml());
        updateRetornoCities();
        recalcRetorno(false);
        updateResumo();
        syncTrechosDatePickerLimit();
        lastTrechosSignature = signature;
        notifyRouteStateChanged();
        return;
      }
      mountTrechosHtml(
        explicitTrechos
          .map(function(trecho, idx) {
            return buildTrechoCard(
              {
                ordem: idx,
                key: String(
                  trecho.key ||
                    trecho.destino_key ||
                    trecho.id ||
                    'explicit-' +
                      idx +
                      '-' +
                      String(trecho.origem_cidade_id || '') +
                      '->' +
                      String(trecho.destino_cidade_id || '')
                ),
                id: trecho.id || '',
                origem_estado_id: trecho.origem_estado_id,
                origem_cidade_id: trecho.origem_cidade_id,
                destino_estado_id: trecho.destino_estado_id,
                destino_cidade_id: trecho.destino_cidade_id,
                origem_nome: trecho.origem_nome || '',
                destino_nome: trecho.destino_nome || '',
              },
              Object.assign({}, trecho, { ordem: idx }),
              window.CV.util.escapeHtml,
              formatDurationInput
            );
          })
          .join('')
      );
      getTrechoCards().forEach(function(card) {
        recalcCard(card, false);
      });
      if (isLoopModeActive(seedState)) {
        syncRetornoFromLoopTrechos(loopRetorno ? [loopRetorno] : [], seedState && seedState.retorno);
      } else {
        updateRetornoCities();
      }
      recalcRetorno(false);
      updateResumo();
      syncTrechosDatePickerLimit();
      scheduleAutoEstimarTrechos();
      lastTrechosSignature = signature;
      notifyRouteStateChanged();
      return;
    }

    var sedeEid = $('id_origem_estado').value || null;
    var sedeCid = $('id_origem_cidade').value || null;
    var sedeNome = selectedText($('id_origem_cidade'));
    var destinos = getDestinos().filter(function(d) { return d.estado_id && d.cidade_id; });
    if (!sedeEid || !sedeCid || !destinos.length) {
      mountTrechosHtml(getTrechosEmptyHtml());
      updateRetornoCities();
      recalcRetorno(false);
      updateResumo();
      syncTrechosDatePickerLimit();
      lastTrechosSignature = signature;
      notifyRouteStateChanged();
      return;
    }
    var cm = currentTrechosMap();
    var sm = stateTrechosMap(seedState || {});
    var trechos = [];
    var oeId = sedeEid;
    var ocId = sedeCid;
    var oNome = sedeNome;
    destinos.forEach(function(d, idx) {
      var key = String(d.key || d.cidade_id || (String(ocId || '') + '->' + String(d.cidade_id || '')));
      trechos.push({
        ordem: idx,
        key: key,
        origem_estado_id: oeId,
        origem_cidade_id: ocId,
        destino_estado_id: d.estado_id,
        destino_cidade_id: d.cidade_id,
        origem_nome: oNome,
        destino_nome: d.cidade_nome || ''
      });
      oeId = d.estado_id;
      ocId = d.cidade_id;
      oNome = d.cidade_nome || '';
    });
    mountTrechosHtml(
      trechos
        .map(function(t) {
          var cv = cm[t.key] || {};
          var sv = sm[t.key] || sm[String(t.destino_cidade_id || '')] || {};
          return buildTrechoCard(
            t,
            preferSeed ? Object.assign({}, cv, sv) : Object.assign({}, sv, cv),
            window.CV.util.escapeHtml,
            formatDurationInput
          );
        })
        .join('')
    );
    getTrechoCards().forEach(function(c) {
      recalcCard(c, false);
    });
    updateRetornoCities();
    recalcRetorno(false);
    updateResumo();
    syncTrechosDatePickerLimit();
    scheduleAutoEstimarTrechos();
    lastTrechosSignature = signature;
    notifyRouteStateChanged();
  }
  function updateResumo() {
    var cards = getTrechoCards();
    var totMin = 0; var totKm = 0;
    cards.forEach(function(c) { totMin += parseInt(c.dataset.tempoTotalMin||0,10)||0; var de = c.querySelector('[name$="_distancia_km"]'); if (de && de.value) { var v = parseFloat(de.value); if (!Number.isNaN(v)) totKm += v; } });
    form.dataset.resumoTrechos = String(cards.length);
    form.dataset.resumoKm = cards.length ? totKm.toFixed(2).replace('.',',')+' km' : '-';
    form.dataset.resumoTempo = cards.length ? hhmm(totMin) : '-';
  }
  function getSelectedRouteInput() {
    return form.querySelector('[data-route-selected-input]');
  }
  function getSelectedRouteId() {
    var input = getSelectedRouteInput();
    return input ? String(input.value || '') : '';
  }
  function setSelectedRouteId(value) {
    var input = getSelectedRouteInput();
    if (!input) return;
    input.value = value ? String(value) : '';
  }
  function captureCurrentState() {
    return {
      roteiro_modo: $('id_roteiro_modo_evento').checked ? 'EVENTO_EXISTENTE' : 'ROTEIRO_PROPRIO',
      roteiro_id: $('id_roteiro_modo_evento').checked ? (getSelectedRouteId() || null) : null,
      sede_estado_id: $('id_origem_estado').value||null, sede_cidade_id: $('id_origem_cidade').value||null,
      destinos_atuais: getDestinos(),
      bate_volta_diario: {
        ativo: (function() {
          var input = $('id_bate_volta_diario_ativo');
          if (!input) return false;
          if (input.type === 'checkbox') return !!input.checked;
          return String(input.value || '').toLowerCase() === 'true';
        })(),
        data_inicio: ($('id_bate_volta_data_inicio_native') || {}).value || '',
        data_fim: ($('id_bate_volta_data_fim_native') || {}).value || '',
        ida_saida_hora: ($('id_bate_volta_ida_saida_hora') || {}).value || '',
        ida_tempo_min: ($('id_bate_volta_ida_tempo_min') || {}).value || '',
        volta_saida_hora: ($('id_bate_volta_volta_saida_hora') || {}).value || '',
        volta_tempo_min: ($('id_bate_volta_volta_tempo_min') || {}).value || ''
      },
      trechos: getTrechoCards().map(function(c) {
        var o = parseInt(c.dataset.ordem||'0',10)||0;
        return { id: c.dataset.trechoId||'', key: c.dataset.key||'', ordem: o, origem_nome: c.dataset.origemNome||'', destino_nome: c.dataset.destinoNome||'',
          origem_estado_id: c.dataset.origemEstadoId||null, origem_cidade_id: c.dataset.origemCidadeId||null,
          destino_estado_id: c.dataset.destinoEstadoId||null, destino_cidade_id: c.dataset.destinoCidadeId||null,
          saida_data: (c.querySelector('[name="trecho_'+o+'_saida_data"]')||{}).value||'',
          saida_hora: (c.querySelector('[name="trecho_'+o+'_saida_hora"]')||{}).value||'',
          chegada_data: (c.querySelector('[name="trecho_'+o+'_chegada_data"]')||{}).value||'',
          chegada_hora: (c.querySelector('[name="trecho_'+o+'_chegada_hora"]')||{}).value||'',
          distancia_km: (c.querySelector('[name="trecho_'+o+'_distancia_km"]')||{}).value||'',
          tempo_cru_estimado_min: (c.querySelector('[name="trecho_'+o+'_tempo_cru_estimado_min"]')||{}).value||'',
          tempo_adicional_min: (c.querySelector('[name="trecho_'+o+'_tempo_adicional_min"]')||{}).value||'0',
          duracao_estimada_min: (c.querySelector('[name="trecho_'+o+'_duracao_estimada_min"]')||{}).value||'',
          rota_fonte: (c.querySelector('[name="trecho_'+o+'_rota_fonte"]')||{}).value||'' };
      }),
      retorno: { saida_cidade: $('id_retorno_saida_cidade').value||'', chegada_cidade: $('id_retorno_chegada_cidade').value||'',
        saida_data: $('id_retorno_saida_data').value||'', saida_hora: $('id_retorno_saida_hora').value||'',
        chegada_data: $('id_retorno_chegada_data').value||'', chegada_hora: $('id_retorno_chegada_hora').value||'',
        distancia_km: $('id_retorno_distancia_km').value||'', tempo_cru_estimado_min: $('id_retorno_tempo_cru_estimado_min').value||'',
        tempo_adicional_min: $('id_retorno_tempo_adicional_min').value||'0', duracao_estimada_min: $('id_retorno_duracao_estimada_min').value||'', rota_fonte: $('id_retorno_rota_fonte').value||'' }
    };
  }
  function clearRouteTrechos(options) {
    // Ao desmarcar um roteiro salvo, mantém a sede (padrão herdado do evento) mas limpa
    // destinos/trechos/retorno — trechos são derivados dos destinos (ver shouldUseExactTrechos),
    // então pra realmente sumir com o trecho da rota antiga é preciso zerar os dois juntos.
    var keepEventoMode = !!(options && options.keepEventoMode);
    var cur = captureCurrentState();
    cur.roteiro_modo = keepEventoMode ? 'EVENTO_EXISTENTE' : 'ROTEIRO_PROPRIO';
    cur.roteiro_id = null;
    cur.destinos_atuais = [];
    cur.trechos = [];
    cur.retorno = {
      saida_cidade: '', chegada_cidade: '',
      saida_data: '', saida_hora: '', chegada_data: '', chegada_hora: '',
      distancia_km: '', duracao_estimada_min: '', tempo_cru_estimado_min: '',
      tempo_adicional_min: 0, rota_fonte: ''
    };
    return applyState(cur).then(function() {
      if ($('id_retorno_saida_cidade')) $('id_retorno_saida_cidade').value = '';
      if ($('id_retorno_chegada_cidade')) $('id_retorno_chegada_cidade').value = '';
      // applyState não zera os campos de exibição (hh:mm) do tempo de retorno, e recalcRetorno
      // os usa como fallback pra re-derivar o tempo cru — sem isso o "Tempo de viagem" antigo volta.
      if ($('id_retorno_tempo_viagem_hhmm')) $('id_retorno_tempo_viagem_hhmm').value = '';
      if ($('id_retorno_tempo_adicional_hhmm')) $('id_retorno_tempo_adicional_hhmm').value = '';
      if ($('id_retorno_tempo_cru_estimado_min')) $('id_retorno_tempo_cru_estimado_min').value = '';
      recalcRetorno(false);
      if (window.CV.roteiros.map && typeof window.CV.roteiros.map.applyExternalRoute === 'function') {
        window.CV.roteiros.map.applyExternalRoute(null);
      }
    });
  }
  function applyRouteSelection(r) {
    return applyState(r.state).then(function() {
      if (window.CV.roteiros.map && typeof window.CV.roteiros.map.applyExternalRoute === 'function') {
        window.CV.roteiros.map.applyExternalRoute(r.state.mapa_rota || null);
      }
    });
  }
  function setDiariasStatus(state, text) {
    var status = $('diarias-status'); if (!status) return;
    status.dataset.state = state || 'pending';
    status.textContent = text || 'Aguardando dados para cálculo.';
    var chip = $('diarias-header-chip');
    if (chip) {
      if (state === 'updated') {
        chip.querySelector('.chip__label').textContent = text || 'Cálculo atualizado.';
        chip.classList.remove('d-none');
      } else {
        chip.classList.add('d-none');
      }
    }
  }
  function applyDiarias(result) {
    var totais = result && result.totais ? result.totais : null;
    var errEl = $('diarias-error');
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.add('d-none');
    }
    $('diarias-tipo').textContent = result && result.tipo_destino ? result.tipo_destino : '-';
    $('diarias-qtd').textContent = totais && totais.total_diarias ? totais.total_diarias : '-';
    $('diarias-valor').textContent = totais && totais.total_valor ? totais.total_valor : '-';
    $('diarias-extenso').textContent = totais && totais.valor_extenso ? totais.valor_extenso : 'Não informado';
    $('id_tipo_destino').value = result && result.tipo_destino ? result.tipo_destino : '';
    $('id_quantidade_diarias').value = totais && totais.total_diarias ? totais.total_diarias : '';
    $('id_valor_diarias').value = totais && totais.total_valor ? totais.total_valor : '';
    $('id_valor_diarias_extenso').value = totais && totais.valor_extenso ? totais.valor_extenso : '';
  }
  function clearDiariasAsPending() {
    var errEl = $('diarias-error');
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.add('d-none');
    }
    applyDiarias(null);
    setDiariasStatus('pending', 'Aguardando dados para cálculo.');
  }
  function markDiariasStale() {
    setDiariasStatus('stale', 'Cálculo desatualizado.');
  }
  function hasCompleteDataForDiarias(state) {
    if (!state || !state.sede_estado_id || !state.sede_cidade_id) return false;
    if (!Array.isArray(state.trechos) || !state.trechos.length) return false;
    for (var i = 0; i < state.trechos.length; i++) {
      var t = state.trechos[i] || {};
      if (!t.origem_estado_id || !t.origem_cidade_id || !t.destino_estado_id || !t.destino_cidade_id) return false;
      if (!t.saida_data || !t.saida_hora || !t.chegada_data || !t.chegada_hora) return false;
    }
    var ret = state.retorno || {};
    return !!(ret.saida_data && ret.saida_hora && ret.chegada_data && ret.chegada_hora);
  }
  function scheduleRealtimeDiarias() {
    markDiariasStale();
    var state = captureCurrentState();
    if (!hasCompleteDataForDiarias(state)) {
      clearTimeout(diariasTimer);
      clearDiariasAsPending();
      return;
    }
    clearTimeout(diariasTimer);
    diariasTimer = setTimeout(function() { calculateDiarias(); }, 700);
  }
  function collectDiariasFormData() {
    var fd = new FormData(form);
    fd.set('sede_estado', $('id_origem_estado').value || '');
    fd.set('sede_cidade', $('id_origem_cidade').value || '');
    return fd;
  }
  function calculateDiarias() {
    if (!apiDiarias) return Promise.resolve();
    if (diariasInFlight) { diariasNeedsRerun = true; return Promise.resolve(); }
    diariasInFlight = true;
    var errPre = $('diarias-error');
    if (errPre) {
      errPre.textContent = '';
      errPre.classList.add('d-none');
    }
    setDiariasStatus('pending', 'Calculando diárias...');
    return window.CV.http.fetchJson(apiDiarias, {
      method: 'POST',
      form: form,
      body: collectDiariasFormData()
    })
      .then(function(result) {
        if (!result.ok || !result.data || !result.data.ok) {
          var errs = (result.data && result.data.errors) || [];
          throw new Error(errs.join('\n') || ((result.data && result.data.error) || 'Erro ao calcular as diárias.'));
        }
        applyDiarias(result.data);
        var qsRaw = (($('id_quantidade_servidores') || {}).value || '1').trim();
        var qn = parseInt(qsRaw, 10);
        if (isNaN(qn)) qn = 1;
        var statusMsg =
          qn === 0
            ? 'Cálculo atualizado (nenhum viajante na Etapa 1 — valor total zerado).'
            : qn === 1
              ? 'Cálculo atualizado (1 servidor).'
              : 'Cálculo atualizado para ' + qn + ' servidores.';
        setDiariasStatus('updated', statusMsg);
      }).catch(function(err) {
        var msg = String((err && err.message) ? err.message : '').trim();
        if (!msg || msg === '.') {
          msg = 'Erro ao calcular as diárias.';
        }
        var errBox = $('diarias-error');
        if (errBox) {
          errBox.textContent = msg;
          errBox.classList.remove('d-none');
        }
        setDiariasStatus('error', 'Falha no cálculo.');
      }).finally(function() {
        diariasInFlight = false;
        if (diariasNeedsRerun) {
          diariasNeedsRerun = false;
          scheduleRealtimeDiarias();
        }
      });
  }
  function applyState(state) {
    var cur = Object.assign({}, state || {}); applyingState = true;
    var curRouteId = cur.roteiro_id || '';
    if (cur.roteiro_modo === 'EVENTO_EXISTENTE') { $('id_roteiro_modo_evento').checked=true; $('id_roteiro_modo_proprio').checked=false; setSelectedRouteId(curRouteId); }
    else { $('id_roteiro_modo_evento').checked=false; $('id_roteiro_modo_proprio').checked=true; setSelectedRouteId(''); }
    setModeUi();
    $('id_origem_estado').value = cur.sede_estado_id || '';
    return loadCities($('id_origem_cidade'), cur.sede_estado_id, cur.sede_cidade_id)
      .then(function() { refreshSelectPickers($('id_origem_estado')); return renderDestinos(cur.destinos_atuais); })
      .then(function() {
        var loop = cur.bate_volta_diario || {};
        if ($('id_bate_volta_diario_ativo')) $('id_bate_volta_diario_ativo').checked = !!loop.ativo;
        var bvNativeStart = $('id_bate_volta_data_inicio_native');
        var bvNativeEnd = $('id_bate_volta_data_fim_native');
        var bvStartIso = parseDateInput(loop.data_inicio || '') || '';
        var bvEndIso = parseDateInput(loop.data_fim || '') || '';
        var bvPickerRoot = bvNativeStart ? bvNativeStart.closest('[data-cv-date-picker]') : null;
        var bvPickerApi = bvPickerRoot ? bvPickerRoot._cvDatePicker : null;
        if (bvPickerApi) {
          bvPickerApi.setRange(bvStartIso, bvEndIso);
        } else {
          if (bvNativeStart) bvNativeStart.value = bvStartIso;
          if (bvNativeEnd) bvNativeEnd.value = bvEndIso;
        }
        if ($('id_bate_volta_ida_saida_hora')) $('id_bate_volta_ida_saida_hora').value = loop.ida_saida_hora || '';
        if ($('id_bate_volta_ida_tempo_min')) $('id_bate_volta_ida_tempo_min').value = loop.ida_tempo_min != null ? loop.ida_tempo_min : '';
        if ($('id_bate_volta_volta_saida_hora')) $('id_bate_volta_volta_saida_hora').value = loop.volta_saida_hora || '';
        if ($('id_bate_volta_volta_tempo_min')) $('id_bate_volta_volta_tempo_min').value = loop.volta_tempo_min != null ? loop.volta_tempo_min : '';
        syncBateVoltaDurationInputs();
        toggleBateVoltaPanel();
        renderTrechos(cur, { preferSeed: true });
        var ret = cur.retorno || {};
        setRoteiroDatePickerValue('id_retorno_saida_data', 'id_retorno_saida_data_display', ret.saida_data || '');
        $('id_retorno_saida_hora').value = ret.saida_hora||'';
        setRoteiroDatePickerValue('id_retorno_chegada_data', 'id_retorno_chegada_data_display', ret.chegada_data || '');
        $('id_retorno_chegada_hora').value = ret.chegada_hora||'';
        $('id_retorno_distancia_km').value = ret.distancia_km||'';
        $('id_retorno_tempo_cru_estimado_min').value = ret.tempo_cru_estimado_min != null ? ret.tempo_cru_estimado_min : '';
        $('id_retorno_tempo_adicional_min').value = ret.tempo_adicional_min != null ? ret.tempo_adicional_min : 0;
        $('id_retorno_duracao_estimada_min').value = ret.duracao_estimada_min||''; $('id_retorno_rota_fonte').value = ret.rota_fonte||'';
        if ($('id_retorno_saida_cidade') && !$('id_retorno_saida_cidade').value && ret.saida_cidade) $('id_retorno_saida_cidade').value = ret.saida_cidade;
        if ($('id_retorno_chegada_cidade') && !$('id_retorno_chegada_cidade').value && ret.chegada_cidade) $('id_retorno_chegada_cidade').value = ret.chegada_cidade;
        recalcRetorno(false); updateResumo(); applyingState = false; scheduleRealtimeDiarias();
      })
      .finally(function() {
        /* JS-04 — o flag só voltava a false no caminho de sucesso, dentro do
           `.then` acima. Uma exceção em qualquer callback desta cadeia — ou na
           carga inicial do editor — deixava `applyingState` travado em true, e
           a partir daí `runAutoEstimarTrechos` e todos os listeners que checam
           o flag abortavam para sempre, sem nenhum sinal na tela. No caminho
           feliz isto é no-op; no triste, é o que devolve o editor. */
        applyingState = false;
      });
  }
  function dtBr(d,h) { if (!d&&!h) return ''; var p=d?d.split('-'):null; return (p?p[2]+'/'+p[1]+'/'+p[0]:'')+(h?' '+h:''); }
  function routePeriodSummary(route) {
    var trechos=(route&&route.state&&route.state.trechos)||[]; var ret=(route&&route.state&&route.state.retorno)||{};
    if (!trechos.length) return 'Sem período informado';
    var ini=dtBr(trechos[0].saida_data||'',trechos[0].saida_hora||''); var ult=trechos[trechos.length-1]||{};
    var fim=dtBr(ret.chegada_data||ult.chegada_data||'',ret.chegada_hora||ult.chegada_hora||'');
    return ini&&fim ? ini+' até '+fim : (ini||fim||'Sem período informado');
  }
  function routeDestinationsSummary(route) {
    var trechos=(route&&route.state&&route.state.trechos)||[]; var names=[];
    trechos.forEach(function(t) { var n=String(t.destino_nome||'').trim(); if (n&&names.indexOf(n)===-1) names.push(n); });
    if (!names.length) return 'Sem destinos';
    return names.slice(0,3).join(' â€¢ ')+(names.length>3?' +'+(names.length-3):'');
  }
  function routeSearchText(route) {
    return [
      route && route.label,
      route && route.resumo,
      route && route.tipo_label,
      routeDestinationsSummary(route),
      routePeriodSummary(route)
    ].join(' ');
  }
  function routeDisplayTitle(route) {
    var label = String((route && route.label) || '').trim();
    label = label.replace(/^Roteiro\s*#\d+\s*[-–—:]\s*/i, '').trim();
    if (label) return label;
    var resumo = String((route && route.resumo) || '').trim();
    if (resumo) return resumo;
    return 'Roteiro salvo';
  }
  function renderRouteList(filterText) {
    var target = $('roteiro-lista'); if (!target) return;
    var emptyEl = $('roteiro-lista-empty');
    var selId = getSelectedRouteId(); var term = window.CV.util.normalize(filterText).replace(/\s+/g, ' ').trim();
    var filtered = routes.filter(function(r) { if (!term) return true; return window.CV.util.normalize(routeSearchText(r)).replace(/\s+/g, ' ').trim().indexOf(term)!==-1; });
    var pickerRoot = target.closest('[data-related-picker-root]');
    var isCardPicker = !pickerRoot || pickerRoot.dataset.relatedPickerPresentation !== 'compact';
    target.replaceChildren();
    if (!filtered.length) {
      if (!isCardPicker) {
        var empty = document.createElement('div');
        empty.className = 'related-route-empty';
        empty.textContent = 'Nenhum roteiro encontrado para a busca.';
        target.appendChild(empty);
      }
      if (emptyEl) emptyEl.hidden = !isCardPicker;
      return;
    }
    if (emptyEl) emptyEl.hidden = true;
    filtered.forEach(function(r) {
      var rid = String(r.id);
      var active = rid === selId;
      var title = routeDisplayTitle(r);
      var config = {
        active: active,
        meta: routePeriodSummary(r),
        title: title,
        value: rid,
      };
      target.appendChild(
        isCardPicker
          ? window.CV.pickerParts.createRelatedCard(config)
          : window.CV.pickerParts.createCompactRouteCard(config),
      );
    });
  }
  function routeResumo() {
    var resumoEl = $('roteiro-selector-resumo');
    if (resumoEl) {
      var r = routeMap[String(getSelectedRouteId() || '')];
      resumoEl.textContent = r ? ((r.tipo_label ? r.tipo_label + ' — ' : '') + r.resumo) : '';
    }
    renderRouteList($('id_roteiro_busca') ? $('id_roteiro_busca').value : '');
  }
  function setModeUi() {
    var em = $('id_roteiro_modo_evento').checked;
    var panel = $('roteiro-selector-wrapper');
    var routeInput = getSelectedRouteInput();
    if (panel) {
      panel.classList.toggle('d-none', !em);
      panel.hidden = !em;
    }
    if (routeInput) routeInput.disabled = !em || !routes.length;
    if ($('id_roteiro_busca')) {
      $('id_roteiro_busca').disabled = !em || !routes.length;
      if (!em) $('id_roteiro_busca').value = '';
    }
    if (!em) setSelectedRouteId('');
    routeResumo();
  }
  var destinosContainer = $('destinos-container');
  if (destinosContainer) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.initDragDrop === 'function') {
      window.CV.locationRows.initDragDrop(destinosContainer, {
        rowSelector: '[data-location-row]',
        removeSelector: '[data-location-remove]',
        dragHandleSelector: '[data-location-drag-handle]',
        onReorder: function() {
          reindexDestinoRows();
          renderTrechos(captureCurrentState(), { force: true });
          scheduleRealtimeDiarias();
          scheduleAutosave();
        }
      });
    }
    destinosContainer.addEventListener('change', function(e) {
      if (applyingState) return; var row = e.target.closest('[data-location-row]'); if (!row) return;
      if (e.target.matches('[data-location-state]')) { var cs = row.querySelector('[data-location-city]'); loadCities(cs, e.target.value||'', null).then(function() { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }); }
      else { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }
    });
    destinosContainer.addEventListener('click', function(e) {
      var addBtn = e.target.closest('[data-location-add]');
      if (addBtn && destinosContainer.contains(addBtn)) {
        var sourceRow = addBtn.closest('[data-location-row]');
        var referenceState = sourceRow ? sourceRow.querySelector('[data-location-state]') : null;
        var estadoId = referenceState
          ? (referenceState.value || destinoEstadoDefaultId || null)
          : (destinoEstadoDefaultId || null);
        addDestinoRow(
          { estado_id: estadoId, cidade_id: null },
          { insertAfter: sourceRow || null }
        ).then(function() {
          renderTrechos(captureCurrentState());
          scheduleRealtimeDiarias();
          scheduleAutosave();
        });
        return;
      }
      var btn = e.target.closest('[data-location-remove]'); if (!btn) return;
      var rows = getDestinoRows(); if (rows.length <= 1) return;
      btn.closest('[data-location-row]').remove(); reindexDestinoRows(); refreshDestinoButtons(); renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave();
    });
  }
  $('id_origem_estado').addEventListener('change', function() { if (applyingState) return; loadCities($('id_origem_cidade'), $('id_origem_estado').value, null).then(function() { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); notifyRouteStateChanged(); }); });
  $('id_origem_cidade').addEventListener('change', function() { if (applyingState) return; renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); notifyRouteStateChanged(); });
  window.addEventListener('roteiros:route-calculated', function() {
    scheduleAutosave();
  });
  $('trechos-gerados-container').addEventListener('click', function(e) {
    var stepBtn = e.target.closest('.trecho-tempo-add-btn');
    if (stepBtn && !applyingState) {
      var card = stepBtn.closest(TRECHO_CARD_SELECTOR);
      if (card) {
        var delta = parseInt(stepBtn.getAttribute('data-tempo-add-delta') || '0', 10);
        if (delta) {
          var o = card.dataset.ordem;
          var hid = card.querySelector('[name="trecho_' + o + '_tempo_adicional_min"]');
          if (hid) {
            var cur = parseInt(hid.value || 0, 10) || 0;
            hid.value = String(Math.max(0, cur + delta));
            hid.dataset.manual = '1';
            e.preventDefault();
            recalcCard(card, true);
            updateResumo(); scheduleRealtimeDiarias(); scheduleAutosave();
            return;
          }
        }
      }
    }
  });
  $('trechos-gerados-container').addEventListener('input', function(e) {
    var c = e.target.closest(TRECHO_CARD_SELECTOR);
    if (!c || applyingState) return;
    var n = e.target.name || '';
    var isTrechoDate = e.target.matches('[data-cv-date-picker-value]') && n.indexOf('_data') !== -1;
    var timeKind = e.target.getAttribute('data-route-time-kind');
    if (
      n.indexOf('_saida_') !== -1 ||
      n.indexOf('_chegada_') !== -1 ||
      n.indexOf('_tempo_adicional_min') !== -1 ||
      n.indexOf('_tempo_cru_estimado_min') !== -1 ||
      timeKind === 'travel' ||
      timeKind === 'additional' ||
      isTrechoDate
    ) {
      if (n.indexOf('_tempo_adicional_min') !== -1) e.target.dataset.manual = '1';
      if (timeKind === 'additional') {
        var h = c.querySelector('[name="trecho_' + c.dataset.ordem + '_tempo_adicional_min"]');
        if (h) h.dataset.manual = '1';
      }
      recalcCard(c, true);
    }
    updateResumo(); scheduleRealtimeDiarias(); scheduleAutosave();
  });
  $('trechos-gerados-container').addEventListener('change', function(e) {
    var c = e.target.closest(TRECHO_CARD_SELECTOR);
    if (!c || applyingState) return;
    var n = e.target.name || '';
    var isTrechoDate = e.target.matches('[data-cv-date-picker-value]') && n.indexOf('_data') !== -1;
    var timeKind = e.target.getAttribute('data-route-time-kind');
    if (
      n.indexOf('_saida_') !== -1 ||
      n.indexOf('_chegada_') !== -1 ||
      n.indexOf('_tempo_adicional_min') !== -1 ||
      n.indexOf('_tempo_cru_estimado_min') !== -1 ||
      timeKind === 'travel' ||
      timeKind === 'additional' ||
      isTrechoDate
    ) {
      if (n.indexOf('_tempo_adicional_min') !== -1) e.target.dataset.manual = '1';
      if (timeKind === 'additional') {
        var h2 = c.querySelector('[name="trecho_' + c.dataset.ordem + '_tempo_adicional_min"]');
        if (h2) h2.dataset.manual = '1';
      }
      recalcCard(c, true);
    }
    updateResumo(); scheduleRealtimeDiarias(); scheduleAutosave();
  });
  ['id_retorno_saida_data','id_retorno_saida_hora','id_retorno_chegada_data','id_retorno_chegada_hora','id_retorno_tempo_viagem_hhmm','id_retorno_tempo_adicional_hhmm'].forEach(function(id) {
    var el = $(id);
    if (!el) return;
    el.addEventListener('input', function() {
      if (applyingState) return;
      if (id === 'id_retorno_tempo_viagem_hhmm' || id === 'id_retorno_tempo_adicional_hhmm') {
        applyHhmmInputMask(el);
      }
      if (id === 'id_retorno_tempo_adicional_hhmm') {
        var rh = $('id_retorno_tempo_adicional_min');
        if (rh) rh.dataset.manual = '1';
      }
      recalcRetorno(id.indexOf('saida_')!==-1||id.indexOf('tempo_')!==-1);
      scheduleRealtimeDiarias(); scheduleAutosave(); notifyRouteStateChanged();
    });
    el.addEventListener('change', function() { if (applyingState) return; recalcRetorno(true); scheduleRealtimeDiarias(); scheduleAutosave(); });
  });
  [['retorno_tempo_add_menos', -15], ['retorno_tempo_add_mais', 15]].forEach(function(pair) {
    var btn = $(pair[0]);
    if (!btn) return;
    btn.addEventListener('click', function() {
      if (applyingState) return;
      var hid = $('id_retorno_tempo_adicional_min');
      if (!hid) return;
      var cur = parseInt(hid.value || 0, 10) || 0;
      hid.value = String(Math.max(0, cur + pair[1]));
      hid.dataset.manual = '1';
      recalcRetorno(true);
      scheduleRealtimeDiarias(); scheduleAutosave(); notifyRouteStateChanged();
    });
  });
  if ($('id_roteiro_busca')) {
    $('id_roteiro_busca').addEventListener('input', function() {
      clearTimeout(routeSearchTimer);
      routeSearchTimer = setTimeout(function() {
        renderRouteList($('id_roteiro_busca').value || '');
      }, 120);
    });
  }
  ['id_bate_volta_diario_ativo','id_bate_volta_ida_saida_hora','id_bate_volta_volta_saida_hora'].forEach(function(id) {
    var field = $(id);
    if (!field) return;
    field.addEventListener('change', function() {
      if (applyingState) return;
      toggleBateVoltaPanel();
      if (id === 'id_bate_volta_diario_ativo' && !isLoopModeActive()) {
        clearLoopGeneratedTrechos();
      } else {
        scheduleLoopTrechosRender({ preferSeed: false, force: true });
      }
      scheduleAutosave();
      notifyRouteStateChanged();
    });
  });
  ['id_bate_volta_data_inicio_native', 'id_bate_volta_data_fim_native'].forEach(function(id) {
    var nativeInput = $(id);
    if (!nativeInput) return;
    nativeInput.addEventListener('change', function() {
      if (applyingState) return;
      toggleBateVoltaPanel();
      scheduleLoopTrechosRender({ preferSeed: false, force: true });
      scheduleAutosave();
    });
  });
  [
    { text: 'id_bate_volta_ida_tempo_hhmm', hidden: 'id_bate_volta_ida_tempo_min', syncReturn: true },
    { text: 'id_bate_volta_volta_tempo_hhmm', hidden: 'id_bate_volta_volta_tempo_min' }
  ].forEach(function(pair) {
    var textInput = $(pair.text);
    var hiddenInput = $(pair.hidden);
    if (!textInput || !hiddenInput) return;
    textInput.addEventListener('input', function() {
      if (applyingState) return;
      var normalized = normalizeDurationInput(this.value);
      var parsed = parseDurationInput(normalized);
      hiddenInput.value = parsed != null ? String(parsed) : '';
      if (normalized !== this.value) this.value = normalized;
      if (pair.syncReturn) {
        syncBateVoltaReturnDurationFromOutbound(normalized, parsed);
      }
      scheduleLoopTrechosRender({ preferSeed: false, force: true });
      scheduleAutosave();
    });
    textInput.addEventListener('blur', function() {
      syncBateVoltaDurationInputs();
    });
  });

  // Calendário de trechos: data inicial → primeiro trecho, data final → último trecho
  var trDatePicker = $('trechos-date-picker');
  if (trDatePicker) {
    trDatePicker.addEventListener('cv:multi-confirm', function(event) {
      if (applyingState) return;
      var dates = (event && event.detail && event.detail.dates) || [];
      applyTrechosDateSelection(dates);
    });
    syncTrechosDatePickerLimit();
  }

  if ($('roteiro-lista')) {
    $('roteiro-lista').addEventListener('click', function(e) {
      var btn = e.target.closest('[data-route-id]'); if (!btn) return;
      var rid = btn.getAttribute('data-route-id')||''; if (!rid) return;
      if (getSelectedRouteId() === rid) {
        clearRouteTrechos({ keepEventoMode: true }).then(function() {
          scheduleRealtimeDiarias();
        });
        scheduleAutosave();
        return;
      }
      setSelectedRouteId(rid);
      routeResumo();
      var r = routeMap[String(rid)];
      if (r && r.state && $('id_roteiro_modo_evento').checked) applyRouteSelection(r);
      else scheduleRealtimeDiarias();
      scheduleAutosave();
    });
  }
  if ($('id_roteiro_modo_evento')) {
    $('id_roteiro_modo_evento').addEventListener('change', function() {
      setModeUi();
      if ($('id_roteiro_modo_evento').checked && getSelectedRouteId()) {
        var r = routeMap[String(getSelectedRouteId())];
        if (r && r.state) applyRouteSelection(r);
      }
      else { scheduleRealtimeDiarias(); }
      scheduleAutosave();
    });
  }
  if ($('id_roteiro_modo_proprio')) {
    $('id_roteiro_modo_proprio').addEventListener('change', function() {
      var hadSelection = !!getSelectedRouteId();
      setModeUi();
      if (hadSelection) { clearRouteTrechos(); }
      else { scheduleRealtimeDiarias(); }
      scheduleAutosave();
    });
  }
  setModeUi();
  toggleBateVoltaPanel();
  syncBateVoltaDurationInputs();
  applyState(initialRoteiroState).then(function() {
    if (initialRoteiroDiarias) {
      applyDiarias(initialRoteiroDiarias);
      setDiariasStatus('updated', 'Cálculo carregado (1 servidor).');
    } else {
      scheduleRealtimeDiarias();
    }
    notifyRouteStateChanged();
  });
  form.addEventListener('autosave:created', function(event) {
    var data = event && event.detail ? event.detail : {};
    if (!data || !data.object_id) return;
    var objectId = String(data.object_id);
    if (autosaveIdInput) autosaveIdInput.value = objectId;
    var editPath = '/roteiros/' + objectId + '/editar/';
    if (window.location.pathname.indexOf('/roteiros/novo/') !== -1) {
      window.history.replaceState({}, '', editPath);
    }
  });
  window.CV.roteiros.editor = {
    canCalculateRoutePreview: canCalculateRoutePreview,
    buildRoutePreviewPayload: buildRoutePreviewPayload,
    applyRoutePreviewResult: applyRoutePreviewResult,
    getPreviewEndpointUrl: function() { return urlCalcularRotaPreview; },
    isLoopModeActive: isLoopModeActive,
  };
  window.dispatchEvent(new CustomEvent('roteiros:editor-ready'));
  if (window.CV.roteiros.map && typeof window.CV.roteiros.map.boot === 'function') {
    window.CV.roteiros.map.boot();
  }
  })();
}
