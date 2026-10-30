"""Chat: projetos, persistência, orquestração da equipe e casos de uso."""
from backend.chat.orquestrador import executar
from backend.chat.projeto import Projeto
from backend.chat.repositorio import Repositorio
from backend.chat.servico import conversar, criar_projeto, descrever_erro

__all__ = ['executar', 'Projeto', 'Repositorio', 'conversar', 'criar_projeto', 'descrever_erro']
