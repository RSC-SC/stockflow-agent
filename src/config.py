"""Configurações da aplicação StockFlow Agent."""

import os
from pathlib import Path

# Diretório raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega o arquivo .env se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# URLs dos serviços Cloud
STOCK_API_BASE_URL = os.getenv("STOCK_API_BASE_URL", "http://150.136.45.59:8082").rstrip("/")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://150.136.45.59:5678/webhook/alerta-estoque").strip()

# Configurações de notificação de e-mail via n8n
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "rsc_sc@hotmail.com").strip()
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", "rafaeldossantoscunha@gmail.com").strip()
ALERT_SENDER_NAME = os.getenv("ALERT_SENDER_NAME", "StockFlow Bot").strip()

# Configuração da LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
