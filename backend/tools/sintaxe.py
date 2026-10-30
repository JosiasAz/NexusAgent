import ast

from langchain_core.tools import tool


@tool
def verificar_sintaxe(codigo: str) -> str:
    """Confere se o código Python é sintaticamente válido, sem executá-lo."""
    if not codigo.strip():
        return 'ERRO_SINTAXE: código vazio'
    try:
        ast.parse(codigo)
        return 'SINTAXE_OK'
    except SyntaxError as e:
        return f'ERRO_SINTAXE linha {e.lineno}: {e.msg}'
