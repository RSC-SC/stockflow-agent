"""Testes unitários e de integração para a Stock Tool e o StockApiClient."""

from src.tools.stock_tool import (
    StockApiClient,
    consultar_produto_tool,
    listar_produtos_tool,
    verificar_saude_api_tool,
)


def test_normalize_codigo():
    """Valida normalização de códigos numéricos e com espaços."""
    client = StockApiClient()
    assert client._normalize_codigo("prd-001") == "PRD-001"
    assert client._normalize_codigo(" 1 ") == "PRD-001"
    assert client._normalize_codigo("12") == "PRD-012"
    assert client._normalize_codigo("PRD-020") == "PRD-020"


def test_api_offline_fallback():
    """Valida tratamento de erro gracioso quando a API está apontando para porta inexistente."""
    offline_client = StockApiClient(base_url="http://127.0.0.1:9999", timeout=1.0)
    res = offline_client.health()
    assert res["status"] == "erro"
    assert res["codigo_http"] == 0
    assert "erro" in res
    assert "mensagem" in res


def test_live_health_cloud_api():
    """Valida consulta de health check contra a API na Cloud."""
    client = StockApiClient()
    res = client.health()
    assert res["status"] == "sucesso"
    assert res["codigo_http"] == 200
    assert res["dados"]["status"] == "ok"
    assert res["dados"]["service"] == "api-estoque"


def test_live_consultar_produto_existente():
    """Valida consulta de produto existente (PRD-001) contra a API na Cloud."""
    res = consultar_produto_tool("PRD-001")
    assert res["status"] == "sucesso"
    assert res["codigo_http"] == 200
    dados = res["dados"]
    assert dados["codigo"] == "PRD-001"
    assert dados["nome"] == "Mouse sem fio"
    assert dados["quantidade_atual"] >= 0
    assert dados["estoque_minimo"] > 0


def test_live_consultar_produto_inexistente_404():
    """Valida tratamento gracioso de 404 (PRD-999) sem lançar exceção não tratada."""
    res = consultar_produto_tool("PRD-999")
    assert res["status"] == "erro"
    assert res["codigo_http"] == 404
    assert res["erro"] == "produto_nao_encontrado"
    assert "mensagem" in res


def test_live_consultar_servico_indisponivel_503():
    """Valida simulação determinística de 503 (PRD-503) retornada pela API."""
    res = consultar_produto_tool("PRD-503")
    assert res["status"] == "erro"
    assert res["codigo_http"] == 503
    assert res["erro"] == "servico_indisponivel"


def test_live_listar_produtos_com_filtro():
    """Valida listagem de produtos com e sem filtro de categoria."""
    # Listagem geral
    res_todos = listar_produtos_tool()
    assert res_todos["status"] == "sucesso"
    assert res_todos["dados"]["total"] >= 12

    # Listagem filtrada
    res_perifericos = listar_produtos_tool(categoria="Periféricos")
    assert res_perifericos["status"] == "sucesso"
    for prod in res_perifericos["dados"]["produtos"]:
        assert prod["categoria"] == "Periféricos"
