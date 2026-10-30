"""Casos de uso do chat: criar projeto (com equipe projetada pela IA) e conversar com persistência.

Usado pela API e pelo terminal, para os dois se comportarem igual.
"""
import logging

from backend.agents import EQUIPE_PADRAO, IDEIAS_PADRAO
from backend.chat.orquestrador import executar
from backend.chat.projeto import Projeto

log = logging.getLogger(__name__)


def descrever_erro(erro):
    texto = str(erro)
    if '429' in texto or 'RESOURCE_EXHAUSTED' in texto:
        return 'Limite de uso do modelo atingido. Aguarde um pouco e tente de novo.'
    if '401' in texto or '403' in texto or 'API key' in texto:
        return 'Chave de API inválida ou sem permissão. Confira o arquivo .env.'
    if 'Connect' in type(erro).__name__ or 'Connection' in texto:
        return 'Não foi possível falar com o modelo. Se usa Ollama local, confira se ele está aberto.'
    return 'Erro inesperado ao consultar o modelo. Veja o log do servidor.'


def resumo_equipe(definicoes):
    return [{'nome': d['nome'], 'etapa': d['etapa'], 'responsabilidade': d['responsabilidade']}
            for d in definicoes]


def criar_projeto(repo, titulo, descricao, arquitetar):
    """Projeta a equipe com a IA (ou usa a padrão se falhar), salva e registra o evento de equipe."""
    aviso = None
    try:
        definicoes, ideias = arquitetar(titulo, descricao)
        origem = 'ia'
    except Exception as erro:
        log.exception('Falha ao projetar a equipe; usando a equipe padrão')
        definicoes, ideias, origem = EQUIPE_PADRAO, IDEIAS_PADRAO, 'padrao'
        aviso = descrever_erro(erro)

    projeto = Projeto(titulo=titulo, descricao=descricao)
    evento = {'tipo': 'equipe', 'origem': origem, 'aviso': aviso,
              'agentes': resumo_equipe(definicoes), 'ideias': list(ideias)}
    repo.criar_projeto(projeto, definicoes)
    repo.adicionar_mensagem(projeto.id, evento)
    return projeto, evento


def conversar(repo, projeto, equipe, mensagem):
    """Executa o pedido, salvando a mensagem, cada evento e o estado final do projeto."""
    repo.adicionar_mensagem(projeto.id, {'tipo': 'usuario', 'conteudo': mensagem})
    try:
        for evento in executar(mensagem, projeto, equipe):
            repo.adicionar_mensagem(projeto.id, evento)
            yield evento
    except Exception as erro:
        log.exception('Falha ao processar o pedido')
        evento = {'tipo': 'erro', 'mensagem': descrever_erro(erro)}
        repo.adicionar_mensagem(projeto.id, evento)
        yield evento
    finally:
        repo.salvar_projeto(projeto)
