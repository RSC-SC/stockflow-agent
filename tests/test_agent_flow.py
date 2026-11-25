"""Testes de fluxo de ponta a ponta para os cenários obrigatórios do Agente."""

from src.agent.graph import create_stock_graph
from src.agent.state import AgentState


def test_cenario_1_produto_existente_baixo_estoque():
    """Cenário 1: Pergunta sobre produto com estoque abaixo do mínimo (PRD-001).
    
    Verifica se o fluxo aciona a ferramenta, executa a análise de estoque e ativa o alerta.
    """
    graph = create_stock_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "Qual o estoque do Mouse sem fio PRD-001?"}],
    }

    result = graph.invoke(initial_state)

    assert result is not None
    assert result.get("stock_query") == "PRD-001"
    assert result.get("stock_status") == "baixo"
    assert result.get("alert_triggered") is True
    assert result.get("product_data") is not None
    assert result["product_data"]["codigo"] == "PRD-001"

    # Verifica se a mensagem final formatada foi gerada
    last_msg = result["messages"][-1]
    msg_content = getattr(last_msg, "content", "") if hasattr(last_msg, "content") else str(last_msg)
    assert "PRD-001" in msg_content
    assert "ESTOQUE BAIXO" in msg_content


def test_cenario_2_produto_inexistente_404():
    """Cenário 2: Pergunta sobre código inexistente (PRD-999).
    
    Verifica se o agente trata graciosamente a ausência sem quebrar ou alucinar saldo.
    """
    graph = create_stock_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "Consulte a quantidade do item PRD-999"}],
    }

    result = graph.invoke(initial_state)

    assert result is not None
    assert result.get("stock_query") == "PRD-999"
    assert result.get("stock_status") == "nao_encontrado"
    assert result.get("alert_triggered") is False

    last_msg = result["messages"][-1]
    msg_content = getattr(last_msg, "content", "") if hasattr(last_msg, "content") else str(last_msg)
    assert "não localizado" in msg_content or "não foi encontrado" in msg_content


def test_cenario_3_pergunta_conceitual_sem_tool():
    """Cenário 3: Pergunta puramente conceitual.
    
    Verifica se o agente responde diretamente no nó 'agent' e encerra em END sem chamar tools.
    """
    graph = create_stock_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "O que é estoque de segurança e para que serve?"}],
    }

    result = graph.invoke(initial_state)

    assert result is not None
    # Verifica que o nó de tools e nó de análise NÃO foram acionados para produtos
    assert result.get("product_data") is None
    assert result.get("stock_status") is None or result.get("stock_status") == "nao_aplicavel"
    assert result.get("action_taken") == "agent_decision"

    last_msg = result["messages"][-1]
    msg_content = getattr(last_msg, "content", "") if hasattr(last_msg, "content") else str(last_msg)
    assert "Estoque de Segurança" in msg_content or "segurança" in msg_content.lower()


def test_cenario_listagem_catalogo():
    """Valida fluxo de listagem geral do catálogo de produtos."""
    graph = create_stock_graph()
    initial_state: AgentState = {
        "messages": [{"role": "user", "content": "Por favor, liste todos os produtos do catalogo"}],
    }

    result = graph.invoke(initial_state)

    assert result is not None
    assert result.get("product_data") is not None
    assert "produtos" in result["product_data"]
    assert len(result["product_data"]["produtos"]) >= 12

    last_msg = result["messages"][-1]
    msg_content = getattr(last_msg, "content", "") if hasattr(last_msg, "content") else str(last_msg)
    assert "Catálogo de Estoque" in msg_content
