import unittest

from backend.agents import montar_equipe, projetar_equipe
from backend.agents.arquiteto import AgenteProjetado, EquipeProjetada, normalizar
from backend.agents.fabrica import PROTOCOLOS
from backend.tests.falsos import ModeloFalso


def agente(nome, etapa, resp='cuida de algo', instr='trabalhe bem'):
    return AgenteProjetado(nome=nome, etapa=etapa, responsabilidade=resp, instrucoes=instr)


class TestNormalizar(unittest.TestCase):
    def test_equipe_completa_e_mantida(self):
        equipe = EquipeProjetada(agentes=[agente('Ana', 'planejamento'), agente('Bia', 'desenvolvimento'),
                                          agente('Caio', 'desenvolvimento'), agente('Duda', 'revisao'),
                                          agente('Edu', 'versionamento')], ideias=['a', 'b', 'c'])
        definicoes, ideias = normalizar(equipe)
        self.assertEqual([d['nome'] for d in definicoes], ['Ana', 'Bia', 'Caio', 'Duda', 'Edu'])
        self.assertEqual(ideias, ['a', 'b', 'c'])

    def test_limites_por_etapa_e_etapas_faltando(self):
        equipe = EquipeProjetada(agentes=[agente('A', 'planejamento'), agente('B', 'planejamento')]
                                 + [agente(f'D{i}', 'desenvolvimento') for i in range(5)], ideias=[])
        definicoes, ideias = normalizar(equipe)
        contagem = {e: sum(d['etapa'] == e for d in definicoes)
                    for e in ('planejamento', 'desenvolvimento', 'revisao', 'versionamento')}
        self.assertEqual(contagem, {'planejamento': 1, 'desenvolvimento': 3, 'revisao': 1, 'versionamento': 1})
        self.assertIn('Rui', [d['nome'] for d in definicoes])  # revisor padrão preencheu a falta
        self.assertTrue(ideias)  # ideias padrão

    def test_nomes_repetidos_vazios_e_textos_longos(self):
        equipe = EquipeProjetada(agentes=[agente('Ana', 'planejamento'), agente('ana', 'desenvolvimento'),
                                          agente('  ', 'desenvolvimento'), agente('Rev', 'revisao', instr='x' * 5000),
                                          agente('Ver', 'versionamento')], ideias=['  ', 'ok'])
        definicoes, ideias = normalizar(equipe)
        nomes = [d['nome'] for d in definicoes]
        self.assertEqual(nomes, ['Ana', 'ana 2', 'Rev', 'Ver'])
        self.assertLessEqual(len(definicoes[2]['instrucoes']), 700)
        self.assertEqual(ideias, ['ok'])


class TestProjetar(unittest.TestCase):
    def test_usa_titulo_e_descricao_no_pedido(self):
        modelo = ModeloFalso(EquipeProjetada(agentes=[agente('Ana', 'planejamento')], ideias=['x']))
        definicoes, _ = projetar_equipe('Estoque', 'Loja {pequena}', modelo)
        self.assertIn('Loja {pequena}', modelo.pedidos[0])
        self.assertEqual(len(definicoes), 4)

    def test_modelo_sem_resposta_gera_erro(self):
        with self.assertRaises(ValueError):
            projetar_equipe('X', 'Y', ModeloFalso(None))


class TestFabrica(unittest.TestCase):
    def test_monta_agentes_com_ferramentas_e_protocolo_da_etapa(self):
        criados = []
        criar = lambda modelo, tools, system_prompt: criados.append((tools, system_prompt)) or object()
        definicoes, _ = normalizar(EquipeProjetada(agentes=[], ideias=[]))
        equipe = montar_equipe(definicoes, 'Estoque', 'Loja', modelo=None, criar=criar)
        self.assertEqual(len(equipe.desenvolvedores), 1)
        ferramentas = [[t.name for t in tools] for tools, _ in criados]
        self.assertEqual(ferramentas, [[], [], ['verificar_sintaxe'], ['proxima_versao']])
        self.assertIn(PROTOCOLOS['revisao'], criados[2][1])
        self.assertIn('"Estoque"', criados[0][1])


if __name__ == '__main__':
    unittest.main()
