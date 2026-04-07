# Contexto do Projeto

## Resumo

Este projeto e um sistema de controle financeiro pessoal feito em Django. O foco atual esta na experiencia web server-rendered, com navegacao simples, filtros mensais e operacoes rapidas sobre lancamentos.

## Objetivo

Permitir que um usuario autenticado acompanhe receitas, despesas e saldo do mes, organize os dados por secoes/categorias e controle o que ja foi pago ou ainda esta pendente.

## Estado atual

- Projeto funcional com telas principais prontas
- Persistencia em PostgreSQL via `DATABASE_URL`
- Autenticacao usando o sistema padrao do Django
- Layout baseado em templates Django e CSS proprio em `static/style.css`
- Cobertura de testes ainda enxuta

## Entidades centrais

### `Account`

- representa uma conta do usuario
- possui `owner`
- possui `initial_balance`

### `Category`

- separa receitas (`IN`) e despesas (`EX`)
- hoje nao esta vinculada diretamente ao usuario

### `Transaction`

- pertence a uma conta e categoria
- possui valor, data, descricao e status
- suporta parcelamento por `group_id`, `installment_no` e `installment_count`
- suporta recorrencia simples por `is_fixed`

## Regras de negocio relevantes

- despesas devem ficar negativas; se o usuario informar positivo, a view converte
- receitas ficam positivas
- status validos:
  - `PEN` para pendente
  - `PAG` para paga
- transacoes parceladas:
  - distribuem o valor total entre as parcelas
  - a primeira pode nascer paga; as demais ficam pendentes
  - nunca devem ser marcadas como fixas
- importacao de fixas:
  - copia do mes anterior para o atual
  - so considera `is_fixed=True`
  - ignora parceladas
  - evita duplicar lancamentos identicos no destino
- tela de despesas:
  - agrupa por categoria
  - mostra total por secao
  - deixa o totalizador verde quando todas as transacoes da secao estao pagas

## Fluxo de telas

- `dashboard.html`
  - resumo do mes
  - totais pagos e pendentes
  - grafico de despesas por categoria
  - saldos por conta
- `new_transaction.html`
  - criacao de transacao com presets por querystring
- `edit_transaction.html`
  - manutencao de transacao existente
- `receitas.html`
  - agrupamento mensal por categoria de receita
- `despesas.html`
  - agrupamento mensal por categoria de despesa
- `transacoes.html`
  - listagem geral com filtros

## Arquivos importantes

- `controle_financeiro/settings.py`
  - configuracao do projeto, banco, timezone e templates
- `controle_financeiro/urls.py`
  - roteamento principal
- `core/models.py`
  - dominio principal
- `core/views.py`
  - regras de negocio das telas
- `templates/`
  - interface server-rendered
- `static/style.css`
  - identidade visual principal

## Convencoes uteis para continuar o projeto

- manter logica de negocio principal em `core/views.py` enquanto a aplicacao continuar pequena
- preservar o padrao atual de valores negativos para despesas
- ao alterar telas de receitas/despesas, verificar impacto na navegacao por mes
- ao mexer em parcelamento ou fixas, validar os efeitos cruzados nas views:
  - `new_transaction`
  - `edit_transaction`
  - `import_fixed`
- sempre que possivel, adicionar teste ao corrigir regra de negocio

## Riscos e pontos de atencao

- as categorias sao globais; isso pode ser um problema em ambiente multiusuario
- alguns arquivos exibem sinais de encoding inconsistente em textos acentuados
- a base de testes ainda nao cobre o fluxo completo das views
- o projeto depende de variaveis de ambiente para subir corretamente

## Proximos passos recomendados

- criar testes para importacao de fixas e parcelamento
- adicionar validacoes mais explicitas em formularios
- considerar separar servicos/helpers da camada de view conforme a complexidade crescer
- documentar melhor o processo de popular dados iniciais
