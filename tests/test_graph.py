"""Testes unitários para o grafo do LangGraph e transições condicionais."""

from src.agent.graph import (
    create_stock_graph,
    should_continue,
    evaluate_stock_level,
    analysis_node,
    END,
)
from src.agent.state import AgentState


def test_evaluate_stock_level_esgotado():
    """Valida regra de negócio para estoque zerado."""
    status, alert = evaluate_stock_level(quantidade_atual=0, estoque_minimo=10)
    assert status == "esgotado"
    assert alert is True


def test_evaluate_stock_level_baixo():
    """Valida regra de negócio para estoque abaixo do mínimo."""
    status, alert = evaluate_stock_level(quantidade_atual=5, estoque_minimo=10)
    assert status == "baixo"
    assert alert is True


def test_evaluate_stock_level_disponivel():
    """Valida regra de negócio para estoque suficiente."""
    status, alert = evaluate_stock_level(quantidade_atual=15, estoque_minimo=10)
    assert status == "disponivel"
    assert alert is False


def test_should_continue_router_to_tools():
    """Valida transição condicional roteando para ferramentas quando há busca pendente."""
    state_with_tool: AgentState = {
        "messages": [{"role": "assistant", "tool_calls": [{"name": "consultar_estoque"}]}],
        "stock_query": "PRD-001",
        "product_data": None,
        "alert_triggered": False,
    }
    decision = should_continue(state_with_tool)
    assert decision == "tools"


def test_should_continue_router_to_end():
    """Valida transição condicional roteando para END quando não há ferramentas."""
    state_without_tool: AgentState = {
        "messages": [{"role": "assistant", "content": "Estoque de segurança é a quantidade mínima..."}],
        "stock_query": None,
        "product_data": None,
        "alert_triggered": False,
    }
    decision = should_continue(state_without_tool)
    assert decision == END


def test_analysis_node_processing():
    """Valida processamento do nó de análise."""
    state: AgentState = {
        "stock_query": "PRD-001",
        "product_data": {
            "codigo": "PRD-001",
            "nome": "Mouse sem fio",
            "quantidade_atual": 4,
            "estoque_minimo": 10,
        },
        "alert_triggered": False,
    }
    output = analysis_node(state)
    assert output["stock_status"] == "baixo"
    assert output["alert_triggered"] is True


def test_graph_compilation_and_execution():
    """Valida compilação e execução estrutural do grafo de ponta a ponta."""
    graph = create_stock_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "O que é estoque?"}],
        "stock_query": None,
        "product_data": None,
        "alert_triggered": False,
    }

    result = graph.invoke(initial_state)
    assert result is not None
    assert result.get("action_taken") == "agent_decision"
