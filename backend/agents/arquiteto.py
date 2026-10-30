"""Arquiteto: a IA projeta a equipe de agentes a partir do título e da descrição do projeto.

O modelo escolhe nomes, responsabilidades e instruções; a estrutura (quantos agentes
por etapa) é garantida por `normalizar`, e a equipe padrão cobre qualquer falha.
"""
from typing import Literal

from pydantic import BaseModel, Field

ETAPAS = ('planejamento', 'desenvolvimento', 'revisao', 'versionamento')
LIMITES = {'planejamento': (1, 1), 'desenvolvimento': (1, 3), 'revisao': (1, 2), 'versionamento': (1, 1)}


class AgenteProjetado(BaseModel):
    nome: str = Field(description='Primeiro nome de pessoa, curto e diferente dos outros agentes')
    etapa: Literal['planejamento', 'desenvolvimento', 'revisao', 'versionamento']
    responsabilidade: str = Field(description='Uma frase curta dizendo do que o agente cuida neste projeto')
    instrucoes: str = Field(description='Duas ou três frases de como trabalhar, específicas deste projeto')


class EquipeProjetada(BaseModel):
    agentes: list[AgenteProjetado]
    ideias: list[str] = Field(description='De 3 a 5 primeiros pedidos concretos e pequenos para o chat')


EQUIPE_PADRAO = [
    {'nome': 'Paulo', 'etapa': 'planejamento', 'responsabilidade': 'Organiza os pedidos em passos curtos.',
     'instrucoes': 'Pense no menor passo que entrega valor e deixe claro o que cada passo produz.'},
    {'nome': 'Dora', 'etapa': 'desenvolvimento', 'responsabilidade': 'Escreve o código Python do projeto.',
     'instrucoes': 'Prefira funções pequenas, nomes claros e validação das entradas.'},
    {'nome': 'Rui', 'etapa': 'revisao', 'responsabilidade': 'Revisa correção, clareza e erros de lógica.',
     'instrucoes': 'Reprove só por problemas reais e diga exatamente o que corrigir.'},
    {'nome': 'Vera', 'etapa': 'versionamento', 'responsabilidade': 'Cuida da versão semântica e dos commits.',
     'instrucoes': 'Escolha major, minor ou patch pelo impacto da mudança.'},
]
IDEIAS_PADRAO = ['Função que diz se um número é primo', 'Classe Pedido com itens e cálculo do total',
                 'Validador de CPF']


def montar_pedido(titulo, descricao):
    return (
        'Você é um arquiteto de equipes de agentes de IA que escrevem código Python.\n'
        f'Projeto: {titulo}\nDescrição: {descricao}\n\n'
        'Monte uma equipe de 4 a 7 agentes para este projeto:\n'
        '- exatamente 1 de planejamento (coordena e quebra pedidos em passos);\n'
        '- de 1 a 3 de desenvolvimento, cada um com uma especialidade diferente e útil para o projeto '
        '(por exemplo: regras de negócio, dados, testes, interface de linha de comando);\n'
        '- de 1 a 2 de revisão, com focos diferentes (por exemplo: qualidade, segurança, desempenho);\n'
        '- exatamente 1 de versionamento.\n'
        'Use primeiros nomes de pessoas brasileiras, todos diferentes. '
        'Escreva responsabilidades e instruções específicas deste projeto, em português com acentuação correta. '
        'Sugira também de 3 a 5 ideias de primeiros pedidos concretos para o chat da equipe.')


def limpar(texto, limite):
    return ' '.join(str(texto).split())[:limite]


def normalizar(equipe: EquipeProjetada):
    """Garante a estrutura da equipe; etapas sem agente válido recebem o agente padrão."""
    por_etapa = {etapa: [] for etapa in ETAPAS}
    for agente in equipe.agentes:
        definicao = {'nome': limpar(agente.nome, 40), 'etapa': agente.etapa,
                     'responsabilidade': limpar(agente.responsabilidade, 240),
                     'instrucoes': limpar(agente.instrucoes, 700)}
        if definicao['nome'] and definicao['responsabilidade']:
            por_etapa[agente.etapa].append(definicao)

    padrao = {d['etapa']: d for d in EQUIPE_PADRAO}
    definicoes, usados = [], set()
    for etapa in ETAPAS:
        minimo, maximo = LIMITES[etapa]
        escolhidos = por_etapa[etapa][:maximo]
        if len(escolhidos) < minimo:
            escolhidos = [dict(padrao[etapa])]
        for definicao in escolhidos:
            nome, n = definicao['nome'], 2
            while nome.lower() in usados:
                nome, n = f"{definicao['nome']} {n}", n + 1
            usados.add(nome.lower())
            definicoes.append({**definicao, 'nome': nome})

    ideias = [limpar(i, 160) for i in equipe.ideias if str(i).strip()][:5] or list(IDEIAS_PADRAO)
    return definicoes, ideias


def projetar_equipe(titulo, descricao, modelo):
    """Pede ao modelo uma equipe estruturada e devolve (definições, ideias)."""
    equipe = modelo.with_structured_output(EquipeProjetada).invoke(montar_pedido(titulo, descricao))
    if equipe is None:
        raise ValueError('O modelo não devolveu uma equipe.')
    return normalizar(equipe)
