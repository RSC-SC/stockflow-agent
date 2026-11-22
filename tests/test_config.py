"""Testes de configuração e variáveis de ambiente."""

import os
from src import config


def test_default_config():
    """Valida se a URL base da API de estoque padrão aponta para o host Cloud."""
    assert config.STOCK_API_BASE_URL.startswith("http://")
    assert "150.136.45.59" in config.STOCK_API_BASE_URL
    assert config.STOCK_API_BASE_URL.endswith("8082")


def test_llm_defaults():
    """Valida valores padrão da LLM."""
    assert config.LLM_PROVIDER in ["gemini", "openai"]
    assert config.LLM_MODEL != ""
