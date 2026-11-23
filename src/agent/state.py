"""Modelagem do Estado Compartilhado (AgentState) para o LangGraph.

Este módulo define a estrutura de dados compartilhada entre os nós do grafo,
garantindo rastreamento do histórico de conversação com reducer `add_messages`,
armazenamento de dados de estoque consultados na API e flags de decisão.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Sequence, TypedDict

# Importação com suporte a fallback caso dependências ainda não estejam instaladas
try:
    from langchain_core.messages import AnyMessage, BaseMessage
    from langgraph.graph.message import add_messages
except ImportError:  # pragma: no cover
    def add_messages(left: list, right: Any) -> list:
        """Reducer padrão simples para concatenar histórico de mensagens."""
        res = list(left)
        if isinstance(right, list):
            res.extend(right)
        else:
            res.append(right)
        return res

    AnyMessage = Any  # type: ignore
    BaseMessage = Any  # type: ignore


# Tipos de classificação de estoque
StockStatus = Literal[
    "disponivel",
    "baixo",
    "esgotado",
    "nao_encontrado",
    "erro_api",
    "nao_aplicavel",
]


class AgentState(TypedDict, total=False):
    """Estado compartilhado da aplicação no fluxo do LangGraph.
    
    Attributes:
        messages: Lista acumulativa de mensagens da conversa, atualizada
            pelo reducer `add_messages` do LangGraph.
        stock_query: Código ou termo de busca do produto extraído da
            solicitação (ex: 'PRD-001', 'mouse').
        product_data: Dicionário contendo os dados estruturados retornados
            pela API de estoque (codigo, nome, quantidade_atual, estoque_minimo, etc.).
        stock_status: Classificação da situação do estoque calculada pelo
            agente ('disponivel', 'baixo', 'esgotado', 'nao_encontrado', 'erro_api').
        alert_triggered: Indica se um alerta crítico foi gerado para envio
            ao webhook do n8n na Cloud.
        action_taken: Rastreia a decisão tomada pelo grafo (ex: 'tool_call',
            'direct_answer', 'api_query').
    """

    messages: Annotated[List[AnyMessage], add_messages]
    stock_query: Optional[str]
    product_data: Optional[Dict[str, Any]]
    stock_status: Optional[StockStatus]
    alert_triggered: bool
    action_taken: Optional[str]
