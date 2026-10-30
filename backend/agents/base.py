"""Utilidades compartilhadas pelos agentes."""
import json
import re

from langchain_core.messages import AIMessage, ToolMessage

RECURSION_LIMIT = 8
LIMITE_RASTRO = 30000  # caracteres guardados de cada entrada/saída no rastro


def invocar(agente, texto):
    """Envia uma mensagem ao agente e devolve (texto final, todas as mensagens)."""
    resposta = agente.invoke({'messages': [{'role': 'user', 'content': texto}]},
                             config={'recursion_limit': RECURSION_LIMIT})
    return resposta['messages'][-1].text, resposta['messages']


def extrair_codigo(texto):
    """Primeiro bloco ```python do texto (mesmo sem fechamento, se a resposta foi cortada)."""
    bloco = re.search(r'```(?:python|py)?[ \t]*\n(.*?)(?:```|\Z)', texto, re.S)
    return (bloco.group(1) if bloco else texto).strip()


def resultados_ferramenta(mensagens, nome):
    """Conteúdos devolvidos pela ferramenta `nome`, na ordem em que foram chamados."""
    return [m.content for m in mensagens
            if isinstance(m, ToolMessage) and m.name == nome and m.status == 'success']


def cortar(texto, limite=LIMITE_RASTRO):
    texto = str(texto)
    return texto if len(texto) <= limite else texto[:limite] + '\n… (cortado)'


def rastrear(mensagens):
    """Ferramentas chamadas (argumentos → resultado) e tokens gastos, para o painel de fluxo."""
    resultados = {m.tool_call_id: m for m in mensagens if isinstance(m, ToolMessage)}
    ferramentas, entrada, saida = [], 0, 0
    for mensagem in mensagens:
        if not isinstance(mensagem, AIMessage):
            continue
        uso = mensagem.usage_metadata or {}
        entrada, saida = entrada + uso.get('input_tokens', 0), saida + uso.get('output_tokens', 0)
        for chamada in mensagem.tool_calls:
            resposta = resultados.get(chamada['id'])
            ferramentas.append({
                'nome': chamada['name'],
                'argumentos': cortar(json.dumps(chamada['args'], ensure_ascii=False), 4000),
                'resultado': cortar(resposta.content, 4000) if resposta else None,
                'status': resposta.status if resposta else 'sem resposta'})
    return {'ferramentas': ferramentas, 'tokens': {'entrada': entrada, 'saida': saida}}
