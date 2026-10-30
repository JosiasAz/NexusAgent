"""Fluxo da equipe: planejar → desenvolver (1 a 3 agentes) ⇄ revisar (1 a 2) → versionar.

`executar` é um gerador de eventos (dicts). Cada agente vira um "nó" com id estável
(`plano`, `r1-dev-0`, `r1-rev-0`, `r1-decisao`, `versao`, `resultado`): o evento
`inicio` leva a entrada do nó e o evento `etapa` leva a saída, a duração, os tokens
e as ferramentas chamadas. O painel de fluxo do frontend desenha o grafo com eles.
"""
import logging
import time

from backend.agents import MARCADOR_CONVERSA
from backend.agents.base import cortar, extrair_codigo, invocar, rastrear, resultados_ferramenta
from backend.config import MAX_RODADAS
from backend.tools import VERSAO_VALIDA, proxima_versao, verificar_sintaxe

log = logging.getLogger(__name__)


def bloco(codigo):
    return f'```python\n{codigo}\n```'


def rodar(membro, no, entrada, rodada=None):
    """Emite o início do nó, chama o agente e devolve (texto, mensagens, dados do nó)."""
    yield {'tipo': 'inicio', 'no': no, 'agente': membro.nome, 'etapa': membro.etapa, 'papel': membro.papel,
           'rodada': rodada, 'entrada': cortar(entrada)}
    comeco = time.perf_counter()
    texto, mensagens = invocar(membro.agente, entrada)
    dados = {'no': no, 'agente': membro.nome, 'etapa': membro.etapa, 'papel': membro.papel, 'rodada': rodada,
             'duracao_ms': round((time.perf_counter() - comeco) * 1000), **rastrear(mensagens)}
    return texto, mensagens, dados


def etapa(dados, conteudo, formato='texto', **extra):
    return {'tipo': 'etapa', **dados, 'conteudo': cortar(conteudo), 'formato': formato, **extra}


def executar(mensagem, projeto, equipe, max_rodadas=MAX_RODADAS):
    contexto = projeto.contexto()
    plano, _, dados = yield from rodar(equipe.planejador, 'plano', f'{contexto}\n\nPedido: {mensagem}'.strip())
    if plano.strip().upper().startswith(MARCADOR_CONVERSA[:-1]):
        resposta = plano.strip()[len(MARCADOR_CONVERSA) - 1:].lstrip(':').strip()
        yield {'tipo': 'conversa', **dados, 'conteudo': resposta}
        return
    yield etapa(dados, plano)

    historico = projeto.contexto(incluir_codigo=False)
    revisao, codigo, aprovado = '', projeto.codigo, False
    for rodada in range(1, max_rodadas + 1):
        for i, dev in enumerate(equipe.desenvolvedores):
            pedido = f'{historico}\n\nPedido: {mensagem}\nPlano:\n{plano}'.strip()
            if codigo:
                pedido += f'\nCódigo atual (devolva-o completo com a sua contribuição):\n{bloco(codigo)}'
            if revisao:
                pedido += f'\nRevisão anterior:\n{revisao}'
            texto, _, dados = yield from rodar(dev, f'r{rodada}-dev-{i}', pedido, rodada)
            anterior, codigo = codigo, extrair_codigo(texto)
            yield etapa(dados, codigo, formato='codigo', codigo_anterior=cortar(anterior))

        pareceres = []
        for i, revisor in enumerate(equipe.revisores):
            parecer, _, dados = yield from rodar(revisor, f'r{rodada}-rev-{i}',
                                                 f'Pedido: {mensagem}\nCódigo:\n{bloco(codigo)}', rodada)
            pareceres.append((revisor.nome, parecer))
            yield etapa(dados, parecer, aprovado=parecer.strip().upper().startswith('APROVADO'))

        # O ast decide a sintaxe; os revisores decidem se o código cumpre o pedido.
        sintaxe = verificar_sintaxe.invoke({'codigo': codigo})
        votos = [{'agente': nome, 'aprovado': p.strip().upper().startswith('APROVADO')} for nome, p in pareceres]
        aprovado = sintaxe == 'SINTAXE_OK' and all(v['aprovado'] for v in votos)
        yield {'tipo': 'decisao', 'no': f'r{rodada}-decisao', 'rodada': rodada, 'sintaxe': sintaxe,
               'votos': votos, 'aprovado': aprovado, 'ultima': rodada == max_rodadas}
        if aprovado:
            break
        revisao = '\n'.join(f'{nome}: {parecer}' for nome, parecer in pareceres)
        if sintaxe != 'SINTAXE_OK':
            revisao += f'\nVerificação automática: {sintaxe}'

    if not aprovado:
        projeto.registrar(mensagem, 'reprovado')
        yield {'tipo': 'resultado', 'no': 'resultado', 'aprovado': False, 'rodadas': rodada,
               'versao': projeto.versao, 'commit': '', 'codigo': codigo}
        return

    commit, mensagens, dados = yield from rodar(
        equipe.versionador, 'versao', f'Versão atual: {projeto.versao}\nPedido: {mensagem}\nCódigo:\n{bloco(codigo)}')
    yield etapa(dados, commit)
    versoes = [v for v in resultados_ferramenta(mensagens, 'proxima_versao') if VERSAO_VALIDA.match(v)]
    if versoes:
        nova_versao = versoes[-1]
    else:
        log.warning('Versionador não usou proxima_versao; aplicando minor por padrão.')
        nova_versao = proxima_versao.invoke({'atual': projeto.versao, 'tipo': 'minor'})

    versao_anterior = projeto.versao
    projeto.versao, projeto.codigo = nova_versao, codigo
    projeto.registrar(mensagem, f'aprovado na versão {nova_versao}')
    yield {'tipo': 'resultado', 'no': 'resultado', 'aprovado': True, 'rodadas': rodada,
           'versao_anterior': versao_anterior, 'versao': nova_versao, 'commit': commit, 'codigo': codigo}
