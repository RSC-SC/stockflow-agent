# Documentação e Mapeamento da API de Estoque (Cloud)

Este documento descreve a infraestrutura, os contratos e os cenários de teste da **API de Estoque** (FastAPI) implantada em ambiente Cloud junto à instância do **n8n**.

---

## 🌐 Informações de Acesso

* **URL Base:** `http://150.136.45.59:8082`
* **Swagger UI:** `http://150.136.45.59:8082/docs`
* **OpenAPI Schema:** `http://150.136.45.59:8082/openapi.json`
* **Versão da API:** 1.0.0
* **Status do Serviço:** Operacional (verificado via `GET /health`)

---

## 📋 Endpoints Disponíveis

| Método | Endpoint | Descrição | Status Sucesso |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Verificação de disponibilidade da API | `200 OK` |
| `GET` | `/produtos` | Listagem geral de produtos (filtro opcional `?categoria=`) | `200 OK` |
| `GET` | `/produtos/{codigo}` | Consulta de produto por código (padrão `PRD-XXX`) | `200 OK` |
| `POST` | `/produtos` | Cadastro de novo produto no inventário | `201 Created` |
| `GET` | `/categorias` | Listagem de categorias existentes | `200 OK` |

---

## 📦 Estrutura do Objeto `Produto`

```json
{
  "codigo": "PRD-001",
  "nome": "Mouse sem fio",
  "categoria": "Periféricos",
  "quantidade_atual": 5,
  "estoque_minimo": 10,
  "unidade": "un"
}
```

---

## 🧪 Cenários de Teste Mapeados para o Agente e n8n

A API disponibiliza 12 produtos fictícios pré-cadastrados com variações de estoque ideais para validação dos cenários obrigatórios do projeto:

### 1. Produtos com Estoque Crítico / Abaixo do Mínimo (Dispara Alerta no n8n)
* **`PRD-001` (Mouse sem fio):** 5 un (Mínimo: 10 un) $\rightarrow$ **Estoque Baixo**
* **`PRD-004` (Cabo HDMI 2 m):** 0 un (Mínimo: 20 un) $\rightarrow$ **Esgotado**
* **`PRD-007` (Cartucho de tinta preta):** 3 un (Mínimo: 8 un) $\rightarrow$ **Estoque Baixo**
* **`PRD-008` (Webcam Full HD):** 0 un (Mínimo: 5 un) $\rightarrow$ **Esgotado**
* **`PRD-011` (Álcool isopropílico):** 4 L (Mínimo: 10 L) $\rightarrow$ **Estoque Baixo**

### 2. Produtos com Estoque Normal / Regular
* **`PRD-002` (Teclado USB):** 40 un (Mínimo: 15 un) $\rightarrow$ **Disponível**
* **`PRD-003` (Monitor 24 polegadas):** 12 un (Mínimo: 5 un) $\rightarrow$ **Disponível**
* **`PRD-006` (Caneta esferográfica azul):** 200 un (Mínimo: 50 un) $\rightarrow$ **Disponível**
* **`PRD-010` (Pen drive 64 GB):** 25 un (Mínimo: 10 un) $\rightarrow$ **Disponível**

### 3. Cenários de Erro e Tratamento de Exceções
* **Produto Inexistente (HTTP 404):**
  * Chamada: `GET /produtos/PRD-999`
  * Retorno: `{"erro": "produto_nao_encontrado", "mensagem": "Produto não encontrado."}`
* **Simulação Determinística de Serviço Indisponível (HTTP 503):**
  * Chamada: `GET /produtos/PRD-503`
  * Retorno: `{"erro": "servico_indisponivel", "mensagem": "Serviço temporariamente indisponível. Tente novamente mais tarde."}`
* **Código Inválido (HTTP 422):**
  * Códigos fora do regex `^PRD-[0-9]{3}$`.
