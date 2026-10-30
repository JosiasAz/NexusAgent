import tempfile
import unittest
from pathlib import Path

from backend.agents import EQUIPE_PADRAO
from backend.chat import Projeto, Repositorio


class TestRepositorio(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.repo = Repositorio(Path(self.pasta.name) / 'sub' / 'teste.db')

    def tearDown(self):
        self.pasta.cleanup()

    def test_ciclo_completo(self):
        projeto = Projeto(titulo='Estoque', descricao='Loja')
        self.repo.criar_projeto(projeto, EQUIPE_PADRAO)
        self.repo.adicionar_mensagem(projeto.id, {'tipo': 'usuario', 'conteudo': 'olá ✓'})

        projeto.versao, projeto.codigo = '0.2.0', 'x = 1'
        projeto.registrar('pedido', 'aprovado')
        self.repo.salvar_projeto(projeto)

        lido = self.repo.obter_projeto(projeto.id)
        self.assertEqual((lido.versao, lido.codigo, lido.historico), ('0.2.0', 'x = 1', [['pedido', 'aprovado']]))
        self.assertEqual([a['nome'] for a in self.repo.agentes(projeto.id)], ['Paulo', 'Dora', 'Rui', 'Vera'])
        self.assertEqual(self.repo.mensagens(projeto.id), [{'tipo': 'usuario', 'conteudo': 'olá ✓'}])
        self.assertEqual(self.repo.listar_projetos()[0]['agentes'], 4)

        self.assertTrue(self.repo.excluir_projeto(projeto.id))
        self.assertIsNone(self.repo.obter_projeto(projeto.id))
        self.assertEqual(self.repo.mensagens(projeto.id), [])  # apagadas em cascata
        self.assertFalse(self.repo.excluir_projeto(projeto.id))

    def test_lista_mais_recente_primeiro(self):
        a, b = Projeto('A', 'a'), Projeto('B', 'b')
        self.repo.criar_projeto(a, EQUIPE_PADRAO)
        self.repo.criar_projeto(b, EQUIPE_PADRAO)
        with self.repo.conexao() as banco:  # força datas distintas
            banco.execute("UPDATE projetos SET atualizado_em = '2000-01-01' WHERE id = ?", (b.id,))
        self.assertEqual([p['titulo'] for p in self.repo.listar_projetos()], ['A', 'B'])

    def test_dados_sobrevivem_a_nova_instancia(self):
        projeto = Projeto('Persistente', 'teste')
        self.repo.criar_projeto(projeto, EQUIPE_PADRAO)
        outro = Repositorio(self.repo.caminho)
        self.assertEqual(outro.obter_projeto(projeto.id).titulo, 'Persistente')


if __name__ == '__main__':
    unittest.main()
