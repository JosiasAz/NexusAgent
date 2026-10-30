"""Persistência em SQLite: projetos, agentes de cada projeto e histórico de mensagens."""
import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend.chat.projeto import Projeto

ESQUEMA = """
CREATE TABLE IF NOT EXISTS projetos (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    descricao TEXT NOT NULL,
    versao TEXT NOT NULL,
    codigo TEXT NOT NULL DEFAULT '',
    historico TEXT NOT NULL DEFAULT '[]',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agentes (
    projeto_id TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    nome TEXT NOT NULL,
    etapa TEXT NOT NULL,
    responsabilidade TEXT NOT NULL,
    instrucoes TEXT NOT NULL,
    PRIMARY KEY (projeto_id, ordem)
);
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id TEXT NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    evento TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensagens_projeto ON mensagens (projeto_id, id);
"""


def agora():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Repositorio:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.conexao() as banco:
            banco.execute('PRAGMA journal_mode = WAL')
            banco.executescript(ESQUEMA)

    @contextmanager
    def conexao(self):
        # Uma conexão por operação: seguro entre as threads do servidor.
        with closing(sqlite3.connect(self.caminho, timeout=10)) as banco:
            banco.row_factory = sqlite3.Row
            banco.execute('PRAGMA foreign_keys = ON')
            with banco:
                yield banco

    def criar_projeto(self, projeto, definicoes):
        momento = agora()
        with self.conexao() as banco:
            banco.execute('INSERT INTO projetos VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                          (projeto.id, projeto.titulo, projeto.descricao, projeto.versao, projeto.codigo,
                           json.dumps(projeto.historico, ensure_ascii=False), momento, momento))
            banco.executemany('INSERT INTO agentes VALUES (?, ?, ?, ?, ?, ?)',
                              [(projeto.id, ordem, d['nome'], d['etapa'], d['responsabilidade'], d['instrucoes'])
                               for ordem, d in enumerate(definicoes)])

    def salvar_projeto(self, projeto):
        with self.conexao() as banco:
            banco.execute('UPDATE projetos SET versao = ?, codigo = ?, historico = ?, atualizado_em = ? WHERE id = ?',
                          (projeto.versao, projeto.codigo, json.dumps(projeto.historico, ensure_ascii=False),
                           agora(), projeto.id))

    def obter_projeto(self, projeto_id):
        with self.conexao() as banco:
            linha = banco.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,)).fetchone()
        if not linha:
            return None
        return Projeto(titulo=linha['titulo'], descricao=linha['descricao'], id=linha['id'],
                       versao=linha['versao'], codigo=linha['codigo'], historico=json.loads(linha['historico']))

    def listar_projetos(self):
        with self.conexao() as banco:
            linhas = banco.execute(
                'SELECT p.id, p.titulo, p.descricao, p.versao, p.criado_em, p.atualizado_em, '
                '(SELECT COUNT(*) FROM agentes a WHERE a.projeto_id = p.id) AS agentes '
                'FROM projetos p ORDER BY p.atualizado_em DESC, p.criado_em DESC').fetchall()
        return [dict(linha) for linha in linhas]

    def agentes(self, projeto_id):
        with self.conexao() as banco:
            linhas = banco.execute('SELECT nome, etapa, responsabilidade, instrucoes FROM agentes '
                                   'WHERE projeto_id = ? ORDER BY ordem', (projeto_id,)).fetchall()
        return [dict(linha) for linha in linhas]

    def adicionar_mensagem(self, projeto_id, evento):
        with self.conexao() as banco:
            banco.execute('INSERT INTO mensagens (projeto_id, evento, criado_em) VALUES (?, ?, ?)',
                          (projeto_id, json.dumps(evento, ensure_ascii=False), agora()))

    def mensagens(self, projeto_id):
        with self.conexao() as banco:
            linhas = banco.execute('SELECT evento FROM mensagens WHERE projeto_id = ? ORDER BY id',
                                   (projeto_id,)).fetchall()
        return [json.loads(linha['evento']) for linha in linhas]

    def excluir_projeto(self, projeto_id):
        with self.conexao() as banco:
            return banco.execute('DELETE FROM projetos WHERE id = ?', (projeto_id,)).rowcount > 0
