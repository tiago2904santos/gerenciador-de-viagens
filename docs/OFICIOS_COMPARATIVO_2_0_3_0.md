# Comparativo Ofícios 2.0 x 3.0

| Funcionalidade | Legacy 2.0 | Estado no 3.0 | Migrar? | Prioridade | Observação |
|---|---|---|---|---|---|
| CRUD | Completo com wizard e fluxos derivados | CRUD mínimo real | Sim | Alta | 3.0 cobre base, sem fluxo avançado |
| listagem | Global + filtros + modo rich/basic | Lista básica com filtros simples | Sim | Média | melhoria de UX opcional |
| detalhe | Resumo completo + contexto documental | Detalhe básico | Sim | Alta | expandir blocos de completude |
| resumo | Painel lateral no wizard | Não | Sim | Média | implementar sem acoplamento de etapa |
| número | Numeração anual com lacuna + retry | Sequencial simples | Sim | Alta | revisar concorrência |
| ano | Derivado por data de criação | Presente | Parcial | Média | alinhar com estratégia de numeração |
| protocolo | Normalização + máscara | Campo básico | Sim | Alta | reforçar validação canônica |
| status | Rascunho/Finalizado com regras implícitas | Rascunho/Finalizado/Arquivado | Parcial | Média | definir transições de negócio |
| evento | Vínculo frequente no legado | Não no modelo atual | Futuro | Média | manter opcional, não obrigatório |
| roteiro | Modo salvo/próprio | FK opcional simples | Sim | Alta | incluir regras de sincronização |
| servidores | M2M com regras operacionais | M2M básico | Sim | Alta | completar validações |
| viatura | FK + cópia textual e regras | FK básica | Sim | Alta | ampliar contexto operacional |
| motorista | FK + carona/protocolo | FK básica | Sim | Alta | regra de carona pendente |
| trechos | `OficioTrecho` + ordenação | Não existe | Sim | Alta | peça-chave de migração |
| retorno | Campos dedicados no ofício | Não existe | Sim | Alta | integrar com trechos/período |
| diárias | Cálculo robusto por período/destino | Não existe | Sim | Alta | dependência crítica documental |
| custeio | Regras completas e textos formais | Parcial | Sim | Alta | faltam cenários avançados |
| justificativa | Modelo e fluxo vinculados | Não existe | Sim | Alta | fase dedicada |
| termos | Vários modos + lote por servidor | Não existe | Sim | Alta | app termos pendente |
| plano | Documento independente com vínculos | Não existe | Sim | Média | fase 22 |
| OS | Documento independente com vínculos | Não existe | Sim | Média | fase 23 |
| DOCX | Geração ativa por tipo | Núcleo pronto, consumo pendente | Sim | Alta | fase 18 |
| PDF | Geração com checks de backend | Contrato parcial | Sim | Alta | fase 19 |
| placeholders | Extração/substituição/validação | Núcleo V1.1 com contrato | Parcial | Alta | falta integração por domínio |
| assinaturas | Configuração por tipo documental | Base de cadastro pronta | Parcial | Alta | integrar no payload final |
| retificação | Comportamento implícito no legado | Não | Sim | Média | definir regra explícita |
| autosave | Presente no wizard | Não | Sim | Média | opcional em formulários longos |
| validações | Distribuídas por model/form/service | Mínimas | Sim | Alta | ampliar cobertura de negócio |
| mensagens | Mensagens funcionais de pendência | Básicas | Sim | Média | padronizar feedback de completude |
| templates | Wizard + docs + globais | CRUD simples | Sim | Média | evoluir para componentes de domínio |
| JS | Alto uso em fluxo e preview | JS básico | Sim | Média | reescrever sem copiar legado |

## Delta aplicado na Etapa 1 (página 3)
- `data_criacao`: agora automática e informativa na UI.
- `protocolo`: normalizado para dígitos e exibido com máscara.
- `status`: cálculo automático com transição para `GERADO` em `save_continue` quando completo.
- `assunto`: removido da UI da Etapa 1 (mantido apenas para compatibilidade interna).
- `motivo`: bloco único com suporte a modelo de motivo ativo.
- `contexto operacional`: removido da Etapa 1.
- `custeio`: consolidado no bloco "Dados do ofício".
- `viajantes`: seleção com filtro progressivo e fallback sem JS.

