import json
from unittest import mock

import httpx
from django.test import Client, SimpleTestCase

from chat import views

ID = 'a' * 32
EVENTOS = (b'{"tipo": "etapa", "agente": "Ana"}\n'
           b'{"tipo": "resultado", "aprovado": true, "versao": "0.2.0"}\n')


def backend_falso(rotas, recebidos=None):
    """Cliente httpx que responde pelas rotas dadas, sem rede."""
    def responder(pedido):
        if recebidos is not None:
            recebidos.append((pedido.method, pedido.url.path, pedido.content))
        resposta = rotas.get((pedido.method, pedido.url.path))
        if isinstance(resposta, Exception):
            raise resposta
        return resposta or httpx.Response(404, json={'detail': 'não encontrado'})
    return httpx.Client(base_url='http://backend', transport=httpx.MockTransport(responder))


class TestFrontend(SimpleTestCase):
    def usar_backend(self, rotas, recebidos=None):
        patcher = mock.patch.object(views, 'cliente', backend_falso(rotas, recebidos))
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, url, corpo):
        return self.client.post(url, json.dumps(corpo), content_type='application/json')

    def test_pagina_inicial_tem_token_csrf(self):
        resposta = self.client.get('/')
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Novo projeto')
        self.assertContains(resposta, 'name="csrf-token"')
        self.assertEqual(self.client.head('/').status_code, 200)

    def test_listar_e_criar_projeto(self):
        recebidos = []
        self.usar_backend({('GET', '/api/projetos'): httpx.Response(200, json=[{'id': ID}]),
                           ('POST', '/api/projetos'): httpx.Response(201, json={'projeto': {'id': ID}})}, recebidos)
        self.assertEqual(self.client.get('/api/projetos').json(), [{'id': ID}])
        resposta = self.post('/api/projetos', {'titulo': 'Estoque', 'descricao': 'Loja'})
        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(json.loads(recebidos[-1][2]), {'titulo': 'Estoque', 'descricao': 'Loja'})

    def test_ver_e_excluir_projeto(self):
        self.usar_backend({('GET', f'/api/projetos/{ID}'): httpx.Response(200, json={'projeto': {'id': ID}}),
                           ('DELETE', f'/api/projetos/{ID}'): httpx.Response(204)})
        self.assertEqual(self.client.get(f'/api/projetos/{ID}').json()['projeto']['id'], ID)
        self.assertEqual(self.client.delete(f'/api/projetos/{ID}').status_code, 204)

    def test_chat_transmite_eventos_do_backend(self):
        self.usar_backend({('POST', f'/api/projetos/{ID}/chat'): httpx.Response(200, content=EVENTOS)})
        resposta = self.post(f'/api/projetos/{ID}/chat', {'mensagem': 'soma'})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/x-ndjson')
        self.assertEqual(b''.join(resposta.streaming_content), EVENTOS)

    def test_erros_do_backend_sao_repassados(self):
        self.usar_backend({('POST', f'/api/projetos/{ID}/chat'): httpx.Response(409, json={'detail': 'ocupado'}),
                           ('POST', '/api/projetos'): httpx.Response(422, json={'detail': []})})
        self.assertEqual(self.post(f'/api/projetos/{ID}/chat', {'mensagem': 'x'}).status_code, 409)
        self.assertEqual(self.post('/api/projetos', {'titulo': ''}).status_code, 422)

    def test_backend_fora_do_ar_retorna_502(self):
        erro = httpx.ConnectError('recusado')
        self.usar_backend({('POST', f'/api/projetos/{ID}/chat'): erro, ('GET', '/api/saude'): erro,
                           ('GET', '/api/projetos'): erro})
        self.assertEqual(self.post(f'/api/projetos/{ID}/chat', {'mensagem': 'oi'}).status_code, 502)
        self.assertEqual(self.client.get('/api/saude').status_code, 502)
        self.assertEqual(self.client.get('/api/projetos').status_code, 502)

    def test_json_invalido(self):
        for corpo in ('não é json', '[1, 2]'):
            self.assertEqual(self.client.post('/api/projetos', corpo, content_type='application/json').status_code, 400)
            self.assertEqual(self.client.post(f'/api/projetos/{ID}/chat', corpo,
                                              content_type='application/json').status_code, 400)

    def test_escrita_exige_csrf(self):
        cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(cliente.post('/api/projetos', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(cliente.delete(f'/api/projetos/{ID}').status_code, 403)

    def test_rotas_so_aceitam_id_valido_e_metodos_certos(self):
        self.assertEqual(self.client.get('/api/projetos/..%2Fsaude').status_code, 404)
        self.assertEqual(self.client.get('/api/projetos/abc').status_code, 404)
        self.assertEqual(self.client.get(f'/api/projetos/{ID}/chat').status_code, 405)
        self.assertEqual(self.client.put(f'/api/projetos/{ID}').status_code, 405)
