import unittest

from backend.agents.base import extrair_codigo
from backend.tools import proxima_versao, verificar_sintaxe


class TestVerificarSintaxe(unittest.TestCase):
    def test_codigo_valido(self):
        self.assertEqual(verificar_sintaxe.invoke({'codigo': 'def f():\n    return 1'}), 'SINTAXE_OK')

    def test_codigo_invalido(self):
        self.assertTrue(verificar_sintaxe.invoke({'codigo': 'def f(:'}).startswith('ERRO_SINTAXE'))

    def test_codigo_vazio(self):
        self.assertTrue(verificar_sintaxe.invoke({'codigo': '   '}).startswith('ERRO_SINTAXE'))


class TestProximaVersao(unittest.TestCase):
    def test_tipos(self):
        for tipo, esperado in [('major', '2.0.0'), ('minor', '1.3.0'), ('patch', '1.2.4'), (' MINOR ', '1.3.0')]:
            self.assertEqual(proxima_versao.invoke({'atual': '1.2.3', 'tipo': tipo}), esperado)

    def test_entradas_invalidas_viram_texto_de_erro(self):
        self.assertTrue(proxima_versao.invoke({'atual': '1.2', 'tipo': 'minor'}).startswith('ERRO'))
        self.assertTrue(proxima_versao.invoke({'atual': '1.2.3', 'tipo': 'mega'}).startswith('ERRO'))


class TestExtrairCodigo(unittest.TestCase):
    def test_bloco_python(self):
        self.assertEqual(extrair_codigo('texto\n```python\nx = 1\n```\nfim'), 'x = 1')

    def test_primeiro_bloco(self):
        self.assertEqual(extrair_codigo('```python\na = 1\n```\n```python\nb = 2\n```'), 'a = 1')

    def test_bloco_sem_fechamento(self):
        self.assertEqual(extrair_codigo('```python\ndef f():\n    return 1\n'), 'def f():\n    return 1')

    def test_sem_bloco(self):
        self.assertEqual(extrair_codigo('x = 1'), 'x = 1')


if __name__ == '__main__':
    unittest.main()
