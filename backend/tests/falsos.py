"""Agentes e modelos falsos: respostas fixas para testar o fluxo sem chamar a IA."""
from langchain_core.messages import AIMessage, ToolMessage

from backend.agents import EquipeMontada, Membro


class AgenteFalso:
    def __init__(self, *respostas, ferramenta=None):
        self.respostas = list(respostas)
        self.ferramenta = ferramenta  # (nome, conteúdo) devolvido como ToolMessage
        self.recebidos = []

    def invoke(self, entrada, config=None):
        self.recebidos.append(entrada['messages'][0]['content'])
        mensagens = []
        if self.ferramenta:
            nome, conteudo = self.ferramenta
            mensagens.append(AIMessage(content='', tool_calls=[{'name': nome, 'args': {'atual': '0.1.0'}, 'id': '1'}]))
            mensagens.append(ToolMessage(content=conteudo, name=nome, tool_call_id='1'))
        mensagens.append(AIMessage(content=self.respostas.pop(0),
                                   usage_metadata={'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}))
        return {'messages': mensagens}


CODIGO_OK = '```python\ndef soma(a, b):\n    """Soma."""\n    return a + b\n```'


def equipe_falsa(planos=('1. Somar',), devs=((CODIGO_OK,),), revisores=(('APROVADO ok',),),
                 commit='feat: soma', versao='0.2.0'):
    """Cada item de `devs` e `revisores` é a lista de respostas de um agente."""
    membro = lambda nome, etapa, agente: Membro(nome, etapa, f'cuida de {etapa}', agente)
    ferramenta = ('proxima_versao', versao) if versao else None
    return EquipeMontada(
        planejador=membro('Paulo', 'planejamento', AgenteFalso(*planos)),
        desenvolvedores=[membro(f'Dev{i}', 'desenvolvimento', AgenteFalso(*r)) for i, r in enumerate(devs, 1)],
        revisores=[membro(f'Rev{i}', 'revisao', AgenteFalso(*r)) for i, r in enumerate(revisores, 1)],
        versionador=membro('Vera', 'versionamento', AgenteFalso(commit, ferramenta=ferramenta)))


class ModeloFalso:
    """Imita `modelo.with_structured_output(Esquema).invoke(...)`."""

    def __init__(self, resposta):
        self.resposta = resposta
        self.pedidos = []

    def with_structured_output(self, esquema):
        return self

    def invoke(self, pedido):
        self.pedidos.append(pedido)
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta
