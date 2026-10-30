"""Estado de um projeto: versão, código atual e pedidos recentes."""
import uuid
from dataclasses import dataclass, field

from backend.config import VERSAO_INICIAL

MAX_HISTORICO = 5


@dataclass
class Projeto:
    titulo: str
    descricao: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    versao: str = VERSAO_INICIAL
    codigo: str = ''
    historico: list = field(default_factory=list)

    def registrar(self, pedido, resumo):
        self.historico = (self.historico + [[pedido, resumo]])[-MAX_HISTORICO:]

    def contexto(self, incluir_codigo=True):
        """Texto com o estado do projeto para enviar aos agentes."""
        partes = []
        if self.historico:
            partes.append('Pedidos anteriores:\n' + '\n'.join(f'- {p} → {r}' for p, r in self.historico))
        if incluir_codigo and self.codigo:
            partes.append(f'Código atual do projeto (versão {self.versao}):\n```python\n{self.codigo}\n```')
        return '\n\n'.join(partes)
