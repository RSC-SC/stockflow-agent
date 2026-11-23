"""Definição do Grafo de Execução do Agente de Estoque com LangGraph.

Este módulo implementa a máquina de estados (StateGraph) responsável por orquestrar:
1. Nó Decisor (agent): Avalia a entrada do usuário e decide se necessita consultar a API.
2. Transição Condicional (should_continue): Roteia para o nó de ferramentas ou finaliza.
3. Nó de Ferramentas (tools): Executa a consulta de estoque.
4. Nó de Análise de Negócio (analysis): Calcula a situação de estoque (disponível, baixo, esgotado)
   e define alertas para o n8n.
5. Condição de Término (END): Garante parada controlada do agente.
"""

from typing import Any, Callable, Dict, List, Literal, Optional
from src.agent.state import AgentState, StockStatus

# Importação condicional para permitir compatibilidade em diferentes ambientes
try:
    from langgraph.graph import END, START, StateGraph
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    LANGGRAPH_AVAILABLE = False
    START = "__start__"
    END = "__end__"

    class StateGraph:  # type: ignore
        """Fallback leve para representação e execução estrutural do grafo."""

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
    """Executor simplificado para o fallback de StateGraph."""

    def __init__(self, graph: StateGraph):
        self.graph = graph

    def invoke(self, initial_state: AgentState) -> AgentState:
        state = dict(initial_state)
        current_node = "agent"

        # Proteção contra loops infinitos (máximo de 10 passos)
        for _ in range(10):
            if current_node == END or current_node not in self.graph.nodes:
                break

            node_func = self.graph.nodes[current_node]
            step_output = node_func(state)
            if isinstance(step_output, dict):
                state.update(step_output)

            # Verifica arestas condicionais
            if current_node in self.graph.conditional_edges:
                router_func, path_map = self.graph.conditional_edges[current_node]
                next_step = router_func(state)
                current_node = path_map.get(next_step, next_step)
            else:
                # Arestas normais
                next_nodes = [dst for src, dst in self.graph.edges if src == current_node]
                current_node = next_nodes[0] if next_nodes else END

        return state  # type: ignore


# ---------------------------------------------------------------------------
# Funções dos Nós e Transições
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Transição condicional: decide se o fluxo deve executar ferramentas ou encerrar.
    
    Regra:
    - Se houver `stock_query` pendente ou chamadas de tool na última mensagem -> 'tools'.
    - Caso contrário (pergunta conceitual já respondida ou encerramento) -> END.
    """
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        # Suporta tanto objetos langchain com tool_calls quanto dicts de mensagens
        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls:
            return "tools"
        if isinstance(last_message, dict) and last_message.get("tool_calls"):
            return "tools"

    # Se uma busca de estoque foi explicitamente sinalizada no estado
    if state.get("stock_query") and not state.get("product_data"):
        return "tools"

    return END


def evaluate_stock_level(quantidade_atual: int, estoque_minimo: int) -> tuple[StockStatus, bool]:
    """Regra de negócio pura para classificar a situação do estoque.
    
    Retorna:
        tuple[StockStatus, bool]: (status_classificado, alert_triggered)
    """
    if quantidade_atual <= 0:
        return "esgotado", True
    if quantidade_atual < estoque_minimo:
        return "baixo", True
    return "disponivel", False


def analysis_node(state: AgentState) -> Dict[str, Any]:
    """Nó de análise de estoque: calcula o status e avalia se aciona alerta para o n8n."""
    product = state.get("product_data")
    if not product:
        return {
            "stock_status": "nao_encontrado" if state.get("stock_query") else "nao_aplicavel",
            "alert_triggered": False,
            "action_taken": "analysis_completed_without_product",
        }

    qtd = int(product.get("quantidade_atual", 0))
    minimo = int(product.get("estoque_minimo", 0))
    status, alert = evaluate_stock_level(qtd, minimo)

    return {
        "stock_status": status,
        "alert_triggered": alert,
        "action_taken": f"analysis_completed_{status}",
    }


def create_stock_graph(
    agent_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
    tools_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
    analysis_node_fn: Optional[Callable[[AgentState], Dict[str, Any]]] = None,
) -> Any:
    """Constrói e compila o grafo do LangGraph para o StockFlow Agent.
    
    Args:
        agent_node_fn: Função executada pelo nó decisor (default: agente com LLM/router).
        tools_node_fn: Função executada pelo nó de ferramentas (default: consulta API estoque).
        analysis_node_fn: Função executada pelo nó de análise de regras de negócio.
        
    Returns:
        Grafo compilado pronto para execução via `.invoke()`.
    """
    workflow = StateGraph(AgentState)

    # Nós padrão se não injetados customizados
    def default_agent_node(s: AgentState) -> Dict[str, Any]:
        return {"action_taken": "agent_decision"}

    def default_tools_node(s: AgentState) -> Dict[str, Any]:
        return {"action_taken": "tools_executed"}

    # Registra nós no grafo
    workflow.add_node("agent", agent_node_fn or default_agent_node)
    workflow.add_node("tools", tools_node_fn or default_tools_node)
    workflow.add_node("analysis", analysis_node_fn or analysis_node)

    # Fluxo de execução e transições
    workflow.add_edge(START, "agent")

    # Transição condicional a partir do agente
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )

    # Conexões lineares após ferramentas
    workflow.add_edge("tools", "analysis")
    workflow.add_edge("analysis", END)

    return workflow.compile()
