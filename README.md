# FinCtrl

Aplicacao web em Django para controle financeiro pessoal, com foco em receitas, despesas, transacoes por periodo, contas, categorias, lancamentos fixos e parcelamentos.

## Stack

- Python 3
- Django 5
- PostgreSQL via `DATABASE_URL`
- Templates Django + Bootstrap

## Funcionalidades

- Dashboard mensal com totais de receitas, despesas, saldo, pagos e pendentes
- Cadastro de transacoes com suporte a:
  - receita e despesa
  - status pago/pendente
  - parcelamento
  - marcacao como lancamento fixo
- Edicao, exclusao e troca rapida de status
- Visualizacao por secoes:
  - `Receitas`
  - `Despesas`
- Importacao de lancamentos fixos do mes anterior
- Filtro de transacoes por mes, conta, status e busca por descricao

## Estrutura

```text
controle_financeiro/
|-- controle_financeiro/   # settings, urls, asgi, wsgi
|-- core/                  # models, views, tests, migrations
|-- static/                # CSS global
|-- templates/             # telas HTML
|-- manage.py
|-- requirements.txt
```

## Modelos principais

- `Account`: conta do usuario com saldo inicial
- `Category`: categoria de receita (`IN`) ou despesa (`EX`)
- `Transaction`: lancamento financeiro com data, valor, status, categoria, conta e metadados de parcelamento/fixo

Regra importante:
- despesas sao persistidas com valor negativo
- receitas sao persistidas com valor positivo

## Como rodar localmente

1. Criar e ativar um ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Criar um arquivo `.env` na raiz com algo como:

```env
SECRET_KEY=dev-secret
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
TIME_ZONE=America/Sao_Paulo
DATABASE_URL=postgresql://postgres:senha@localhost:5432/controle_financeiro
```

4. Aplicar migracoes:

```powershell
python manage.py migrate
```

5. Criar um usuario admin:

```powershell
python manage.py createsuperuser
```

6. Subir o servidor:

```powershell
python manage.py runserver
```

7. Acessar:

- App: `http://127.0.0.1:8000/`
- Login padrao quando nao autenticado: `http://127.0.0.1:8000/admin/login/`

## Rotas principais

- `/` - dashboard
- `/receitas/` - secoes de receitas
- `/despesas/` - secoes de despesas
- `/transacoes/` - listagem filtravel de transacoes
- `/transacoes/nova/` - novo lancamento
- `/transacoes/<id>/editar/` - edicao
- `/transacoes/<id>/excluir/` - exclusao
- `/transacoes/<id>/toggle/` - alterna pago/pendente
- `/fixas/importar/<kind>/` - importa fixas do mes anterior

## Testes

```powershell
python manage.py test
```

Se o comando falhar com erro de importacao do Django, verifique se o ambiente virtual esta ativado e se as dependencias foram instaladas.

## Observacoes de negocio

- Ao parcelar uma transacao, o sistema distribui os centavos entre as parcelas
- Apenas a primeira parcela herda o status escolhido no cadastro; as demais nascem pendentes
- Lancamentos fixos so valem para transacoes simples, nao parceladas
- A importacao de fixas evita duplicar um lancamento identico no mes de destino
- Na tela de despesas, o total da secao fica verde quando todos os itens daquela secao estao pagos

## Melhorias futuras sugeridas

- ampliar cobertura de testes
- adicionar seeds/dados iniciais
- proteger categorias por usuario, caso isso faca sentido para o produto
- revisar encoding de alguns textos exibidos nos templates/arquivos
