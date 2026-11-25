"""Definição do Grafo de Execução do Agente de Estoque com LangGraph.

Este módulo implementa a máquina de estados (StateGraph) responsável por orquestrar:
1. Nó Decisor (agent): Avalia a entrada do usuário e aciona a LLM vinculada às tools.
2. Transição Condicional (should_continue): Roteia para execução de ferramenta ou encerramento.
3. Nó de Ferramentas (tools): Executa a consulta de estoque via API Cloud.
4. Nó de Análise de Negócio (analysis): Calcula o diagnóstico de estoque e define alertas para o n8n.
5. Condição de Término (END): Garante parada controlada do agente sem loops infinitos.
"""

import json
from typing import Any, Callable, Dict, List, Literal, Optional

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.state import AgentState, StockStatus
from src.agent.llm import get_llm
from src.tools.stock_tool import (
    consultar_produto_tool,
    listar_produtos_tool,
    verificar_saude_api_tool,
)

# Importação condicional do LangGraph / LangChain com fallback
try:
    from langgraph.graph import END, START, StateGraph
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    LANGGRAPH_AVAILABLE = False
    START = "__start__"
    END = "__end__"

    class BaseMessage:  # type: ignore
        def __init__(self, content: str = "", **kwargs: Any):
            self.content = content
            for k, v in kwargs.items():
                setattr(self, k, v)

    class AIMessage(BaseMessage):  # type: ignore
        pass

    class HumanMessage(BaseMessage):  # type: ignore
        pass

    class SystemMessage(BaseMessage):  # type: ignore
        pass

    class ToolMessage(BaseMessage):  # type: ignore
        def __init__(self, content: str = "", tool_call_id: str = "", **kwargs: Any):
            super().__init__(content=content, **kwargs)
            self.tool_call_id = tool_call_id

    class StateGraph:  # type: ignore
        def __init__(self, state_schema: Any):
            self.state_schema = state_schema
            self.nodes: Dict[str, Callable] = {}
            self.edges: List[tuple] = []
            self.conditional_edges: Dict[str, tuple] = {}

        def add_node(self, name: str, action: Callable):
            self.nodes[name] = action

        def add_edge(self, start: str, end: str):
            self.edges.append((start, end))

        def add_conditional_edges(self, source: str, path: Callable, path_map: Optional[Dict[str, str]] = None):
            self.conditional_edges[source] = (path, path_map or {})

        def compile(self):
            return CompiledGraphFallback(self)


class CompiledGraphFallback:  # pragma: no cover
    """Executor determinístico de StateGraph para ambientes de teste e fallback."""

    def __init__(self, graph: StateGraph):
        self.graph = graph

    def invoke(self, initial_state: AgentState) -> AgentState:
        state = dict(initial_state)
        current_node = "agent"

        # Proteção contra loops infinitos (máximo de 8 passos por turno)
        for _ in range(8):
            if current_node == END or current_node not in self.graph.nodes:
                break

            node_func = self.graph.nodes[current_node]
            step_output = node_func(state)
            if isinstance(step_output, dict):
                # Se houver mensagens acumuladas, preserva
                if "messages" in step_output:
                    existing_msgs = list(state.get("messages", []))
                    new_msgs = step_output["messages"]
                    existing_msgs.extend(new_msgs if isinstance(new_msgs, list) else [new_msgs])
                    state["messages"] = existing_msgs
                for k, v in step_output.items():
                    if k != "messages":
                        state[k] = v

            # Avalia transição condicional
            if current_node in self.graph.conditional_edges:
                router_func, path_map = self.graph.conditional_edges[current_node]
                next_step = router_func(state)
                current_node = path_map.get(next_step, next_step)
            else:
                next_nodes = [dst for src, dst in self.graph.edges if src == current_node]
                current_node = next_nodes[0] if next_nodes else END

        return state  # type: ignore


# Lista padrão de ferramentas disponíveis para o agente
DEFAULT_TOOLS = [
    consultar_produto_tool,
    listar_produtos_tool,
    verificar_saude_api_tool,
]


# ---------------------------------------------------------------------------
# Regras de Negócio e Classificação de Estoque
# ---------------------------------------------------------------------------

def evaluate_stock_level(quantidade_atual: int, estoque_minimo: int) -> tuple[StockStatus, bool]:
    """Classifica a situação do estoque com base no saldo e estoque de segurança.
    
    Retorna:
        tuple[StockStatus, bool]: (status_classificado, alert_triggered)
    """
    if quantidade_atual <= 0:
        return "esgotado", True
    if quantidade_atual < estoque_minimo:
        return "baixo", True
    return "disponivel", False


# ---------------------------------------------------------------------------
# Nós do LangGraph
# ---------------------------------------------------------------------------

def agent_node(state: AgentState, llm: Optional[Any] = None) -> Dict[str, Any]:
    """Nó Decisor: Avalia o histórico de conversação com o System Prompt e aciona a LLM."""
    model = llm or get_llm(tools=DEFAULT_TOOLS)

    messages = list(state.get("messages", []))
    # Injeta o System Prompt no início se ainda não presente
    has_system = any(
        isinstance(m, SystemMessage) or (isinstance(m, dict) and m.get("role") == "system")
        for m in messages
    )
    if not has_system:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = model.invoke(messages)
    return {
        "messages": [response],
        "action_taken": "agent_decision",
    }


def tools_node(state: AgentState) -> Dict[str, Any]:
    """Nó de Ferramentas: Executa as chamadas solicitadas pelo modelo e captura dados do estoque."""
    messages = state.get("messages", [])
    if not messages:
        return {"action_taken": "tools_skipped_no_messages"}

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", None)
    if not tool_calls and isinstance(last_message, dict):
        tool_calls = last_message.get("tool_calls", [])

    if not tool_calls:
        # Se não há tool_calls explícitas mas há stock_query pendente
        query = state.get("stock_query")
        if query:
            res = consultar_produto_tool(query)
            return {
                "product_data": res.get("dados") if res.get("status") == "sucesso" else res,
                "action_taken": "tools_executed_direct_query",
            }
        return {"action_taken": "tools_skipped_no_calls"}

    tool_messages = []
    product_data = None
    stock_query = None

    for call in tool_calls:
        name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
        args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", "tool_call_0")

        if name == "consultar_produto_tool":
            codigo = args.get("codigo", "")
            stock_query = codigo
            res = consultar_produto_tool(codigo)
            product_data = res.get("dados") if res.get("status") == "sucesso" else res
            content = json.dumps(res, ensure_ascii=False)
            tool_messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

        elif name == "listar_produtos_tool":
            categoria = args.get("categoria")
            res = listar_produtos_tool(categoria=categoria)
            product_data = res.get("dados")
            content = json.dumps(res, ensure_ascii=False)
            tool_messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

        elif name == "verificar_saude_api_tool":
            res = verificar_saude_api_tool()
            content = json.dumps(res, ensure_ascii=False)
            tool_messages.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

    return {
        "messages": tool_messages,
        "product_data": product_data,
        "stock_query": stock_query or state.get("stock_query"),
        "action_taken": "tools_executed",
    }


def analysis_node(state: AgentState) -> Dict[str, Any]:
    """Nó de Análise de Negócio: Calcula a situação do estoque e sintetiza a resposta final."""
    product = state.get("product_data")

    # Caso 1: Produto inexistente ou erro retornado pela tool
    if isinstance(product, dict) and product.get("status") == "erro":
        erro_tipo = product.get("erro", "")
        msg_erro = product.get("mensagem", "Erro ao consultar a API de estoque.")
        if erro_tipo == "produto_nao_encontrado":
            resposta = (
                f"❌ **Produto não localizado:** O código informado (`{state.get('stock_query')}`) "
                "não foi encontrado no catálogo de produtos da empresa. "
                "Por favor, verifique o código ou solicite a listagem geral dos produtos disponíveis."
            )
        elif erro_tipo == "servico_indisponivel":
            resposta = (
                "⚠️ **Serviço Temporariamente Indisponível:** A API de estoque está em manutenção "
                "ou simulando instabilidade. Por favor, tente novamente em alguns instantes."
            )
        else:
            resposta = f"⚠️ **Atenção:** {msg_erro}"

        return {
            "messages": [AIMessage(content=resposta)],
            "stock_status": "nao_encontrado" if erro_tipo == "produto_nao_encontrado" else "erro_api",
            "alert_triggered": False,
            "action_taken": "analysis_completed_error",
        }

    # Caso 2: Listagem de produtos (múltiplos itens)
    if isinstance(product, dict) and "produtos" in product:
        produtos = product.get("produtos", [])
        total = product.get("total", len(produtos))
        linhas = [f"📋 **Catálogo de Estoque ({total} produtos cadastrados):**\n"]
        criticos = 0

        for p in produtos:
            qtd = p.get("quantidade_atual", 0)
            minimo = p.get("estoque_minimo", 0)
            status, _ = evaluate_stock_level(qtd, minimo)
            tag = "🔴 [ESGOTADO]" if status == "esgotado" else ("🟡 [BAIXO]" if status == "baixo" else "🟢 [NORMAL]")
            if status in ["esgotado", "baixo"]:
                criticos += 1
            linhas.append(f"- **{p.get('codigo')}** | {p.get('nome')}: **{qtd} {p.get('unidade')}** (Mín: {minimo}) {tag}")

        linhas.append(f"\n*Total de itens em estado de atenção/reposição: {criticos}*")
        return {
            "messages": [AIMessage(content="\n".join(linhas))],
            "stock_status": "baixo" if criticos > 0 else "disponivel",
            "alert_triggered": criticos > 0,
            "action_taken": "analysis_completed_listing",
        }

    # Caso 3: Produto individual encontrado com sucesso
    if isinstance(product, dict) and "codigo" in product:
        codigo = product.get("codigo", "")
        nome = product.get("nome", "")
        qtd = int(product.get("quantidade_atual", 0))
        minimo = int(product.get("estoque_minimo", 0))
        unidade = product.get("unidade", "un")
        categoria = product.get("categoria", "Geral")

        status, alert = evaluate_stock_level(qtd, minimo)

        if status == "esgotado":
            status_desc = "🔴 **ESGOTADO**"
            orientacao = "🚨 **Ação Imediata:** Produto com estoque zerado! Pedido de reposição urgente necessário."
        elif status == "baixo":
            status_desc = "🟡 **ESTOQUE BAIXO**"
            defasagem = minimo - qtd
            orientacao = f"⚠️ **Alerta de Compra:** O estoque está abaixo do mínimo em {defasagem} {unidade}. Recomendado reabastecimento."
        else:
            status_desc = "🟢 **DISPONÍVEL / NORMAL**"
            orientacao = "✅ **Regular:** O nível de estoque atende à margem de segurança recomendada."

        texto_final = (
            f"📦 **Análise de Estoque: {nome} (`{codigo}`)**\n\n"
            f"- **Categoria:** {categoria}\n"
            f"- **Quantidade Disponível:** {qtd} {unidade}\n"
            f"- **Estoque de Segurança Mínimo:** {minimo} {unidade}\n"
            f"- **Situação:** {status_desc}\n\n"
            f"{orientacao}"
        )

        return {
            "messages": [AIMessage(content=texto_final)],
            "stock_status": status,
            "alert_triggered": alert,
            "action_taken": f"analysis_completed_{status}",
        }

    # Caso 4: Análise sem dados de produto (ex: resposta puramente textual/conceitual já atendida)
    return {
        "stock_status": "nao_aplicavel",
        "alert_triggered": False,
        "action_taken": "analysis_completed_without_product",
    }


def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Transição condicional: roteia para execução de tools ou finaliza em END.
    
    Regra:
    - Se a última mensagem possuir `tool_calls` -> direciona para 'tools'.
    - Caso contrário (pergunta conceitual já respondida pelo modelo) -> END.
    """
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls:
            return "tools"
        if isinstance(last_message, dict) and last_message.get("tool_calls"):
            return "tools"

    # Se uma busca de estoque foi explicitamente sinalizada no estado sem dados
    if state.get("stock_query") and not state.get("product_data"):
        return "tools"

    return END


# ---------------------------------------------------------------------------
# Construtor do Grafo
# ---------------------------------------------------------------------------

def create_stock_graph(
    agent_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
    tools_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
    analysis_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
) -> Any:
    """Constrói e compila o grafo do LangGraph para o StockFlow Agent.
    
    Returns:
        Grafo compilado pronto para execução via `.invoke()`.
    """
    workflow = StateGraph(AgentState)

    # Adiciona nós ao grafo
    workflow.add_node("agent", agent_node_fn or agent_node)
    workflow.add_node("tools", tools_node_fn or tools_node)
    workflow.add_node("analysis", analysis_node_fn or analysis_node)

    # Ponto de entrada
    workflow.add_edge(START, "agent")

    # Aresta condicional a partir do decisor (agent)
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )

    # Fluxo determinístico após execução de ferramentas
    workflow.add_edge("tools", "analysis")
    workflow.add_edge("analysis", END)

    return workflow.compile()
