import re

from langchain_core.tools import tool

VERSAO_VALIDA = re.compile(r'^\d+\.\d+\.\d+$')


@tool
def proxima_versao(atual: str, tipo: str) -> str:
    """Calcula a próxima versão semântica. tipo deve ser major, minor ou patch."""
    # Devolve o erro como texto para o agente poder corrigir a chamada.
    if not VERSAO_VALIDA.match(atual.strip()):
        return f'ERRO: versão "{atual}" não está no formato X.Y.Z'
    tipo = tipo.strip().lower()
    ma, mi, pa = map(int, atual.strip().split('.'))
    proximas = {'major': f'{ma + 1}.0.0', 'minor': f'{ma}.{mi + 1}.0', 'patch': f'{ma}.{mi}.{pa + 1}'}
    if tipo not in proximas:
        return f'ERRO: tipo "{tipo}" inválido; use major, minor ou patch'
    return proximas[tipo]
