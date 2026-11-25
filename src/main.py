"""Ponto de entrada interativo (CLI) do StockFlow Agent.

Permite interagir com o agente LangGraph através de um console interativo (REPL)
ou executar perguntas diretamente via linha de comando com a flag --pergunta.
"""

import argparse
import sys
from typing import Any, Dict, Optional

from src import config
from src.agent.graph import create_stock_graph
from src.agent.state import AgentState
from src.tools.stock_tool import verificar_saude_api_tool, listar_produtos_tool

BANNER = f"""
======================================================================
  📦 StockFlow Agent — Especialista em Gestão de Estoque (LangGraph)
----------------------------------------------------------------------
  • API de Estoque Cloud: {config.STOCK_API_BASE_URL}
  • Provedor LLM: {config.LLM_PROVIDER} ({config.LLM_MODEL})
  • Digite 'ajuda' para ver comandos ou 'sair' para encerrar.
======================================================================
"""

AJUDA_TEXT = """
💡 Exemplos de perguntas que você pode fazer:
  1. Consulta de produto: "Qual o estoque do Mouse sem fio PRD-001?"
  2. Diagnóstico de risco: "Temos cabos HDMI em estoque?"
  3. Dúvida conceitual:   "O que é estoque de segurança e para que serve?"
  4. Teste de produto 404: "Consulte o produto PRD-999"

Comandos especiais disponíveis:
  • catalogo    -> Lista rapidamente os produtos cadastrados
  • status-api  -> Verifica a saúde da API na Cloud
  • limpar      -> Reinicia o histórico da conversa
  • ajuda       -> Mostra esta mensagem de ajuda
  • sair        -> Encerra a aplicação
"""


def format_agent_response(result: Dict[str, Any]) -> str:
    """Extrai e formata o conteúdo da resposta final do agente."""
    messages = result.get("messages", [])
    if not messages:
        return "Nenhuma resposta gerada pelo agente."

    last_message = messages[-1]
    content = getattr(last_message, "content", "") if hasattr(last_message, "content") else ""
    if not content and isinstance(last_message, dict):
        content = last_message.get("content", "")

    return str(content).strip() or "Processamento concluído sem mensagem textual."


def process_user_query(
    query: str,
    state: Optional[AgentState] = None,
    graph: Optional[Any] = None,
) -> tuple[str, AgentState]:
    """Processa uma consulta do usuário no grafo LangGraph e retorna a resposta e o novo estado.
    
    Args:
        query: Pergunta enviada pelo usuário.
        state: Estado acumulado das mensagens anteriores.
        graph: Instância compilada do StateGraph.
        
    Returns:
        tuple[str, AgentState]: (resposta_formatada, novo_estado)
    """
    active_graph = graph or create_stock_graph()
    current_state: AgentState = state or {"messages": []}

    # Adiciona a mensagem do usuário ao histórico
    msgs = list(current_state.get("messages", []))
    msgs.append({"role": "user", "content": query})
    current_state["messages"] = msgs

    # Executa o ciclo do grafo
    new_state = active_graph.invoke(current_state)
    resposta = format_agent_response(new_state)

    return resposta, new_state


def run_interactive_cli() -> None:
    """Inicia o loop interativo (REPL) no terminal."""
    print(BANNER)
    graph = create_stock_graph()
    state: AgentState = {"messages": []}

    while True:
        try:
            user_input = input("\n👤 Você > ").strip()
            if not user_input:
                continue

            comando = user_input.lower()

            if comando in ["sair", "exit", "quit", "q"]:
                print("\n👋 Encerrando o StockFlow Agent. Até logo!")
                break

            if comando in ["limpar", "clear", "reset"]:
                state = {"messages": []}
                print("\n🔄 Histórico de conversa reiniciado com sucesso!")
                continue

            if comando in ["ajuda", "help", "?"]:
                print(AJUDA_TEXT)
                continue

            if comando in ["status-api", "saude", "health"]:
                print("\n⏳ Verificando status da API na Cloud...")
                res = verificar_saude_api_tool()
                if res.get("status") == "sucesso":
                    dados = res.get("dados", {})
                    print(f"✅ API Online! Serviço: {dados.get('service')} | Versão: {dados.get('version')}")
                else:
                    print(f"❌ Falha ao conectar: {res.get('mensagem')}")
                continue

            if comando in ["catalogo", "produtos", "listar"]:
                print("\n⏳ Consultando catálogo na Cloud...")
                res = listar_produtos_tool()
                if res.get("status") == "sucesso":
                    prods = res.get("dados", {}).get("produtos", [])
                    print(f"\n📋 Catálogo ({len(prods)} produtos cadastrados):")
                    for p in prods:
                        print(f"  • [{p.get('codigo')}] {p.get('nome')}: {p.get('quantidade_atual')} {p.get('unidade')} (Mín: {p.get('estoque_minimo')})")
                else:
                    print(f"❌ Erro ao listar: {res.get('mensagem')}")
                continue

            # Processamento normal pelo LangGraph
            print("\n🤖 StockFlow Agent pensando...")
            resposta, state = process_user_query(user_input, state=state, graph=graph)
            print(f"\n{resposta}")

        except KeyboardInterrupt:
            print("\n\n👋 Operação interrompida pelo usuário (Ctrl+C). Até logo!")
            break
        except EOFError:
            print("\n👋 Fim da entrada. Até logo!")
            break


def main() -> None:
    """Ponto de entrada principal com suporte a flags de linha de comando."""
    parser = argparse.ArgumentParser(
        description="StockFlow Agent — Assistente Inteligente de Estoque (LangGraph)",
    )
    parser.add_argument(
        "--pergunta", "-p",
        type=str,
        help="Executa uma pergunta única no agente e encerra (modo single-shot).",
    )
    args = parser.parse_args()

    if args.pergunta:
        graph = create_stock_graph()
        resposta, _ = process_user_query(args.pergunta, graph=graph)
        print(f"\n{resposta}\n")
    else:
        run_interactive_cli()


if __name__ == "__main__":
    main()
