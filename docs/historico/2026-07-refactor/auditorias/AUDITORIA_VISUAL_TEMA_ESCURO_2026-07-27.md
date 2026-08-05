# Auditoria visual completa — tema escuro

Data: 27/07/2026

## Escopo

O tema escuro é a única referência visual desta etapa. O dashboard permanece em
segundo plano; a prioridade são os fluxos operacionais de documentos, eventos,
roteiros, prestação de contas, listas, formulários e cadastros.

Foram auditadas telas reais em desktop e mobile, além da árvore de templates,
dependências de CSS e contratos dos componentes globais.

## Diagnóstico

### Críticos

- Páginas de um domínio carregam CSS de outros domínios. Eventos e Ofícios, por
  exemplo, dependem de estilos de Roteiros e Prestação de Contas.
- O cabeçalho avançado de listas só possuía adaptação completa abaixo de 720 px,
  embora a sidebar reduza o espaço útil muito antes disso.
- Componentes equivalentes recebem alturas e raios diferentes por
  sobrescritas locais.
- `ui/layouts/form_section.html` abre uma `<section>` sem fechá-la. Os
  consumidores precisam completar o HTML manualmente, quebrando encapsulamento.
- Datas e destinos já tinham primitivas globais, mas as páginas repetiam a
  composição e o espaçamento da seção.

### Altos

- Há mais de vinte folhas globais em várias páginas e folhas monolíticas acima
  de 100 KB, aumentando colisões de especificidade.
- Estados vazios possuem alinhamentos diferentes sem variantes documentadas.
- Busca, select, período e botões do mesmo rail não compartilham um único
  contrato responsivo.
- Hooks de JavaScript de destinos ainda carregam nomes de módulos.

### Médios

- Hierarquia tipográfica de subseções varia entre fluxos.
- Rodapés misturam alturas de ações primária e secundária.
- Parte da documentação descreve conformidade visual anterior que não reflete a
  renderização atual.

## Arquitetura adotada

1. Tokens escuros.
2. Primitivas globais.
3. Componentes compostos por tarefa.
4. Padrões completos de página.

O primeiro composto é
`components/travel/period_destinations_section.html`. Ele contém o date picker
global, a coleção global de destinos e um slot opcional para campos relacionados.

## Correções desta etapa

- Composição “Período e destinos” aplicada a Evento, Termo, Ordem de Serviço e
  Plano de Trabalho.
- Hook global `data-destination-add` adicionado sem quebrar os hooks legados.
- Cabeçalho escuro de filtros passa a reorganizar data e ações no intervalo em
  que a sidebar reduz o conteúdo.
- Ícone de busca recebe dimensões e comportamento de flex explícitos.
- Contrato estrutural e responsivo do composto incluído no CSS global de
  seções.
- Componente incompleto `form_section.html` removido; seus dez consumidores
  agora usam blocos fechados ou a confirmação de exclusão global.
- Confirmações de exclusão passam a compartilhar estrutura, hierarquia,
  mensagens, prévia opcional e rodapé.
- Controles do cabeçalho e ações de rodapé usam a régua global de 44 px e raio
  de controle.
- Estado vazio compacto virou uma variante global explícita, sem depender do
  tipo de página para receber seu layout.
- Linhas globais de destino empilham UF e cidade no celular, evitando campos
  comprimidos e placeholders ilegíveis.
- Listas de Ofícios, Eventos, Ordens de Serviço, Planos e Prestações deixaram de
  carregar folhas completas de outros domínios que eram usadas apenas por
  componentes hoje globalizados.
- Cabeçalhos com múltiplos selects mantêm período e limpeza juntos na segunda
  linha em desktops médios, evitando uma ação isolada.

## Próximas migrações

1. Consolidar alturas, raios e estados de foco de campos e botões.
2. Transformar estados vazios em variantes globais explícitas.
3. Reduzir CSS cruzado entre domínios.
4. Migrar os demais formulários de viagem.
5. Validar todas as rotas no tema escuro em desktop e mobile.
6. Tratar o dashboard por último.
