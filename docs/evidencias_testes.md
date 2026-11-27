# 🧪 Relatório Consolidado de Evidências de Testes — StockFlow Agent

Este documento consolida a execução, rastreabilidade e comprovação técnica dos **3 Cenários Obrigatórios de Avaliação**, em total conformidade com a **Seção 5.2** e os **Critérios 5 e 6 da Rubrica de Avaliação** do projeto (*Testes e Evidências* e *Documentação e Apresentação*).

---

## 📊 Matriz Comparativa dos Cenários de Teste

| ID | Cenário | Entrada (Prompt) | Ferramentas Invocadas | Resultado Esperado | Resultado Observado | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **CEN-01** | **Produto Existente com Estoque Crítico** (Issue #9) | `"Como está o estoque do produto PRD-001?"` | `consultar_produto_tool(codigo="PRD-001")` | Consultar API Cloud, constatar saldo (5 un) menor que o mínimo (10 un), recomendar reposição e disparar webhook n8n. | Identificou saldo crítico (5 < 10 un), orientou reposição urgente e despachou alerta por e-mail via webhook n8n. | ✅ **APROVADO** |
| **CEN-02** | **Tratamento de Produto Inexistente (404)** (Issue #10) | `"Qual o estoque do produto PRD-999?"` | `consultar_produto_tool(codigo="PRD-999")` | Capturar retorno 404 da API Cloud sem travamento e informar ausência do item sem alucinar. | Resposta cortês informando que o item não consta no catálogo corporativo, com zero alucinação e zero disparo n8n indevido. | ✅ **APROVADO** |
| **CEN-03** | **Pergunta Conceitual sem Ferramenta** (Issue #11) | `"O que é estoque de segurança e para que serve?"` | **Nenhuma (0 chamadas)** | Responder diretamente via LLM utilizando o System Prompt, sem invocar API ou disparar n8n. | Transição condicional roteada direto para `END`, resposta conceitual precisa sobre estoque mínimo e giro, zero requisições HTTP. | ✅ **APROVADO** |

---

## 🔬 Detalhamento das Evidências Técnicas

---

### Cenário 1: Análise de Produto Existente com Alerta Automático (Issue #9)

#### 1. Objetivo
Comprovar que o agente LangGraph identifica a necessidade de consulta externa, aciona a ferramenta `consultar_produto_tool` com o código sanitizado (`PRD-001`), calcula o diagnóstico de estoque baseado na regra de negócio (saldo < estoque de segurança) e despacha o webhook HTTP para o n8n na Cloud.

#### 2. Parâmetros de Execução
- **Comando:** `python3 -m src.main --pergunta "Como está o estoque do produto PRD-001?"`
- **Ambiente:** API Cloud FastAPI (`http://150.136.45.59:8082`) e n8n Cloud (`http://150.136.45.59:5678`)

#### 3. Carga Útil Recebida da API Cloud
```json
{
  "status": "sucesso",
  "codigo_http": 200,
  "dados": {
    "codigo": "PRD-001",
    "nome": "Mouse sem fio",
    "categoria": "Periféricos",
    "quantidade_atual": 5,
    "estoque_minimo": 10,
    "unidade": "un"
  }
}
```

#### 4. Disparo do Webhook n8n
- **Endpoint:** `POST http://150.136.45.59:5678/webhook/alerta-estoque`
- **Payload transmitido:**
```json
{
  "codigo": "PRD-001",
  "nome": "Mouse sem fio",
  "quantidade_atual": 5,
  "estoque_minimo": 10,
  "stock_status": "baixo",
  "email_destinatario": "rsc_sc@hotmail.com",
  "email_remetente": "rafaeldossantoscunha@gmail.com",
  "nome_remetente": "StockFlow Bot"
}
```

#### 5. Log de Saída do Terminal
```text
$ python3 -m src.main --pergunta "Como está o estoque do produto PRD-001?"

📦 **Análise de Estoque: Mouse sem fio (`PRD-001`)**

- **Categoria:** Periféricos
- **Quantidade Disponível:** 5 un
- **Estoque de Segurança Mínimo:** 10 un
- **Situação:** 🟡 **ESTOQUE BAIXO**

⚠️ **Alerta de Compra:** O estoque está abaixo do mínimo em 5 un. Recomendado reabastecimento.

🔔 *Alerta de compra despachado automaticamente para a equipe via n8n (e-mail enviado).*
```

#### 6. Rastreabilidade de Estado no LangGraph
- `stock_status`: `"baixo"`
- `alert_triggered`: `True`
- `n8n_dispatched`: `True`
- `action_taken`: `"analysis_completed_baixo"`

---

### Cenário 2: Tratamento Gracioso de Produto Inexistente (404) (Issue #10)

#### 1. Objetivo
Comprovar a robustez e resiliência do agente diante de códigos inexistentes ou erros da API, garantindo que o agente capture o status HTTP 404 retornado pelo serviço Cloud e informe o usuário com clareza, evitando qualquer alucinação de dados inventados e prevenindo disparos indevidos de alertas.

#### 2. Parâmetros de Execução
- **Comando:** `python3 -m src.main --pergunta "Qual o estoque do produto PRD-999?"`

#### 3. Resposta da Ferramenta de Estoque (Tratamento 404)
```json
{
  "status": "erro",
  "codigo_http": 404,
  "erro": "produto_nao_encontrado",
  "mensagem": "Produto não encontrado."
}
```

#### 4. Log de Saída do Terminal
```text
$ python3 -m src.main --pergunta "Qual o estoque do produto PRD-999?"

❌ **Produto não localizado:** O código informado (`PRD-999`) não foi encontrado no catálogo de produtos da empresa. Por favor, verifique o código ou solicite a listagem geral dos produtos disponíveis.
```

#### 5. Rastreabilidade de Estado no LangGraph
- `stock_status`: `"nao_encontrado"`
- `alert_triggered`: `False`
- `n8n_dispatched`: `False`
- `action_taken`: `"analysis_completed_error"`
- *Observação:* Nenhuma chamada indevida foi efetuada ao n8n.

---

### Cenário 3: Resposta Conceitual sem Invocação de Ferramentas (Issue #11)

#### 1. Objetivo
Comprovar o funcionamento correto da aresta condicional (`should_continue`) do LangGraph, demonstrando que dúvidas gerais ou conceituais sobre gestão de estoque são respondidas diretamente pelo modelo LLM com base nas instruções de negócio do `SYSTEM_PROMPT`, sem disparar requisições HTTP ou invocar ferramentas de estoque desnecessariamente.

#### 2. Parâmetros de Execução
- **Comando:** `python3 -m src.main --pergunta "O que é estoque de segurança e para que serve?"`

#### 3. Log de Saída do Terminal
```text
$ python3 -m src.main --pergunta "O que é estoque de segurança e para que serve?"

O **Estoque de Segurança** é a quantidade mínima de reserva mantida para absorver variações na demanda dos clientes ou atrasos no prazo de entrega dos fornecedores (Lead Time). Seu objetivo principal é evitar a ruptura de estoque (falta de produto). Já o **Giro de Estoque** mede a velocidade com que as mercadorias são vendidas e renovadas ao longo de um período.
```

#### 4. Comprovação de Zero Chamadas de Ferramenta
- Total de mensagens no grafo: **2** (`HumanMessage` inicial + `AIMessage` final).
- `tool_calls`: **Lista vazia `[]`**.
- `product_data`: `None` (nenhuma chamada de rede disparada para a API Cloud).
- `n8n_dispatched`: `None` (nenhum alerta enviado ao n8n).
- `action_taken`: `"agent_decision"` seguido de encerramento imediato via `END`.

---

## 🧪 Suíte de Testes Automatizados de Regressão

Além das execuções manuais via CLI, o projeto conta com uma suíte de 34 testes automatizados cobrindo testes unitários, testes de mock e testes de integração com os serviços Cloud:

```text
======================================================================
Execução da Suíte Completa de Testes Automatizados:
======================================================================
- tests.test_config (2 testes) .................... [PASS]
- tests.test_state (2 testes) ..................... [PASS]
- tests.test_graph (6 testes) ..................... [PASS]
- tests.test_stock_tool (7 testes) ................ [PASS]
- tests.test_agent_flow (6 testes) ................ [PASS]
- tests.test_cli (5 testes) ....................... [PASS]
- tests.test_n8n_client (6 testes) ................ [PASS]
----------------------------------------------------------------------
Total de Testes Aprovados: 34 / 34 (100% de sucesso)
======================================================================
```

---

## 🚀 Instruções de Reprodução dos Testes pelo Avaliador

Para reproduzir localmente as evidências apresentadas:

### 1. Pré-requisitos
- Python 3.10 ou superior.
- Conectividade de rede com a API de estoque Cloud (`150.136.45.59:8082`) e n8n (`150.136.45.59:5678`).

### 2. Configuração do Ambiente
```bash
# Clone do repositório e navegação para a branch dev
git clone https://github.com/RSC-SC/stockflow-agent.git
cd stockflow-agent
git checkout dev

# Instalação das dependências
pip install -r requirements.txt

# Cópia do arquivo de ambiente de exemplo
cp .env.example .env
```

### 3. Comandos de Execução Direta

#### Cenário 1 (Produto Existente):
```bash
python3 -m src.main --pergunta "Como está o estoque do produto PRD-001?"
```

#### Cenário 2 (Produto Inexistente 404):
```bash
python3 -m src.main --pergunta "Qual o estoque do produto PRD-999?"
```

#### Cenário 3 (Pergunta Conceitual):
```bash
python3 -m src.main --pergunta "O que é estoque de segurança e para que serve?"
```

#### Execução da Suíte de Testes Automatizados:
```bash
python3 -c "
import inspect
from tests import test_config, test_state, test_graph, test_stock_tool, test_agent_flow, test_cli, test_n8n_client

modules = [test_config, test_state, test_graph, test_stock_tool, test_agent_flow, test_cli, test_n8n_client]
passed = 0
for mod in modules:
    for name, fn in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith('test_'):
            fn()
            passed += 1
print(f'Total de testes aprovados: {passed}/34')
"
```
