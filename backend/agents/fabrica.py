"""Fábrica: transforma as definições da equipe em agentes LangChain.

A personalidade vem da IA (responsabilidade e instruções); as regras de cada etapa
são fixas aqui, para o fluxo não depender do que o arquiteto escreveu.
"""
from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent

from backend.tools import proxima_versao, verificar_sintaxe

MARCADOR_CONVERSA = 'CONVERSA:'

ROTULOS = {'planejamento': 'planejamento', 'desenvolvimento': 'desenvolvimento',
           'revisao': 'revisão', 'versionamento': 'versionamento'}

PROTOCOLOS = {
    'planejamento': (
        'Se a mensagem não pedir para criar ou alterar código (saudação, conversa, dúvida geral), '
        f'comece com {MARCADOR_CONVERSA} e responda em uma ou duas linhas sobre o projeto e o que a equipe pode fazer. '
        'Caso contrário, quebre o pedido em no máximo cinco passos curtos, considerando o código atual '
        'do projeto se houver. Não escreva código.'),
    'desenvolvimento': (
        'Você recebe o pedido, o plano, o código atual do projeto e eventuais revisões. '
        'Devolva o código Python COMPLETO do projeto já com a sua contribuição, preservando o que já funciona, '
        'com docstrings, em um único bloco ```python. Não escreva nada fora do bloco.'),
    'revisao': (
        'Chame verificar_sintaxe com o código recebido. Avalie o código segundo a sua responsabilidade. '
        'Comece a resposta com APROVADO ou REPROVADO e explique em até duas linhas.'),
    'versionamento': (
        'Funcionalidade nova compatível é minor; correção é patch; quebra de compatibilidade é major. '
        'Chame proxima_versao com a versão atual e escreva uma mensagem de commit no padrão '
        'Conventional Commits, em até três linhas.'),
}

FERRAMENTAS = {'revisao': [verificar_sintaxe], 'versionamento': [proxima_versao]}


@dataclass
class Membro:
    nome: str
    etapa: str
    responsabilidade: str
    agente: Any

    @property
    def papel(self):
        return ROTULOS[self.etapa]


@dataclass
class EquipeMontada:
    planejador: Membro
    desenvolvedores: list
    revisores: list
    versionador: Membro


def montar_prompt(definicao, titulo, descricao):
    return (f'Você é {definicao["nome"]}, da equipe do projeto "{titulo}".\n'
            f'Sobre o projeto: {descricao}\n'
            f'Sua responsabilidade: {definicao["responsabilidade"]}\n'
            f'{definicao["instrucoes"]}\n\n'
            f'Regras obrigatórias da sua etapa:\n{PROTOCOLOS[definicao["etapa"]]}\n'
            'Responda sempre em português.')


def montar_equipe(definicoes, titulo, descricao, modelo, criar=create_agent):
    """Cria um agente por definição e agrupa por etapa (as definições já vêm normalizadas)."""
    membros = [Membro(d['nome'], d['etapa'], d['responsabilidade'],
                      criar(modelo, tools=FERRAMENTAS.get(d['etapa'], []),
                            system_prompt=montar_prompt(d, titulo, descricao)))
               for d in definicoes]
    da_etapa = lambda etapa: [m for m in membros if m.etapa == etapa]
    return EquipeMontada(planejador=da_etapa('planejamento')[0], desenvolvedores=da_etapa('desenvolvimento'),
                         revisores=da_etapa('revisao'), versionador=da_etapa('versionamento')[0])
