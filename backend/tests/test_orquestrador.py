import unittest

from backend.chat import Projeto, executar
from backend.tests.falsos import CODIGO_OK, equipe_falsa

CODIGO_DEV2 = '```python\ndef soma(a, b):\n    """Soma."""\n    return a + b\n\n\ndef test_soma():\n    assert soma(1, 2) == 3\n```'


def tipos(eventos):
    return [e['tipo'] for e in eventos]


def sem_rastro(eventos):
    """Só os eventos que o chat mostra (sem início de nó nem decisão de rodada)."""
    return [e for e in eventos if e['tipo'] not in ('inicio', 'decisao')]


def novo_projeto(**campos):
    return Projeto(titulo='Calculadora', descricao='Funções matemáticas', **campos)


class TestRastro(unittest.TestCase):
    def test_nos_tem_inicio_fim_e_metricas(self):
        projeto = novo_projeto(codigo='x = 1')
        eventos = list(executar('soma', projeto, equipe_falsa(revisores=(('APROVADO',), ('APROVADO',)))))
        nos = [(e['tipo'], e.get('no')) for e in eventos]
        self.assertEqual(nos, [('inicio', 'plano'), ('etapa', 'plano'),
                               ('inicio', 'r1-dev-0'), ('etapa', 'r1-dev-0'),
                               ('inicio', 'r1-rev-0'), ('etapa', 'r1-rev-0'),
                               ('inicio', 'r1-rev-1'), ('etapa', 'r1-rev-1'),
                               ('decisao', 'r1-decisao'),
                               ('inicio', 'versao'), ('etapa', 'versao'), ('resultado', 'resultado')])
        inicio_dev, fim_dev = eventos[2], eventos[3]
        self.assertIn('Pedido: soma', inicio_dev['entrada'])
        self.assertEqual(fim_dev['codigo_anterior'], 'x = 1')
        self.assertGreaterEqual(fim_dev['duracao_ms'], 0)
        self.assertEqual(fim_dev['tokens'], {'entrada': 10, 'saida': 5})
        decisao = eventos[8]
        self.assertEqual((decisao['sintaxe'], decisao['aprovado']), ('SINTAXE_OK', True))
        self.assertEqual([v['agente'] for v in decisao['votos']], ['Rev1', 'Rev2'])
        versao = eventos[10]
        self.assertEqual(versao['ferramentas'][0]['nome'], 'proxima_versao')
        self.assertEqual(versao['ferramentas'][0]['resultado'], '0.2.0')
        self.assertEqual((eventos[-1]['versao_anterior'], eventos[-1]['versao']), ('0.1.0', '0.2.0'))

    def test_decisao_reprovada_e_rodada_seguinte(self):
        equipe = equipe_falsa(devs=((CODIGO_OK, CODIGO_OK),), revisores=(('REPROVADO x', 'APROVADO'),))
        eventos = list(executar('soma', novo_projeto(), equipe))
        decisoes = [e for e in eventos if e['tipo'] == 'decisao']
        self.assertEqual([(d['no'], d['aprovado']) for d in decisoes], [('r1-decisao', False), ('r2-decisao', True)])
        self.assertIn(('inicio', 'r2-dev-0'), [(e['tipo'], e.get('no')) for e in eventos])


class TestOrquestrador(unittest.TestCase):
    def test_conversa_nao_aciona_equipe(self):
        equipe = equipe_falsa(planos=('CONVERSA: Olá! Criamos código Python.',))
        projeto = novo_projeto()
        eventos = list(executar('olá', projeto, equipe))
        self.assertEqual(tipos(eventos), ['inicio', 'conversa'])
        self.assertEqual(eventos[1]['conteudo'], 'Olá! Criamos código Python.')
        self.assertEqual(equipe.desenvolvedores[0].agente.recebidos, [])
        self.assertEqual(projeto.versao, '0.1.0')

    def test_aprovado_atualiza_projeto(self):
        projeto = novo_projeto()
        eventos = sem_rastro(executar('soma', projeto, equipe_falsa()))
        self.assertEqual(tipos(eventos), ['etapa', 'etapa', 'etapa', 'etapa', 'resultado'])
        self.assertEqual([e.get('etapa') for e in eventos[:4]],
                         ['planejamento', 'desenvolvimento', 'revisao', 'versionamento'])
        self.assertTrue(eventos[-1]['aprovado'])
        self.assertEqual(projeto.versao, '0.2.0')
        self.assertIn('def soma', projeto.codigo)

    def test_varios_desenvolvedores_trabalham_em_sequencia(self):
        equipe = equipe_falsa(devs=((CODIGO_OK,), (CODIGO_DEV2,)))
        projeto = novo_projeto()
        list(executar('soma com teste', projeto, equipe))
        self.assertIn('def soma', equipe.desenvolvedores[1].agente.recebidos[0])  # recebe o código do anterior
        self.assertIn('def test_soma', projeto.codigo)

    def test_todos_os_revisores_precisam_aprovar(self):
        equipe = equipe_falsa(devs=((CODIGO_OK, CODIGO_OK),),
                              revisores=(('APROVADO', 'APROVADO'), ('REPROVADO falta teste', 'APROVADO')))
        resultado = list(executar('soma', novo_projeto(), equipe))[-1]
        self.assertTrue(resultado['aprovado'])
        self.assertEqual(resultado['rodadas'], 2)
        self.assertIn('Rev2: REPROVADO falta teste', equipe.desenvolvedores[0].agente.recebidos[1])

    def test_reprovado_duas_vezes_mantem_versao_e_codigo(self):
        equipe = equipe_falsa(devs=((CODIGO_OK, CODIGO_OK),), revisores=(('REPROVADO a', 'REPROVADO b'),))
        projeto = novo_projeto(codigo='x = 1')
        resultado = list(executar('soma', projeto, equipe))[-1]
        self.assertFalse(resultado['aprovado'])
        self.assertEqual(resultado['rodadas'], 2)
        self.assertEqual((projeto.versao, projeto.codigo), ('0.1.0', 'x = 1'))

    def test_sintaxe_invalida_reprova_mesmo_com_aprovado(self):
        quebrado = '```python\ndef soma(a, b:\n```'
        equipe = equipe_falsa(devs=((quebrado, CODIGO_OK),), revisores=(('APROVADO', 'APROVADO'),))
        resultado = list(executar('soma', novo_projeto(), equipe))[-1]
        self.assertTrue(resultado['aprovado'])
        self.assertEqual(resultado['rodadas'], 2)
        self.assertIn('ERRO_SINTAXE', equipe.desenvolvedores[0].agente.recebidos[1])

    def test_versao_padrao_quando_versionador_nao_usa_ferramenta(self):
        projeto = novo_projeto(versao='1.4.2')
        list(executar('soma', projeto, equipe_falsa(versao=None)))
        self.assertEqual(projeto.versao, '1.5.0')

    def test_pedido_seguinte_recebe_codigo_e_historico(self):
        projeto = novo_projeto()
        list(executar('soma', projeto, equipe_falsa()))
        equipe = equipe_falsa(versao='0.2.1')
        list(executar('agora subtrai', projeto, equipe))
        self.assertIn('def soma', equipe.planejador.agente.recebidos[0])
        recebido_dev = equipe.desenvolvedores[0].agente.recebidos[0]
        self.assertIn('Pedidos anteriores', recebido_dev)
        self.assertIn('Código atual', recebido_dev)


if __name__ == '__main__':
    unittest.main()
