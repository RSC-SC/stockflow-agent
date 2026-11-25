"""Testes automatizados para a interface CLI e helper de processamento."""

from src.main import format_agent_response, process_user_query
from src.agent.state import AgentState


def test_format_agent_response_empty():
    """Valida tratamento quando não há mensagens."""
    assert format_agent_response({}) == "Nenhuma resposta gerada pelo agente."


def test_format_agent_response_with_dict_message():
    """Valida formatação de mensagem retornada em dicionário."""
    result = {"messages": [{"role": "assistant", "content": "Teste de resposta"}]}
    assert format_agent_response(result) == "Teste de resposta"


def test_process_user_query_product():
    """Valida processamento de consulta via process_user_query para produto PRD-001."""
    resposta, new_state = process_user_query("Qual o estoque do PRD-001?")
    assert resposta != ""
    assert "PRD-001" in resposta
    assert new_state.get("stock_query") == "PRD-001"
    assert new_state.get("stock_status") == "baixo"
    assert len(new_state.get("messages", [])) >= 2


def test_process_user_query_conceptual():
    """Valida processamento de consulta conceitual sem tool."""
    resposta, new_state = process_user_query("O que é estoque de segurança?")
    assert resposta != ""
    assert "segurança" in resposta.lower()
    # Verifica que não houve tool nem produto consultado
    assert new_state.get("product_data") is None


def test_process_user_query_state_accumulation():
    """Valida acúmulo de turnos sucessivos de conversa no mesmo estado."""
    resp1, state1 = process_user_query("O que é estoque de segurança?")
    resp2, state2 = process_user_query("Qual o estoque do Mouse sem fio PRD-001?", state=state1)

    assert len(state2.get("messages", [])) > len(state1.get("messages", []))
    assert state2.get("stock_query") == "PRD-001"
