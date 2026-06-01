/**
 * Cards de trechos do editor — markup alinhado ao design system (cv-field, date-picker, máscaras).
 */

export const TRECHOS_EMPTY_HTML =
  '<div class="roteiro-editor__empty">' +
  '<p class="roteiro-editor__empty-title">Trechos ainda não disponíveis</p>' +
  '<p class="roteiro-editor__empty-text">Os trechos aparecem aqui após definir os destinos.</p>' +
  '</div>';

export const TRECHO_CARD_SELECTOR = '.roteiro-trecho-card[data-key]';

var CALENDAR_ICON_SVG =
  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
  '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>' +
  '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>' +
  '</svg>';

var DATE_PICKER_PANEL_HTML =
  '<div class="cv-date-picker__panel" hidden data-cv-date-picker-panel>' +
  '<div class="cv-date-picker__panel-header">' +
  '<button class="cv-date-picker__nav" type="button" data-cv-date-picker-prev aria-label="Mês anterior">Anterior</button>' +
  '<div class="cv-date-picker__month" data-cv-date-picker-month></div>' +
  '<button class="cv-date-picker__nav" type="button" data-cv-date-picker-next aria-label="Próximo mês">Próximo</button>' +
  '</div>' +
  '<div class="cv-date-picker__weekdays" data-cv-date-picker-weekdays></div>' +
  '<div class="cv-date-picker__days" data-cv-date-picker-days></div>' +
  '<div class="cv-date-picker__footer">' +
  '<button type="button" class="cv-date-picker__footer-action" data-cv-date-picker-today>Hoje</button>' +
  '<button type="button" class="cv-date-picker__footer-action" data-cv-date-picker-clear>Limpar</button>' +
  '</div></div>';

function isoToDisplayDate(iso) {
  var raw = String(iso || '').trim();
  if (!raw) return '';
  var m = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return raw;
  return m[3] + '/' + m[2] + '/' + m[1];
}

function buildDatePickerField(ordem, role, label, isoValue, esc) {
  var idBase = 'trecho_' + ordem + '_' + role;
  var display = isoToDisplayDate(isoValue);
  var initialAttr = display ? ' data-initial-date="' + esc(display) + '"' : '';
  return (
    '<div class="field cv-field field-size-1">' +
    '<label class="cv-field__label" for="' +
    idBase +
    '_data_display">' +
    esc(label) +
    '</label>' +
    '<div class="cv-date-picker" data-cv-date-picker data-mode="single" data-trecho-date="' +
    esc(role) +
    '"' +
    initialAttr +
    '>' +
    '<div class="cv-date-picker__control">' +
    '<input type="text" class="cv-field__control" id="' +
    idBase +
    '_data_display" placeholder="dd/mm/aaaa" autocomplete="off" inputmode="numeric" maxlength="10" value="' +
    esc(display) +
    '" data-cv-date-picker-display>' +
    '<button type="button" class="cv-date-picker__trigger cv-date-picker__trigger--icon" data-cv-date-picker-trigger aria-expanded="false" aria-label="Abrir calendário">' +
    CALENDAR_ICON_SVG +
    '</button></div>' +
    '<input type="hidden" name="trecho_' +
    ordem +
    '_' +
    role +
    '_data" id="' +
    idBase +
    '_data" value="' +
    esc(isoValue || '') +
    '" data-cv-date-picker-value>' +
    DATE_PICKER_PANEL_HTML +
    '</div></div>'
  );
}

function buildTimeField(ordem, role, label, value, esc) {
  var id = 'trecho_' + ordem + '_' + role + '_hora';
  return (
    '<div class="field cv-field field-size-1">' +
    '<label class="cv-field__label" for="' +
    id +
    '">' +
    esc(label) +
    '</label>' +
    '<input type="text" class="cv-field__control" name="trecho_' +
    ordem +
    '_' +
    role +
    '_hora" id="' +
    id +
    '" data-mask="time" value="' +
    esc(value || '') +
    '" placeholder="00:00" inputmode="numeric" maxlength="5" autocomplete="off">' +
    '</div>'
  );
}

function buildLegPanel(ordem, role, title, cityName, dateValue, timeValue, esc) {
  return (
    '<div class="roteiro-trecho-card__leg">' +
    '<div class="roteiro-trecho-card__leg-title">' +
    esc(title) +
    '</div>' +
    '<div class="field-grid field-grid--cols-2 roteiro-trecho-card__leg-grid">' +
    '<div class="field cv-field cv-field--readonly roteiro-trecho-card__leg-cidade">' +
    '<label class="cv-field__label">Cidade</label>' +
    '<input type="text" class="cv-field__control" value="' +
    esc(cityName) +
    '" readonly tabindex="-1" aria-readonly="true">' +
    '</div>' +
    buildDatePickerField(ordem, role, 'Data', dateValue, esc) +
    buildTimeField(ordem, role, 'Hora', timeValue, esc) +
    '</div></div>'
  );
}

/**
 * @param {object} trecho
 * @param {object} value
 * @param {function} esc
 * @param {function} formatDurationInput
 */
export function buildTrechoCard(trecho, value, esc, formatDurationInput) {
  var o = trecho.ordem;
  var dist = value.distancia_km || '';
  var cru = value.tempo_cru_estimado_min || '';
  var add =
    value.tempo_adicional_min != null && value.tempo_adicional_min !== ''
      ? value.tempo_adicional_min
      : 0;
  var fonte = value.rota_fonte || '';
  var trechoId = value.id || trecho.id || '';
  var fmt = typeof formatDurationInput === 'function' ? formatDurationInput : function (v) {
    return v || '';
  };

  return (
    '<article class="roteiro-trecho-card oficio-roteiro-trecho-card" data-key="' +
    esc(trecho.key) +
    '" data-trecho-id="' +
    esc(trechoId) +
    '" data-ordem="' +
    o +
    '" data-origem-nome="' +
    esc(trecho.origem_nome) +
    '" data-destino-nome="' +
    esc(trecho.destino_nome) +
    '" data-origem-estado-id="' +
    esc(trecho.origem_estado_id) +
    '" data-origem-cidade-id="' +
    esc(trecho.origem_cidade_id) +
    '" data-destino-estado-id="' +
    esc(trecho.destino_estado_id) +
    '" data-destino-cidade-id="' +
    esc(trecho.destino_cidade_id) +
    '">' +
    '<header class="roteiro-trecho-card__header">' +
    '<h4 class="roteiro-trecho-card__title">Trecho ' +
    (o + 1) +
    ' \u2014 ' +
    esc(trecho.origem_nome) +
    ' \u2192 ' +
    esc(trecho.destino_nome) +
    '</h4></header>' +
    '<div class="roteiro-trecho-card__body">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_origem_nome" value="' +
    esc(trecho.origem_nome) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_id" value="' +
    esc(trechoId) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_destino_nome" value="' +
    esc(trecho.destino_nome) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_origem_estado_id" value="' +
    esc(trecho.origem_estado_id) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_origem_cidade_id" value="' +
    esc(trecho.origem_cidade_id) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_destino_estado_id" value="' +
    esc(trecho.destino_estado_id) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_destino_cidade_id" value="' +
    esc(trecho.destino_cidade_id) +
    '">' +
    '<div class="roteiro-trecho-card__route-row field-grid field-grid--cols-2">' +
    buildLegPanel(o, 'saida', 'Saída', trecho.origem_nome, value.saida_data || '', value.saida_hora || '', esc) +
    buildLegPanel(
      o,
      'chegada',
      'Chegada',
      trecho.destino_nome,
      value.chegada_data || '',
      value.chegada_hora || '',
      esc
    ) +
    '</div>' +
    '<div class="wizard-inner-section roteiro-trecho-card__time-section">' +
    '<div class="wizard-inner-section__header"><h5 class="wizard-inner-section__title">Tempo de viagem</h5></div>' +
    '<div class="field-grid field-grid--cols-3 oficio-roteiro-time-calc-grid roteiro-time-calc-grid roteiro-trecho-card__time-grid">' +
    '<div class="field cv-field field-size-1">' +
    '<label class="cv-field__label">Tempo de viagem</label>' +
    '<input type="text" class="cv-field__control trecho-tempo-viagem-hhmm" value="' +
    esc(fmt(cru)) +
    '" placeholder="00:00" data-mask="time" inputmode="numeric" maxlength="5" autocomplete="off">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_tempo_cru_estimado_min" value="' +
    esc(cru) +
    '">' +
    '</div>' +
    '<div class="field cv-field field-size-1">' +
    '<label class="cv-field__label">Tempo adicional</label>' +
    '<div class="roteiro-time-calc-stepper roteiro-trecho-card__time-stepper">' +
    '<button type="button" class="cv-btn cv-btn--secondary cv-btn--control trecho-tempo-add-btn" data-tempo-add-delta="-15" aria-label="Menos 15 minutos">−</button>' +
    '<input type="text" class="cv-field__control trecho-tempo-adicional-hhmm" value="' +
    esc(add ? fmt(add) : '') +
    '" placeholder="00:00" data-mask="time" inputmode="numeric" maxlength="5" autocomplete="off">' +
    '<button type="button" class="cv-btn cv-btn--secondary cv-btn--control trecho-tempo-add-btn" data-tempo-add-delta="15" aria-label="Mais 15 minutos">+</button>' +
    '</div>' +
    '<input type="hidden" name="trecho_' +
    o +
    '_tempo_adicional_min" value="' +
    esc(add) +
    '">' +
    '</div>' +
    '<div class="field cv-field cv-field--readonly field-size-1">' +
    '<label class="cv-field__label">Tempo total</label>' +
    '<input type="text" class="cv-field__control trecho-tempo-total" value="" readonly tabindex="-1" aria-readonly="true">' +
    '</div></div></div>' +
    '<input type="hidden" name="trecho_' +
    o +
    '_distancia_km" value="' +
    esc(dist) +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_duracao_estimada_min" value="' +
    esc(value.duracao_estimada_min || '') +
    '">' +
    '<input type="hidden" name="trecho_' +
    o +
    '_rota_fonte" value="' +
    esc(fonte) +
    '">' +
    '</div></article>'
  );
}

export function initTrechosFields(container) {
  var root = container || document.getElementById('trechos-gerados-container');
  if (!root || !window.CV || !window.CV.fields || typeof window.CV.fields.init !== 'function') {
    return;
  }
  window.CV.fields.init(root);
}

/** Atualiza data ISO (hidden + display) após cálculo de chegada. */
export function setTrechoDateValue(card, role, isoDate, options) {
  if (!card) return;
  var opts = options || {};
  var o = card.dataset.ordem;
  var hidden = card.querySelector('[name="trecho_' + o + '_' + role + '_data"]');
  if (hidden) {
    hidden.value = isoDate || '';
    if (!opts.silent) {
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  var picker = card.querySelector('[data-trecho-date="' + role + '"]');
  if (picker) {
    var display = picker.querySelector('[data-cv-date-picker-display]');
    if (display) {
      display.value = isoToDisplayDate(isoDate);
    }
  }
}

export function queryTrechoCards(container) {
  var root = container || document.getElementById('trechos-gerados-container');
  return root ? Array.prototype.slice.call(root.querySelectorAll(TRECHO_CARD_SELECTOR)) : [];
}

export function createTrechosModule() {
  return {
    name: 'trechos',
    buildTrechoCard: buildTrechoCard,
    initTrechosFields: initTrechosFields,
    setTrechoDateValue: setTrechoDateValue,
    queryTrechoCards: queryTrechoCards,
    TRECHOS_EMPTY_HTML: TRECHOS_EMPTY_HTML,
    TRECHO_CARD_SELECTOR: TRECHO_CARD_SELECTOR,
  };
}
