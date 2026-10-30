"""Ferramentas determinísticas usadas pelos agentes."""
from backend.tools.sintaxe import verificar_sintaxe
from backend.tools.versao import VERSAO_VALIDA, proxima_versao

__all__ = ['verificar_sintaxe', 'proxima_versao', 'VERSAO_VALIDA']
