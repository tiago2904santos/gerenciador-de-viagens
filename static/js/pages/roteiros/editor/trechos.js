/**
 * Cards de trechos do editor — markup alinhado ao design system (cv-field, date-picker, máscaras).
 */

export const TRECHOS_EMPTY_HTML =
  '<div class="roteiro-editor__empty">' +
  '<p class="roteiro-editor__empty-title">Trechos ainda não disponíveis</p>' +
  '<p class="roteiro-editor__empty-text">Os trechos aparecem aqui após definir os destinos.</p>' +
  '</div>';

export const TRECHO_CARD_SELECTOR = '.roteiro-trecho-card[data-key]';

function isRoteiroOficio() {
  return !!document.querySelector('.roteiro-editor--oficio');
}

/** Empty state: no ofício vira um bloco irmão (mesmo padrão visual dos trechos). */
export function getTrechosEmptyHtml() {
  if (!isRoteiroOficio()) return TRECHOS_EMPTY_HTML;
  return (
    '<section class="form-block form-block--resource roteiro-editor__section--trechos-empty route-section-block" aria-labelledby="sec-trechos-empty">' +
    '<header class="form-block__header">' +
    '<div class="form-block__copy">' +
    '<h4 class="form-block__title" id="sec-trechos-empty">Trechos</h4>' +
    '<p class="form-block__description">Saídas e chegadas entre sede e destinos.</p>' +
    '</div></header>' +
    '<div class="form-block__body">' +
    TRECHOS_EMPTY_HTML +
    '</div></section>'
  );
}

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
  var template = document.getElementById('trecho-single-date-picker-template');
  if (!template) return '';
  return template.innerHTML
    .replace(/__LABEL__/g, esc(label))
    .replace(/__DISPLAY_ID__/g, esc(idBase + '_data_display'))
    .replace(/__HIDDEN_ID__/g, esc(idBase + '_data'))
    .replace(/__HIDDEN_NAME__/g, esc('trecho_' + ordem + '_' + role + '_data'))
    .replace(/__ISO_VALUE__/g, esc(isoValue || ''))
    .replace(/__INITIAL_DATE__/g, esc(display))
    .replace(/__ROLE__/g, esc(role));
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
  var num = o + 1;
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
  var oficio = isRoteiroOficio();
  var routeText = esc(trecho.origem_nome) + ' \u2192 ' + esc(trecho.destino_nome);
  var titleId = 'sec-trecho-' + num;

  var article =
    '<article class="roteiro-trecho-card roteiro-deslocamento" data-key="' +
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
    (oficio
      ? ''
      : '<div class="roteiro-leg-label">' +
        '<span class="roteiro-leg-label__num">Trecho ' +
        num +
        '</span>' +
        '<span class="roteiro-leg-label__route">' +
        routeText +
        '</span></div>') +
    '<div class="roteiro-deslocamento__body">' +
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
    '<div class="field-grid field-grid--cols-3 oficio-roteiro-time-calc-grid roteiro-time-calc-grid roteiro-trecho-card__time-grid">' +
    '<div class="field cv-field field-size-1">' +
    '<label class="cv-field__label">Tempo de viagem</label>' +
    '<input type="text" class="cv-field__control trecho-tempo-viagem-hhmm" data-route-time-kind="travel" value="' +
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
    '<input type="text" class="cv-field__control trecho-tempo-adicional-hhmm" data-route-time-kind="additional" value="' +
    esc(add ? fmt(add) : '') +
    '" placeholder="00:00" data-mask="time" inputmode="numeric" maxlength="5" autocomplete="off">' +
    '<button type="button" class="cv-btn cv-btn--secondary cv-btn--control trecho-tempo-add-btn" data-tempo-add-delta="-15" aria-label="Menos 15 minutos">−</button>' +
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
    '</div></div>' +
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
    '</div></article>';

  if (!oficio) return article;

  return (
    '<section class="form-block form-block--resource roteiro-editor__section--trecho route-section-block" aria-labelledby="' +
    titleId +
    '">' +
    '<header class="form-block__header">' +
    '<div class="form-block__copy">' +
    '<h4 class="form-block__title" id="' +
    titleId +
    '">Trecho ' +
    num +
    '</h4>' +
    '<p class="form-block__description">' +
    routeText +
    '</p>' +
    '</div>' +
    (num === 1
      ? '<div class="form-block__actions" data-trechos-date-picker-slot></div>'
      : '') +
    '</header>' +
    '<div class="form-block__body">' +
    article +
    '</div></section>'
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
    // Só avisa quando a data realmente mudou. O `change` sobe até o listener do
    // container do editor, que recalcula o card e pode voltar aqui; sem esta
    // guarda, um chamador que esqueça o `silent` reabre a recursão infinita.
    var mudou = hidden.value !== (isoDate || '');
    hidden.value = isoDate || '';
    if (mudou && !opts.silent) {
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  var picker = card.querySelector('[data-trecho-date="' + role + '"]');
  if (picker) {
    if (picker._cvDatePicker && typeof picker._cvDatePicker.setSingle === 'function') {
      picker._cvDatePicker.setSingle(isoDate || '');
    } else {
      var display = picker.querySelector('[data-cv-date-picker-display]');
      if (display) {
        display.value = isoToDisplayDate(isoDate);
      }
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
    getTrechosEmptyHtml: getTrechosEmptyHtml,
    TRECHOS_EMPTY_HTML: TRECHOS_EMPTY_HTML,
    TRECHO_CARD_SELECTOR: TRECHO_CARD_SELECTOR,
  };
}
