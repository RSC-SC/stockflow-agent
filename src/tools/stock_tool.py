"""Ferramentas (Tools) Python para integração com a API de Estoque na Cloud.

Este módulo disponibiliza ferramentas tipadas para o LangGraph consultar produtos,
listar itens e verificar a saúde da API de Estoque (FastAPI) em execução na nuvem.
Contempla tratamento para produtos inexistentes (404), indisponibilidade (503),
erros de validação (422) e quedas de conexão/timeouts.
"""

import json
import re
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from src import config

# Importação condicional para ferramentas e validação
try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    def tool(fn_or_name: Any = None, **kwargs: Any) -> Any:
        """Fallback leve para o decorador @tool do LangChain."""
        if callable(fn_or_name):
            setattr(fn_or_name, "is_tool", True)
            return fn_or_name

        def decorator(fn: Any) -> Any:
            setattr(fn, "is_tool", True)
            return fn

        return decorator

# Suporte opcional ao httpx, mantendo urllib como fallback universal
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False


class StockApiClient:
    """Cliente HTTP dedicado para a API de Estoque na Cloud."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self.base_url = (base_url or config.STOCK_API_BASE_URL).rstrip("/")
        self.timeout = timeout

    def _normalize_codigo(self, codigo: str) -> str:
        """Normaliza e sanitiza o código do produto para o padrão PRD-XXX."""
        code = str(codigo).strip().upper()
        # Se o usuário informou apenas o número (ex: "1" ou "001"), formata para PRD-001
        if re.match(r"^\d{1,3}$", code):
            code = f"PRD-{int(code):03d}"
        return code

    def _request(self, endpoint: str, query_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Realiza requisição HTTP GET com tratamento robusto de exceções."""
        url = f"{self.base_url}{endpoint}"
        if query_params:
            filtered_params = {k: v for k, v in query_params.items() if v is not None}
            if filtered_params:
                url += "?" + urllib.parse.urlencode(filtered_params)

        if HTTPX_AVAILABLE:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(url)
                    data = resp.json() if resp.content else {}
                    if resp.status_code == 200:
                        return {"status": "sucesso", "codigo_http": 200, "dados": data}
                    if resp.status_code == 404:
                        return {
                            "status": "erro",
                            "codigo_http": 404,
                            "erro": data.get("erro", "produto_nao_encontrado"),
                            "mensagem": data.get("mensagem", "Produto não encontrado."),
                        }
                    if resp.status_code == 503:
                        return {
                            "status": "erro",
                            "codigo_http": 503,
                            "erro": data.get("erro", "servico_indisponivel"),
                            "mensagem": data.get("mensagem", "Serviço temporariamente indisponível. Tente novamente mais tarde."),
                        }
                    if resp.status_code == 422:
                        return {
                            "status": "erro",
                            "codigo_http": 422,
                            "erro": data.get("erro", "codigo_invalido"),
                            "mensagem": data.get("mensagem", "Código de produto ou parâmetro inválido."),
                        }
                    return {
                        "status": "erro",
                        "codigo_http": resp.status_code,
                        "erro": "erro_http",
                        "mensagem": f"A API retornou status HTTP {resp.status_code}.",
                    }
            except (httpx.ConnectError, httpx.ConnectTimeout):
                return {
                    "status": "erro",
                    "codigo_http": 0,
                    "erro": "conexao_recusada",
                    "mensagem": f"Não foi possível conectar à API de Estoque em {self.base_url}. Verifique se o servidor Cloud está online.",
                }
            except httpx.TimeoutException:
                return {
                    "status": "erro",
                    "codigo_http": 0,
                    "erro": "timeout",
                    "mensagem": f"Tempo limite de resposta excedido ({self.timeout}s) ao consultar a API de Estoque.",
                }
            except Exception as exc:
                return {
                    "status": "erro",
                    "codigo_http": 0,
                    "erro": "excecao_desconhecida",
                    "mensagem": f"Falha ao comunicar com a API: {str(exc)}",
                }

        # Fallback utilizando a biblioteca padrão urllib
        req = urllib.request.Request(url, headers={"User-Agent": "StockFlow-Agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return {
                    "status": "sucesso",
                    "codigo_http": response.status,
                    "dados": json.loads(body) if body else {},
                }
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                err_data = json.loads(err_body)
            except Exception:
                err_data = {}

            if err.code == 404:
                return {
                    "status": "erro",
                    "codigo_http": 404,
                    "erro": err_data.get("erro", "produto_nao_encontrado"),
                    "mensagem": err_data.get("mensagem", "Produto não encontrado."),
                }
            if err.code == 503:
                return {
                    "status": "erro",
                    "codigo_http": 503,
                    "erro": err_data.get("erro", "servico_indisponivel"),
                    "mensagem": err_data.get("mensagem", "Serviço temporariamente indisponível. Tente novamente mais tarde."),
                }
            if err.code == 422:
                return {
                    "status": "erro",
                    "codigo_http": 422,
                    "erro": err_data.get("erro", "codigo_invalido"),
                    "mensagem": err_data.get("mensagem", "Código de produto ou parâmetro inválido."),
                }
            return {
                "status": "erro",
                "codigo_http": err.code,
                "erro": "erro_http",
                "mensagem": err_data.get("mensagem", f"A API retornou status HTTP {err.code}."),
            }
        except (urllib.error.URLError, TimeoutError) as err:
            return {
                "status": "erro",
                "codigo_http": 0,
                "erro": "falha_conexao",
                "mensagem": f"Falha de conexão com a API de Estoque ({self.base_url}): {str(err.reason if hasattr(err, 'reason') else err)}",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "codigo_http": 0,
                "erro": "excecao_desconhecida",
                "mensagem": f"Erro inesperado: {str(exc)}",
            }

    def health(self) -> Dict[str, Any]:
        """Verifica a saúde da API."""
        return self._request("/health")

    def consultar_produto(self, codigo: str) -> Dict[str, Any]:
        """Consulta um produto específico pelo código (ex: 'PRD-001')."""
        codigo_norm = self._normalize_codigo(codigo)
        return self._request(f"/produtos/{codigo_norm}")

    def listar_produtos(self, categoria: Optional[str] = None) -> Dict[str, Any]:
        """Lista os produtos do estoque, com filtro opcional por categoria."""
        params = {"categoria": categoria} if categoria else None
        return self._request("/produtos", query_params=params)


# Instância global padrão do cliente
_default_client = StockApiClient()


# ---------------------------------------------------------------------------
# Ferramentas (@tool) para uso pelo LangGraph e LLM
# ---------------------------------------------------------------------------

@tool
def consultar_produto_tool(codigo: str) -> Dict[str, Any]:
    """Consulta informações detalhadas de um produto na API de Estoque pelo código (ex: PRD-001).
    
    Retorna nome, categoria, quantidade disponível em estoque, estoque mínimo e unidade de medida.
    Em caso de código não cadastrado ou falha de rede, retorna mensagem clara de erro.
    """
    return _default_client.consultar_produto(codigo)


@tool
def listar_produtos_tool(categoria: Optional[str] = None) -> Dict[str, Any]:
    """Lista todos os produtos cadastrados no estoque na Cloud, com filtro opcional por categoria (ex: Periféricos).
    
    Retorna o total de itens e a lista de produtos com suas respectivas quantidades e níveis mínimos.
    """
    return _default_client.listar_produtos(categoria=categoria)


@tool
def verificar_saude_api_tool() -> Dict[str, Any]:
    """Verifica se a API de Estoque na Cloud está ativa e respondendo normalmente."""
    return _default_client.health()
