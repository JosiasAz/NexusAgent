"""Chat no terminal: python -m backend.cli"""
from backend.agents import montar_equipe, projetar_equipe
from backend.chat import Repositorio, conversar, criar_projeto
from backend.config import DB_PATH, MAX_TOKENS_ARQUITETO, criar_modelo, descrever_modelo


def mostrar(evento):
    if evento['tipo'] == 'equipe':
        if evento['aviso']:
            print(f'\n⚠️ {evento["aviso"]} Usando a equipe padrão.')
        print(f'\nEquipe com {len(evento["agentes"])} agentes:')
        for agente in evento['agentes']:
            print(f'  • {agente["nome"]} ({agente["etapa"]}): {agente["responsabilidade"]}')
        print('Ideias para começar:\n' + '\n'.join(f'  - {ideia}' for ideia in evento['ideias']))
    elif evento['tipo'] == 'conversa':
        print(f'\n[{evento["agente"]}]\n{evento["conteudo"]}')
    elif evento['tipo'] == 'etapa':
        rodada = f' (rodada {evento["rodada"]})' if evento['rodada'] else ''
        print(f'\n[{evento["agente"]} — {evento["papel"]}{rodada}]\n{evento["conteudo"]}')
    elif evento['tipo'] == 'resultado':
        if evento['aprovado']:
            print(f'\n✔ Aprovado em {evento["rodadas"]} rodada(s). Versão do projeto: {evento["versao"]}')
        else:
            print(f'\n✘ Reprovado após {evento["rodadas"]} rodada(s); versão mantida em {evento["versao"]}.')
    elif evento['tipo'] == 'erro':
        print(f'\n[erro] {evento["mensagem"]}')


def ler(rotulo):
    while not (texto := input(rotulo).strip()):
        pass
    return texto


def main():
    repo, modelo = Repositorio(DB_PATH), criar_modelo()
    print(f'Equipe de software · {descrever_modelo()}')
    try:
        titulo, descricao = ler('Título do projeto> '), ler('Descrição> ')
    except (EOFError, KeyboardInterrupt):
        return
    print('\nMontando a equipe…')
    arquiteto = criar_modelo(max_tokens=MAX_TOKENS_ARQUITETO)
    projeto, evento = criar_projeto(repo, titulo, descricao, lambda t, d: projetar_equipe(t, d, arquiteto))
    mostrar(evento)
    equipe = montar_equipe(repo.agentes(projeto.id), projeto.titulo, projeto.descricao, modelo)

    print('\nDescreva o que quer construir ou digite "sair".')
    while True:
        try:
            mensagem = input('\nVocê> ').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if mensagem.lower() in {'sair', 'exit', 'quit'}:
            break
        if mensagem:
            for evento in conversar(repo, projeto, equipe, mensagem):
                mostrar(evento)
    print('Até mais! O projeto fica salvo e aparece no histórico da interface web.')


if __name__ == '__main__':
    main()
