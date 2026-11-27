"""Testes unitários e de integração para o cliente HTTP do n8n."""

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

from src import config
from src.agent.graph import analysis_node
from src.agent.state import AgentState
from src.tools.n8n_client import disparar_alerta_estoque_n8n


def test_n8n_missing_url():
    """Valida comportamento defensivo quando a URL do webhook não está configurada."""
    prod = {"codigo": "PRD-001", "nome": "Mouse", "quantidade_atual": 2, "estoque_minimo": 10}
    res = disparar_alerta_estoque_n8n(prod, "baixo", webhook_url="")
    assert res["status"] == "ignorado"
    assert res["disparado"] is False


def test_n8n_mocked_success():
    """Valida envio com sucesso quando o n8n responde HTTP 200 via urllib."""
    prod = {
        "codigo": "PRD-001",
        "nome": "Mouse sem fio",
        "quantidade_atual": 5,
        "estoque_minimo": 10,
    }

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.read.return_value = json.dumps({"status": "processado_com_sucesso"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp), \
         patch("src.tools.n8n_client.HTTPX_AVAILABLE", False):
        res = disparar_alerta_estoque_n8n(prod, "baixo", webhook_url="http://mock-n8n/webhook/test")

        assert res["status"] == "sucesso"
        assert res["codigo_http"] == 200
        assert res["disparado"] is True
        assert res["payload"]["codigo"] == "PRD-001"
        assert res["payload"]["stock_status"] == "baixo"
        assert res["payload"]["email_destinatario"] == config.ALERT_EMAIL_TO


def test_n8n_mocked_http_error():
    """Valida tratamento defensivo quando o n8n retorna erro HTTP 500 sem interromper o agente."""
    prod = {"codigo": "PRD-001", "nome": "Mouse", "quantidade_atual": 0, "estoque_minimo": 10}

    http_error = urllib.error.HTTPError(
        url="http://mock-n8n/webhook/test",
        code=500,
        msg="Internal Server Error",
        hdrs={},  # type: ignore
        fp=io.BytesIO(b"Internal Server Error"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error), \
         patch("src.tools.n8n_client.HTTPX_AVAILABLE", False):
        res = disparar_alerta_estoque_n8n(prod, "esgotado", webhook_url="http://mock-n8n/webhook/test")

        assert res["status"] == "erro"
        assert res["codigo_http"] == 500
        assert res["disparado"] is False


def test_n8n_connection_timeout():
    """Valida que queda de conexão ou timeout não quebra a execução do agente."""
    prod = {"codigo": "PRD-001", "nome": "Mouse", "quantidade_atual": 1, "estoque_minimo": 10}

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")), \
         patch("src.tools.n8n_client.HTTPX_AVAILABLE", False):
        res = disparar_alerta_estoque_n8n(prod, "baixo", webhook_url="http://mock-n8n/webhook/test")

        assert res["status"] == "erro"
        assert res["disparado"] is False
        assert "Connection timed out" in res["erro"]


def test_analysis_node_dispatches_n8n_on_low_stock():
    """Valida que o nó de análise do LangGraph aciona o n8n automaticamente para estoque crítico."""
    state: AgentState = {
        "stock_query": "PRD-001",
        "product_data": {
            "codigo": "PRD-001",
            "nome": "Mouse sem fio",
            "quantidade_atual": 5,
            "estoque_minimo": 10,
            "unidade": "un",
            "categoria": "Periféricos",
        },
        "messages": [],
    }

    with patch("src.agent.graph.disparar_alerta_estoque_n8n") as mock_dispatch:
        mock_dispatch.return_value = {
            "status": "sucesso",
            "codigo_http": 200,
            "disparado": True,
        }

        output = analysis_node(state)

        assert output["stock_status"] == "baixo"
        assert output["alert_triggered"] is True
        assert output["n8n_dispatched"] is True
        assert mock_dispatch.called
        msg_text = output["messages"][0].content
        assert "Alerta de compra despachado automaticamente para a equipe via n8n" in msg_text


def test_analysis_node_does_not_dispatch_n8n_on_normal_stock():
    """Valida que o nó de análise NÃO aciona o n8n quando o estoque está regular."""
    state: AgentState = {
        "stock_query": "PRD-002",
        "product_data": {
            "codigo": "PRD-002",
            "nome": "Teclado Mecânico",
            "quantidade_atual": 25,
            "estoque_minimo": 10,
            "unidade": "un",
            "categoria": "Periféricos",
        },
        "messages": [],
    }

    with patch("src.agent.graph.disparar_alerta_estoque_n8n") as mock_dispatch:
        output = analysis_node(state)

        assert output["stock_status"] == "disponivel"
        assert output["alert_triggered"] is False
        assert output["n8n_dispatched"] is False
        assert not mock_dispatch.called
