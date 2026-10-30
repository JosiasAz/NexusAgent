"""API HTTP: projetos com equipes projetadas pela IA, histórico persistente e chat em streaming (NDJSON)."""
import json
import logging
import threading
from collections import OrderedDict
from dataclasses import asdict
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Path, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.agents import montar_equipe, projetar_equipe
from backend.chat import Repositorio, conversar, criar_projeto, descrever_erro
from backend.config import (DB_PATH, MAX_DESCRICAO, MAX_EQUIPES_EM_MEMORIA, MAX_MENSAGEM, MAX_TITULO,
                            MAX_TOKENS_ARQUITETO, criar_modelo, descrever_modelo)

log = logging.getLogger(__name__)

app = FastAPI(title='Equipe de Software Multiagente', version='2.0.0')
ID_PROJETO = Path(pattern=r'^[0-9a-f]{32}$')


# --- Dependências (substituídas nos testes) -----------------------------------
@lru_cache
def obter_repositorio():
    return Repositorio(DB_PATH)


@lru_cache
def modelo_chat():
    return criar_modelo()


@lru_cache
def modelo_arquiteto():
    return criar_modelo(max_tokens=MAX_TOKENS_ARQUITETO)


def obter_arquiteto():
    return lambda titulo, descricao: projetar_equipe(titulo, descricao, modelo_arquiteto())


def obter_montador():
    return lambda definicoes, projeto: montar_equipe(definicoes, projeto.titulo, projeto.descricao, modelo_chat())


# --- Estado em memória: uma trava por projeto e equipes já montadas ----------
_travas, _equipes, _guarda = {}, OrderedDict(), threading.Lock()


def trava_do_projeto(projeto_id):
    with _guarda:
        return _travas.setdefault(projeto_id, threading.Lock())


def equipe_do_projeto(projeto, repo, montar):
    with _guarda:
        if projeto.id in _equipes:
            _equipes.move_to_end(projeto.id)
            return _equipes[projeto.id]
    equipe = montar(repo.agentes(projeto.id), projeto)
    with _guarda:
        _equipes[projeto.id] = equipe
        while len(_equipes) > MAX_EQUIPES_EM_MEMORIA:
            _equipes.popitem(last=False)
    return equipe


# --- Esquemas ----------------------------------------------------------------
class NovoProjeto(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    titulo: str = Field(min_length=1, max_length=MAX_TITULO)
    descricao: str = Field(min_length=1, max_length=MAX_DESCRICAO)


class PedidoChat(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    mensagem: str = Field(min_length=1, max_length=MAX_MENSAGEM)


def linha(evento):
    return json.dumps(evento, ensure_ascii=False) + '\n'


def detalhes(projeto, repo):
    dados = asdict(projeto)
    dados.pop('historico')
    return {'projeto': dados, 'agentes': repo.agentes(projeto.id), 'mensagens': repo.mensagens(projeto.id)}


def projeto_ou_404(repo, projeto_id):
    projeto = repo.obter_projeto(projeto_id)
    if not projeto:
        raise HTTPException(404, 'Projeto não encontrado.')
    return projeto


# --- Rotas -------------------------------------------------------------------
@app.get('/api/saude')
def saude():
    return {'status': 'ok', 'modelo': descrever_modelo()}


@app.get('/api/projetos')
def listar_projetos(repo=Depends(obter_repositorio)):
    return repo.listar_projetos()


@app.post('/api/projetos', status_code=201)
def novo_projeto(dados: NovoProjeto, repo=Depends(obter_repositorio), arquitetar=Depends(obter_arquiteto)):
    projeto, _ = criar_projeto(repo, dados.titulo, dados.descricao, arquitetar)
    return detalhes(projeto, repo)


@app.get('/api/projetos/{projeto_id}')
def ver_projeto(projeto_id: str = ID_PROJETO, repo=Depends(obter_repositorio)):
    return detalhes(projeto_ou_404(repo, projeto_id), repo)


@app.delete('/api/projetos/{projeto_id}', status_code=204)
def excluir_projeto(projeto_id: str = ID_PROJETO, repo=Depends(obter_repositorio)):
    trava = trava_do_projeto(projeto_id)
    if not trava.acquire(blocking=False):
        raise HTTPException(409, 'O projeto está processando um pedido. Tente quando terminar.')
    try:
        if not repo.excluir_projeto(projeto_id):
            raise HTTPException(404, 'Projeto não encontrado.')
        with _guarda:
            _equipes.pop(projeto_id, None)
            _travas.pop(projeto_id, None)
    finally:
        trava.release()
    return Response(status_code=204)


@app.post('/api/projetos/{projeto_id}/chat')
def chat(pedido: PedidoChat, projeto_id: str = ID_PROJETO, repo=Depends(obter_repositorio),
         montar=Depends(obter_montador)):
    projeto = projeto_ou_404(repo, projeto_id)
    trava = trava_do_projeto(projeto_id)
    if not trava.acquire(blocking=False):
        raise HTTPException(409, 'Este projeto ainda está processando o pedido anterior.')
    try:
        equipe = equipe_do_projeto(projeto, repo, montar)
    except Exception as erro:
        trava.release()
        log.exception('Falha ao montar a equipe')
        raise HTTPException(503, descrever_erro(erro))

    def eventos():
        try:
            for evento in conversar(repo, projeto, equipe, pedido.mensagem):
                yield linha(evento)
        finally:
            trava.release()

    return StreamingResponse(eventos(), media_type='application/x-ndjson')
