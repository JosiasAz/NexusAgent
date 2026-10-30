"""Páginas e proxy para o backend FastAPI.

O navegador só fala com o Django; as chamadas /api/* são repassadas ao backend,
e a resposta do chat (NDJSON) é transmitida em tempo real.
"""
import json
import logging

import httpx
from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST, require_safe

log = logging.getLogger(__name__)
INDISPONIVEL = 'Backend indisponível. Confira se ele está rodando (python -m backend).'

# Leitura longa: montar a equipe e responder um pedido podem levar minutos.
cliente = httpx.Client(base_url=settings.BACKEND_URL, timeout=httpx.Timeout(10, read=300))


def corpo_json(request):
    """Objeto JSON do corpo da requisição, ou None se for inválido."""
    try:
        corpo = json.loads(request.body)
    except ValueError:
        return None
    return corpo if isinstance(corpo, dict) else None


def encaminhar(metodo, caminho, corpo=None):
    """Repassa uma chamada simples (sem streaming) ao backend."""
    try:
        resposta = cliente.request(metodo, caminho, json=corpo)
    except httpx.HTTPError:
        log.exception('Falha ao conectar no backend')
        return JsonResponse({'detail': INDISPONIVEL}, status=502)
    if resposta.status_code == 204:
        return HttpResponse(status=204)
    return HttpResponse(resposta.content, status=resposta.status_code,
                        content_type=resposta.headers.get('content-type', 'application/json'))


def json_invalido():
    return JsonResponse({'detail': 'JSON inválido.'}, status=400)


@require_safe
@ensure_csrf_cookie
def index(request):
    return render(request, 'chat/index.html')


@require_GET
def saude(request):
    return encaminhar('GET', '/api/saude')


@require_http_methods(['GET', 'POST'])
def projetos(request):
    if request.method == 'GET':
        return encaminhar('GET', '/api/projetos')
    corpo = corpo_json(request)
    return encaminhar('POST', '/api/projetos', corpo) if corpo is not None else json_invalido()


@require_http_methods(['GET', 'DELETE'])
def projeto(request, projeto_id):
    return encaminhar(request.method, f'/api/projetos/{projeto_id}')


@require_POST
def chat(request, projeto_id):
    corpo = corpo_json(request)
    if corpo is None:
        return json_invalido()
    try:
        pedido = cliente.build_request('POST', f'/api/projetos/{projeto_id}/chat', json=corpo)
        resposta = cliente.send(pedido, stream=True)
    except httpx.HTTPError:
        log.exception('Falha ao conectar no backend')
        return JsonResponse({'detail': INDISPONIVEL}, status=502)

    if resposta.status_code != 200:
        conteudo = resposta.read()
        resposta.close()
        return HttpResponse(conteudo, status=resposta.status_code,
                            content_type=resposta.headers.get('content-type', 'application/json'))

    def fluxo():
        try:
            yield from resposta.iter_bytes()
        except httpx.HTTPError:
            log.exception('Conexão com o backend caiu durante o chat')
            erro = {'tipo': 'erro', 'mensagem': 'A conexão com o backend caiu. Tente de novo.'}
            yield (json.dumps(erro, ensure_ascii=False) + '\n').encode()
        finally:
            resposta.close()

    streaming = StreamingHttpResponse(fluxo(), content_type='application/x-ndjson')
    streaming['Cache-Control'] = 'no-cache'
    streaming['X-Accel-Buffering'] = 'no'  # evita buffer em proxies como nginx
    return streaming
