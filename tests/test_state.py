"""Testes unitários para o AgentState e gerenciamento de estado."""

from src.agent.state import AgentState, add_messages


def test_agent_state_initialization():
    """Valida instanciação e campos opcionais do AgentState."""
    state: AgentState = {
        "messages": [],
        "stock_query": "PRD-001",
        "product_data": {
            "codigo": "PRD-001",
            "nome": "Mouse sem fio",
            "quantidade_atual": 5,
            "estoque_minimo": 10,
            "unidade": "un",
        },
        "stock_status": "baixo",
        "alert_triggered": True,
        "action_taken": "tool_call",
    }

    assert state["stock_query"] == "PRD-001"
    assert state["stock_status"] == "baixo"
    assert state["alert_triggered"] is True
    assert state["product_data"]["quantidade_atual"] == 5


def test_add_messages_reducer():
    """Valida o funcionamento do reducer add_messages na acumulação do histórico."""
    initial_messages = [{"role": "user", "content": "Consultar estoque PRD-001"}]
    new_message = [{"role": "assistant", "content": "O estoque do PRD-001 está baixo."}]

    combined = add_messages(initial_messages, new_message)

    assert len(combined) == 2
    assert combined[0]["content"] == "Consultar estoque PRD-001"
    assert combined[1]["content"] == "O estoque do PRD-001 está baixo."


def test_state_with_single_message_append():
    """Valida adição de uma única mensagem (não lista) via reducer."""
    initial = [{"role": "user", "content": "Olá"}]
    combined = add_messages(initial, {"role": "assistant", "content": "Olá, como posso ajudar?"})

    assert len(combined) == 2
    assert combined[1]["role"] == "assistant"
