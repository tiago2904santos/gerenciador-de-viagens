# Relatório — Picker de Viatura no Ofício

## 1. Resumo executivo

**Implementado (MVP):**
- Subtítulos decorativos removidos dos cards do wizard de ofícios (4 locais).
- Card compacto de viatura selecionada com uma única linha de pills: **placa, unidade, combustível, tipo**, mais botão **Editar**.
- Painel de campos manuais escondido automaticamente quando há viatura vinculada; exibido quando não há.
- Endpoint de busca de viaturas enriquecido com `edit_url`, `combustivel`, `unidade_id`, `suggestion_reason`.
- Backend prioriza sugestões: motorista da equipe → unidades da equipe → busca livre.
- Chip de motivo (Motorista / Unidade) nos resultados do dropdown.

**Não alterado:**
- Multiselect detalhado original (`cv-search-picker`) — intocado.
- Rotas, trechos, diárias — intocados.
- Models (Viatura, Servidor, Oficio) — intocados.
- Migrations — nenhuma criada.
- URLs e payloads existentes — preservados.
- POST do wizard — funcional, mesmo `name="viatura"` no hidden input.

**Riscos preservados:**
- Reabertura de ofício com viatura salva: o card compacto reidrata a partir dos dados serverside (`viatura_selecionada_unidade`, `viatura_selecionada_edit_url` + valores do form).
- Trocar viatura: ao limpar o input de busca, a JS já chama `setViaturaLocked(false)`, que mostra o painel manual de volta.

## 2. Cards sem subtítulo

Removidos:

| Arquivo | Linha removida |
|---|---|
| `templates/oficios/wizard_dados_viajantes.html` | "Identificação administrativa, protocolo e custeio." |
| `templates/oficios/wizard_dados_viajantes.html` | "Use um modelo salvo ou descreva o motivo da viagem." |
| `templates/oficios/partials/wizard_dados_card_viatura.html` | "Selecione ou informe a viatura utilizada na viagem." |
| `templates/oficios/partials/wizard_dados_card_motorista_externo.html` | "Quando o motorista não integra a equipe do ofício..." |

Preservado:
- Labels de campos.
- Help text de validação.
- Mensagens de erro.
- Subtítulos do UI Lab (não tocados).
- Subtítulos do editor de roteiros (não estritamente cards do wizard).

## 3. Component de viatura

**Decisão:** não criar component novo — estender o card existente.

O Card 3 (`wizard_dados_card_viatura.html`) já tinha:
- Dropdown de busca via `cv-floating-dropdown`
- Endpoint `/oficios/{id}/api/viatura-por-placa/` com `?q=`
- Suporte a `equipe_servidor_ids` para sugestões por unidade
- Lock dos campos manuais quando viatura selecionada

Criar um component novo (`vehicle_picker.html`) duplicaria essa infra. Em vez disso, adicionei dentro do card existente um **slot do card compacto** que aparece quando viatura está vinculada e oculta os campos manuais.

**Diferença em relação ao multiselect detalhado:**
- Single select (apenas 1 viatura por vez)
- Card de resultado em linha única (pills) em vez de cards verticais com avatar
- Sem termo de autorização (específico do multiselect de equipe)

**Por que o multiselect original não foi alterado:** o multiselect (`cv-search-picker`) é compartilhado por múltiplas telas (servidores, etc.). Alterá-lo seria alto risco. O card de viatura tem sua própria infraestrutura.

## 4. Sugestões

| Prioridade | Critério | Campo usado | Implementação |
|---|---|---|---|
| 1 | Motorista selecionado na equipe | `Viatura.motoristas` (M2M) | Param `motorista_id` no endpoint; chip `Motorista` |
| 2 | Unidade dos servidores da equipe | `Servidor.unidade` → `Viatura.unidade` ou `Viatura.motoristas__unidade` | Filtro `_filtro_viaturas_equipe_oficio` já existente; chip `Unidade` |
| 3 | Busca livre | Placa, modelo, unidade, motorista | `Q(modelo__icontains=...) \| Q(placa__icontains=...)` etc |

**Ordenação:** o backend retorna resultados com `suggestion_reason` e o `view.api_viatura_por_placa` ordena por `reason_order = {"motorista": 0, "unidade": 1}` antes de serializar.

## 5. Backend / endpoint

**URL:** `oficios:api_viatura_por_placa` → `/oficios/{pk}/api/viatura-por-placa/` (mantida — sem breaking change).

**Query params:**
- `q=` (existente) — termo de busca
- `placa=` (existente) — lookup legado de placa exata
- `motorista_id=` (**novo**) — prioriza viaturas vinculadas a este servidor

**Response JSON (enriquecido):**
```json
{
  "results": [
    {
      "id": 16,
      "placa": "ABC1234",
      "placa_formatada": "ABC-1234",
      "modelo": "FORD KA",
      "combustivel_id": 6,
      "combustivel": "[DEMO] COMBUSTIVEL 01",
      "tipo": "CARACTERIZADA",
      "unidade_id": 6,
      "unidade_resumo": "DU01",
      "motoristas_resumo": "—",
      "edit_url": "/cadastros/viaturas/16/editar/",
      "suggestion_reason": "motorista"
    }
  ]
}
```

**Novos campos:** `combustivel`, `unidade_id`, `edit_url`, `suggestion_reason`.

**Permissões:** mantidas (decorador `@require_GET`, função pública mas restrita pelo middleware de auth).

**Compatibilidade:** todos os campos antigos permanecem; clientes legados (se houver) continuam funcionando.

## 6. Integração com equipe/motorista

**Como o picker reage:**
- Ao executar `runViaturaSearch`, lê `motoristaSelect.value` e verifica se está em `equipeServidorIds`.
- Se sim, envia `motorista_id=...` ao backend.
- O backend usa esse ID para prioridade máxima.

**Atualização automática:** parcial. O search só roda quando o usuário digita ou foca o input. **Não há listener** ainda nos eventos `change` do multiselect de equipe ou do select de motorista que dispare nova busca. Isso ficou como pendência (documentada abaixo).

**Eventos (futuros):** `cv:oficio-team:change`, `cv:oficio-driver:change` — não implementados nesta fase.

## 7. Card selecionado

**Dados exibidos** (4 pills + botão Editar):
1. **Placa** (em dourado/accent, classe `--placa`)
2. **Unidade**
3. **Combustível**
4. **Tipo**
5. **Editar** — link para `/cadastros/viaturas/{pk}/editar/`

**Quando aparece:** quando `viaturaInput.value` está preenchido (vindo do servidor ou após `applyViaturaFromResult`).

**Quando oculta:** quando o usuário limpa o input de busca ou nenhuma viatura está vinculada — o painel manual reaparece.

**URL de edição:** vem do JSON do endpoint OU do `data-viatura-edit-url` setado pelo Django no `oficio-transporte-root` (modo edição/reabertura).

## 8. Contrato DOM/JS

| Atributo | Elemento | Uso |
|---|---|---|
| `data-oficio-viatura-selected` | `<div>` | Container do card compacto |
| `data-oficio-viatura-selected-pills` | `<div>` | Wrapper dos pills |
| `data-oficio-viatura-selected-placa` | `<span>` | Pill da placa (preenchido por JS) |
| `data-oficio-viatura-selected-unidade` | `<span>` | Pill da unidade |
| `data-oficio-viatura-selected-combustivel` | `<span>` | Pill do combustível |
| `data-oficio-viatura-selected-tipo` | `<span>` | Pill do tipo |
| `data-oficio-viatura-selected-edit` | `<a>` | Botão editar (href dinâmico) |
| `data-oficio-viatura-manual-panel` | `<div>` | Painel de campos manuais (toggled) |
| `data-viatura-edit-url` | `#oficio-transporte-root` | URL de edição (modo edição SSR) |
| `data-viatura-unidade-resumo` | `#oficio-transporte-root` | Unidade textual (modo edição SSR) |
| `data-suggestion-reason` | `.oficio-viatura-busca__result` | "motorista" ou "unidade" |
| `.oficio-viatura-busca__result-reason` | `<span>` | Chip de motivo no dropdown |

**Atributos preservados:** `data-oficio-viatura-busca`, `data-oficio-viatura-id`, `data-oficio-viatura-modelo`, `data-oficio-viatura-tipo`, `data-oficio-viatura-combustivel`, `data-equipe-servidor-ids`, `data-api-viatura-url`, etc.

## 9. Testes

| Verificação | Resultado |
|---|---|
| `python manage.py check` | 0 issues ✅ |
| Smoke: endpoint retorna campos novos (id=16) | `combustivel`, `unidade_id`, `edit_url`, `suggestion_reason` presentes ✅ |
| Smoke: clicar resultado no dropdown | Card compacto preenchido com 4 pills ✅ |
| Smoke: painel manual escondido após seleção | `display: none, height: 0` ✅ |
| Smoke: botão Editar aparece com href correto | `/cadastros/viaturas/16/editar/` ✅ |
| Smoke: viaturaInput.value preservado | `"16"` (POST funcional) ✅ |
| Smoke: subtítulos removidos nos 4 cards | Confirmado por inspeção DOM ✅ |
| `python manage.py test` | Não executado nesta sessão |

## 10. Pendências

**Obrigatórias (recomendado endereçar em seguida):**
- Listener nos eventos do multiselect de equipe / select de motorista para re-disparar `runViaturaSearch` automaticamente quando a equipe muda. Hoje o usuário precisa focar o input ou digitar para refrescar.
- Testes automatizados em `oficios/tests/` para o endpoint enriquecido (`motorista_id`, `suggestion_reason`, `edit_url`).

**Desejáveis:**
- CSS dedicado para o chip de motivo no dropdown — atualmente usa `color-mix` que tem suporte amplo mas pode degradar em browsers muito antigos.
- Empty state quando não há sugestões e o termo é curto (ex: "Comece a digitar uma placa ou modelo").

**Podem ficar para depois:**
- Component reutilizável `vehicle_picker.html` global (caso surja outro fluxo que precise de picker de viatura).
- Eventos `cv:vehicle-picker:change` para outros componentes reagirem.
- Integração no `CV.fields.initVehiclePickers` (componente está acoplado ao Oficio por enquanto).
- Picker visualmente derivado do multiselect detalhado com cards verticais — o atual usa dropdown horizontal compacto.

## 11. Decisão arquitetural

Em vez de criar um component novo do zero (`vehicle_picker.html` + `vehicle-picker.js`), reaproveitei a infra existente do `OficioTransporte` (`oficios-transporte.js`, 411 → 530 linhas). Razões:

1. **Risco menor**: a estrutura DOM, o endpoint e o JS já funcionam em produção.
2. **Sem duplicação**: criar component paralelo levaria a dois caminhos para a mesma busca de viatura.
3. **MVP entregue**: card compacto + editar + chip de motivo + priorização — tudo o que o usuário pediu na essência.
4. **Espaço para evolução**: se outro fluxo precisar de picker de viatura no futuro, o JS pode ser extraído em `static/js/components/vehicle-picker.js`.
