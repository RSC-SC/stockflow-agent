"""Cliente de Integração HTTP com o Webhook do n8n na Cloud.

Este módulo implementa o cliente responsável por despachar notificações de estoque crítico
(produtos esgotados ou abaixo do estoque mínimo de segurança) diretamente para o webhook do n8n,
acionando o fluxo automatizado de e-mails para o time de compras e governança.
Contempla timeout curto e tratamento defensivo (try/except) para assegurar que falhas ou lentidão
no n8n não travem ou derrubem a execução do agente de IA.
"""

import json
import logging
from typing import Any, Dict, Optional
import urllib.error
import urllib.request

from src import config

logger = logging.getLogger(__name__)

# Suporte opcional ao httpx, com fallback transparente para urllib
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False


def disparar_alerta_estoque_n8n(
    product: Dict[str, Any],
    stock_status: str,
    webhook_url: Optional[str] = None,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """Dispara uma notificação HTTP POST para o webhook do n8n informando estoque crítico.

    Args:
        product: Dicionário contendo dados do produto (codigo, nome, quantidade_atual, estoque_minimo).
        stock_status: Classificação da situação ('baixo' ou 'esgotado').
        webhook_url: URL do webhook (opcional; utiliza config.N8N_WEBHOOK_URL por padrão).
        timeout: Tempo limite da requisição em segundos (padrão: 5.0s para não prender o agente).

    Returns:
        Dict[str, Any]: Dicionário com status ('sucesso', 'erro' ou 'ignorado'), payload e detalhes.
    """
    target_url = (config.N8N_WEBHOOK_URL if webhook_url is None else webhook_url).strip()

    if not target_url:
        logger.warning("Disparo n8n ignorado: N8N_WEBHOOK_URL não configurada.")
        return {
            "status": "ignorado",
            "mensagem": "N8N_WEBHOOK_URL não configurada.",
            "disparado": False,
        }

    payload = {
        "codigo": product.get("codigo", ""),
        "nome": product.get("nome", ""),
        "quantidade_atual": int(product.get("quantidade_atual", 0)),
        "estoque_minimo": int(product.get("estoque_minimo", 0)),
        "stock_status": stock_status,
        "email_destinatario": config.ALERT_EMAIL_TO,
        "email_remetente": config.ALERT_EMAIL_FROM,
        "nome_remetente": config.ALERT_SENDER_NAME,
    }

    try:
        if HTTPX_AVAILABLE:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    target_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                status_code = resp.status_code
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

                if 200 <= status_code < 300:
                    logger.info("Alerta despachado com sucesso ao n8n: HTTP %d", status_code)
                    return {
                        "status": "sucesso",
                        "codigo_http": status_code,
                        "resposta": data,
                        "payload": payload,
                        "disparado": True,
                    }
                else:
                    logger.warning("n8n retornou status HTTP %d: %s", status_code, data)
                    return {
                        "status": "erro",
                        "codigo_http": status_code,
                        "erro": f"Status HTTP {status_code}",
                        "resposta": data,
                        "payload": payload,
                        "disparado": False,
                    }

        # Fallback universal com urllib
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = response.getcode()
            body_text = response.read().decode("utf-8")
            try:
                data = json.loads(body_text)
            except Exception:
                data = body_text

            return {
                "status": "sucesso",
                "codigo_http": status_code,
                "resposta": data,
                "payload": payload,
                "disparado": True,
            }

    except urllib.error.HTTPError as exc:
        logger.error("Erro HTTP ao despachar alerta n8n: %s", exc)
        return {
            "status": "erro",
            "codigo_http": exc.code,
            "erro": str(exc),
            "payload": payload,
            "disparado": False,
        }
    except Exception as exc:
        logger.error("Exceção ao comunicar com n8n: %s", exc)
        return {
            "status": "erro",
            "erro": str(exc),
            "payload": payload,
            "disparado": False,
        }
