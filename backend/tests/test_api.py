import json
import tempfile
import threading
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.agents import EQUIPE_PADRAO
from backend.api import app as modulo
from backend.chat import Repositorio
from backend.tests.falsos import equipe_falsa

app = modulo.app


def eventos(resposta):
    return [json.loads(linha) for linha in resposta.text.splitlines() if linha.strip()]


class TestApi(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.repo = Repositorio(Path(self.pasta.name) / 'teste.db')
        self.arquitetadas = []

        def arquitetar(titulo, descricao):
            self.arquitetadas.append((titulo, descricao))
            return EQUIPE_PADRAO, ['Primeira ideia']

        app.dependency_overrides[modulo.obter_repositorio] = lambda: self.repo
        app.dependency_overrides[modulo.obter_arquiteto] = lambda: arquitetar
        app.dependency_overrides[modulo.obter_montador] = lambda: (lambda definicoes, projeto: equipe_falsa())
        self.cliente = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        modulo._equipes.clear()
        self.pasta.cleanup()

    def criar(self, titulo='Estoque', descricao='Loja pequena'):
        resposta = self.cliente.post('/api/projetos', json={'titulo': titulo, 'descricao': descricao})
        self.assertEqual(resposta.status_code, 201)
        return resposta.json()

    def test_saude(self):
        self.assertEqual(self.cliente.get('/api/saude').json()['status'], 'ok')

    def test_criar_projeto_registra_equipe_e_ideias(self):
        dados = self.criar('  Estoque  ')
        self.assertEqual(dados['projeto']['titulo'], 'Estoque')  # espaços removidos
        self.assertEqual(len(dados['agentes']), 4)
        equipe = dados['mensagens'][0]
        self.assertEqual((equipe['tipo'], equipe['origem'], equipe['ideias']), ('equipe', 'ia', ['Primeira ideia']))
        self.assertEqual(len(equipe['agentes']), 4)
        self.assertEqual(self.cliente.get('/api/projetos').json()[0]['id'], dados['projeto']['id'])

    def test_falha_do_arquiteto_usa_equipe_padrao(self):
        def quebrado(titulo, descricao):
            raise RuntimeError('429 RESOURCE_EXHAUSTED')
        app.dependency_overrides[modulo.obter_arquiteto] = lambda: quebrado
        equipe = self.criar()['mensagens'][0]
        self.assertEqual(equipe['origem'], 'padrao')
        self.assertIn('Limite de uso', equipe['aviso'])
        self.assertEqual([a['nome'] for a in equipe['agentes']], ['Paulo', 'Dora', 'Rui', 'Vera'])

    def test_validacao_de_entrada(self):
        self.assertEqual(self.cliente.post('/api/projetos', json={'titulo': ' ', 'descricao': 'x'}).status_code, 422)
        self.assertEqual(self.cliente.post('/api/projetos', json={'titulo': 'x' * 81, 'descricao': 'x'}).status_code, 422)
        self.assertEqual(self.cliente.post('/api/projetos', json={'titulo': 'x', 'descricao': 'x' * 1501}).status_code, 422)
        projeto_id = self.criar()['projeto']['id']
        self.assertEqual(self.cliente.post(f'/api/projetos/{projeto_id}/chat', json={'mensagem': ''}).status_code, 422)
        self.assertEqual(self.cliente.get('/api/projetos/nao-hex').status_code, 422)
        self.assertEqual(self.cliente.get(f'/api/projetos/{"0" * 32}').status_code, 404)

    def test_chat_persiste_historico_e_versao(self):
        projeto_id = self.criar()['projeto']['id']
        lista = eventos(self.cliente.post(f'/api/projetos/{projeto_id}/chat', json={'mensagem': 'soma'}))
        self.assertEqual(lista[-1]['tipo'], 'resultado')
        dados = self.cliente.get(f'/api/projetos/{projeto_id}').json()
        self.assertEqual(dados['projeto']['versao'], '0.2.0')
        self.assertIn('def soma', dados['projeto']['codigo'])
        self.assertEqual([m['tipo'] for m in dados['mensagens'] if m['tipo'] not in ('inicio', 'decisao')],
                         ['equipe', 'usuario', 'etapa', 'etapa', 'etapa', 'etapa', 'resultado'])
        self.assertEqual(sum(m['tipo'] == 'inicio' for m in dados['mensagens']), 4)  # rastro salvo para o replay

    def test_projetos_tem_versoes_independentes(self):
        a, b = self.criar('A')['projeto']['id'], self.criar('B')['projeto']['id']
        eventos(self.cliente.post(f'/api/projetos/{a}/chat', json={'mensagem': 'soma'}))
        self.assertEqual(self.cliente.get(f'/api/projetos/{a}').json()['projeto']['versao'], '0.2.0')
        self.assertEqual(self.cliente.get(f'/api/projetos/{b}').json()['projeto']['versao'], '0.1.0')

    def test_erro_do_modelo_vira_evento_e_libera_o_projeto(self):
        class Quebrado:
            def invoke(self, *args, **kwargs):
                raise RuntimeError('429 RESOURCE_EXHAUSTED')

        def montar(definicoes, projeto):
            equipe = equipe_falsa()
            equipe.planejador.agente = Quebrado()
            return equipe

        app.dependency_overrides[modulo.obter_montador] = lambda: montar
        projeto_id = self.criar()['projeto']['id']
        lista = eventos(self.cliente.post(f'/api/projetos/{projeto_id}/chat', json={'mensagem': 'soma'}))
        self.assertEqual(lista[-1]['tipo'], 'erro')
        self.assertIn('Limite de uso', lista[-1]['mensagem'])
        self.assertEqual(self.cliente.get(f'/api/projetos/{projeto_id}').json()['mensagens'][-1]['tipo'], 'erro')
        self.assertTrue(modulo.trava_do_projeto(projeto_id).acquire(blocking=False))  # trava liberada
        modulo.trava_do_projeto(projeto_id).release()

    def test_pedido_simultaneo_no_mesmo_projeto_e_recusado(self):
        projeto_id = self.criar()['projeto']['id']
        trava = modulo.trava_do_projeto(projeto_id)
        trava.acquire()
        try:
            resposta = self.cliente.post(f'/api/projetos/{projeto_id}/chat', json={'mensagem': 'soma'})
            self.assertEqual(resposta.status_code, 409)
            self.assertEqual(self.cliente.delete(f'/api/projetos/{projeto_id}').status_code, 409)
        finally:
            trava.release()

    def test_excluir_projeto(self):
        projeto_id = self.criar()['projeto']['id']
        self.assertEqual(self.cliente.delete(f'/api/projetos/{projeto_id}').status_code, 204)
        self.assertEqual(self.cliente.get(f'/api/projetos/{projeto_id}').status_code, 404)
        self.assertEqual(self.cliente.delete(f'/api/projetos/{projeto_id}').status_code, 404)
        self.assertEqual(self.cliente.get('/api/projetos').json(), [])

    def test_equipe_e_montada_uma_vez_por_projeto(self):
        montagens = []
        lock = threading.Lock()

        def montar(definicoes, projeto):
            with lock:
                montagens.append(projeto.id)
            return equipe_falsa(planos=('CONVERSA: oi',))

        app.dependency_overrides[modulo.obter_montador] = lambda: montar
        projeto_id = self.criar()['projeto']['id']
        for _ in range(2):
            eventos(self.cliente.post(f'/api/projetos/{projeto_id}/chat', json={'mensagem': 'oi'}))
        # A equipe em cache já gastou a resposta do planejador; o segundo pedido vira erro, mas montou só uma vez.
        self.assertEqual(montagens, [projeto_id])


if __name__ == '__main__':
    unittest.main()
