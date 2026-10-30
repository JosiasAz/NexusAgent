// Interface da equipe: projetos (histórico), criação com equipe montada pela IA e chat em streaming.
// Todo texto vindo do modelo ou do usuário entra com textContent, nunca como HTML.

const $ = (id) => document.getElementById(id);
const CSRF = document.querySelector('meta[name="csrf-token"]').content;
const ETAPAS = { planejamento: 'planejamento', desenvolvimento: 'desenvolvimento', revisao: 'revisão', versionamento: 'versionamento' };

const mensagens = $('mensagens');
const entrada = $('entrada');
let projetoAtual = null;   // { projeto, agentes }
let execucoes = [];        // um item por pedido: { pedido, eventos } (alimenta o painel de fluxo)
let ocupado = false;
const TELA_LARGA = window.matchMedia('(min-width: 1100px)');

// --- Utilidades --------------------------------------------------------------
function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    ...opcoes,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF, ...(opcoes.headers || {}) },
  });
  if (!resposta.ok) throw new Error(await lerErro(resposta));
  return resposta;
}

async function lerErro(resposta) {
  try {
    const corpo = await resposta.json();
    if (typeof corpo.detail === 'string') return corpo.detail;
    if (Array.isArray(corpo.detail)) return 'Dados inválidos (campo vazio ou longo demais).';
  } catch { /* corpo não é JSON */ }
  return `Erro ${resposta.status} no servidor.`;
}

function rolar() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function adicionar(el) {
  mensagens.appendChild(el);
  return el;
}

function definirOcupado(valor) {
  ocupado = valor;
  $('enviar').disabled = valor;
  $('excluir').disabled = valor;
  document.querySelectorAll('.ideias button').forEach((b) => (b.disabled = valor));
}

// --- Renderização de eventos (histórico e streaming usam o mesmo código) ------
function blocoCodigo(codigo) {
  const bloco = elemento('div', 'bloco-codigo');
  const pre = elemento('pre');
  pre.appendChild(elemento('code', '', codigo));
  const copiar = elemento('button', 'copiar', 'Copiar');
  copiar.type = 'button';
  copiar.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(codigo);
      copiar.textContent = 'Copiado!';
    } catch {
      copiar.textContent = 'Falhou';
    }
    setTimeout(() => (copiar.textContent = 'Copiar'), 1500);
  });
  bloco.append(pre, copiar);
  return bloco;
}

function cartao(agente, etapa, papel, conteudo, formato) {
  const card = $('tpl-cartao').content.firstElementChild.cloneNode(true);
  if (etapa) card.dataset.etapa = etapa;
  card.querySelector('.agente').textContent = agente;
  card.querySelector('.papel').textContent = papel || '';
  const corpo = card.querySelector('.conteudo');
  if (formato === 'codigo') corpo.appendChild(blocoCodigo(conteudo));
  else corpo.textContent = conteudo;
  return card;
}

function cartaoEquipe(evento) {
  const card = elemento('article', 'cartao equipe');
  card.appendChild(elemento('h3', '', `Montei ${evento.agentes.length} agentes para este projeto`));
  if (evento.aviso) card.appendChild(elemento('p', 'aviso', `⚠️ ${evento.aviso} Usando a equipe padrão.`));
  const lista = elemento('ul');
  for (const agente of evento.agentes) {
    const item = elemento('li');
    item.dataset.etapa = agente.etapa;
    item.append(elemento('strong', '', agente.nome), elemento('span', 'etapa', ETAPAS[agente.etapa] || agente.etapa),
      elemento('span', 'resp', agente.responsabilidade));
    lista.appendChild(item);
  }
  card.appendChild(lista);
  if (evento.ideias?.length) {
    card.appendChild(elemento('p', 'rotulo', 'Ideias para começar'));
    const ideias = elemento('div', 'ideias');
    for (const ideia of evento.ideias) {
      const botao = elemento('button', '', ideia);
      botao.type = 'button';
      botao.disabled = ocupado;
      botao.addEventListener('click', () => enviar(ideia));
      ideias.appendChild(botao);
    }
    card.appendChild(ideias);
  }
  return card;
}

function bolhaUsuario(texto, indice) {
  const bolha = elemento('div', 'usuario');
  bolha.appendChild(elemento('span', '', texto));
  const ver = elemento('button', 'ver-fluxo', 'Ver fluxo');
  ver.type = 'button';
  ver.title = 'Mostrar o passo a passo deste pedido no painel de fluxo';
  ver.addEventListener('click', () => {
    const execucao = execucoes[indice];
    Fluxo.carregar(projetoAtual.agentes, execucao.pedido, execucao.eventos);
    mostrarFluxo(true);
  });
  bolha.appendChild(ver);
  return bolha;
}

function mostrarEvento(evento, indice) {
  switch (evento.tipo) {
    case 'equipe':
      adicionar(cartaoEquipe(evento));
      break;
    case 'usuario':
      adicionar(bolhaUsuario(evento.conteudo, indice));
      break;
    case 'conversa':
      adicionar(cartao(evento.agente, 'planejamento', '', evento.conteudo));
      break;
    case 'etapa': {
      const papel = evento.rodada ? `${evento.papel} · rodada ${evento.rodada}` : evento.papel;
      adicionar(cartao(evento.agente, evento.etapa, papel, evento.conteudo, evento.formato));
      break;
    }
    case 'resultado':
      adicionar(elemento('p', `resultado ${evento.aprovado ? 'ok' : 'falha'}`, evento.aprovado
        ? `✔ Aprovado em ${evento.rodadas} rodada(s). Versão do projeto: ${evento.versao}`
        : `✘ Reprovado após ${evento.rodadas} rodada(s). Versão mantida: ${evento.versao}`));
      if (evento.aprovado) atualizarProjeto({ versao: evento.versao, codigo: evento.codigo });
      break;
    case 'erro':
      adicionar(elemento('p', 'cartao erro', `⚠️ ${evento.mensagem}`));
      break;
  }
}

// --- Lista de projetos (histórico) ---------------------------------------------
async function carregarLista() {
  try {
    const projetos = await (await api('/api/projetos')).json();
    const lista = $('lista-projetos');
    lista.replaceChildren();
    for (const p of projetos) {
      const link = elemento('a');
      link.href = `#/projeto/${p.id}`;
      if (projetoAtual?.projeto.id === p.id) link.setAttribute('aria-current', 'page');
      link.append(elemento('span', 'nome', p.titulo), elemento('span', 'sutil', `v${p.versao} · ${p.agentes} agentes`));
      const item = elemento('li');
      item.appendChild(link);
      lista.appendChild(item);
    }
    $('lista-vazia').hidden = projetos.length > 0;
  } catch (erro) {
    $('lista-vazia').hidden = false;
    $('lista-vazia').textContent = erro.message;
  }
}

// --- Telas -------------------------------------------------------------------
function mostrarTela(nome) {
  $('tela-novo').hidden = nome !== 'novo';
  $('tela-projeto').hidden = nome !== 'projeto';
  document.body.classList.remove('menu-aberto');
  $('fundo-menu').hidden = true;
}

function abrirNovo() {
  projetoAtual = null;
  execucoes = [];
  Fluxo.limpar();
  mostrarTela('novo');
  carregarLista();
  $('titulo').focus();
}

function atualizarProjeto({ versao, codigo }) {
  $('versao').textContent = versao;
  projetoAtual.projeto.versao = versao;
  projetoAtual.projeto.codigo = codigo;
  $('painel-codigo').hidden = !codigo;
  $('codigo-atual').replaceChildren(...(codigo ? [blocoCodigo(codigo)] : []));
}

async function abrirProjeto(id) {
  mostrarTela('projeto');
  mensagens.replaceChildren(elemento('p', 'digitando', 'Carregando projeto'));
  try {
    projetoAtual = await (await api(`/api/projetos/${id}`)).json();
  } catch (erro) {
    mensagens.replaceChildren(elemento('p', 'cartao erro', `⚠️ ${erro.message}`));
    return;
  }
  const { projeto, agentes } = projetoAtual;
  $('projeto-titulo').textContent = projeto.titulo;
  $('projeto-descricao').textContent = projeto.descricao;
  $('projeto-descricao').title = projeto.descricao;
  $('qtd-agentes').textContent = `${agentes.length} agentes`;
  atualizarProjeto(projeto);
  mensagens.replaceChildren();
  execucoes = [];
  for (const evento of projetoAtual.mensagens) {
    if (evento.tipo === 'usuario') execucoes.push({ pedido: evento.conteudo, eventos: [] });
    else execucoes.at(-1)?.eventos.push(evento);
    mostrarEvento(evento, execucoes.length - 1);
  }
  if (execucoes.length) Fluxo.carregar(agentes, execucoes.at(-1).pedido, execucoes.at(-1).eventos);
  else Fluxo.limpar();
  carregarLista();
  rolar();
  entrada.focus();
}

function rotear() {
  const id = location.hash.match(/^#\/projeto\/([0-9a-f]{32})$/)?.[1];
  if (id) abrirProjeto(id);
  else abrirNovo();
}

// --- Ações -------------------------------------------------------------------
$('form-projeto').addEventListener('submit', async (e) => {
  e.preventDefault();
  const botao = $('criar');
  const status = $('status-criacao');
  botao.disabled = true;
  status.className = 'sutil digitando';
  status.textContent = 'A IA está montando a equipe do projeto';
  try {
    const resposta = await api('/api/projetos', {
      method: 'POST',
      body: JSON.stringify({ titulo: $('titulo').value, descricao: $('descricao').value }),
    });
    const { projeto } = await resposta.json();
    $('form-projeto').reset();
    status.textContent = '';
    location.hash = `#/projeto/${projeto.id}`;
  } catch (erro) {
    status.className = 'sutil erro';
    status.textContent = `⚠️ ${erro.message}`;
  } finally {
    botao.disabled = false;
    if (status.textContent && !status.classList.contains('erro')) status.className = 'sutil';
  }
});

$('excluir').addEventListener('click', async () => {
  if (ocupado || !projetoAtual) return;
  if (!confirm(`Excluir o projeto "${projetoAtual.projeto.titulo}" e todo o histórico?`)) return;
  try {
    await api(`/api/projetos/${projetoAtual.projeto.id}`, { method: 'DELETE' });
    location.hash = '#/novo';
  } catch (erro) {
    alert(erro.message);
  }
});

async function enviar(texto) {
  if (ocupado || !projetoAtual || !texto.trim()) return;
  const id = projetoAtual.projeto.id;
  definirOcupado(true);
  const execucao = { pedido: texto, eventos: [] };
  execucoes.push(execucao);
  mostrarEvento({ tipo: 'usuario', conteudo: texto }, execucoes.length - 1);
  Fluxo.montar(projetoAtual.agentes, texto);
  const indicador = adicionar(elemento('p', 'digitando', 'A equipe está trabalhando'));
  rolar();

  try {
    const resposta = await api(`/api/projetos/${id}/chat`, { method: 'POST', body: JSON.stringify({ mensagem: texto }) });
    const leitor = resposta.body.getReader();
    const decodificador = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { value, done } = await leitor.read();
      if (done) break;
      buffer += decodificador.decode(value, { stream: true });
      const linhas = buffer.split('\n');
      buffer = linhas.pop();
      for (const linha of linhas) {
        if (!linha.trim() || projetoAtual?.projeto.id !== id) continue; // usuário trocou de projeto
        const evento = JSON.parse(linha);
        execucao.eventos.push(evento);
        Fluxo.evento(evento);
        mostrarEvento(evento);
        mensagens.appendChild(indicador); // mantém o indicador no fim
        rolar();
      }
    }
  } catch (erro) {
    if (projetoAtual?.projeto.id === id) {
      const evento = { tipo: 'erro', mensagem: erro.message || 'Falha de conexão com o servidor.' };
      Fluxo.evento(evento);
      mostrarEvento(evento);
    }
  } finally {
    indicador.remove();
    definirOcupado(false);
    carregarLista();
    entrada.focus();
  }
}

function ajustarAltura() {
  entrada.style.height = 'auto';
  entrada.style.height = `${entrada.scrollHeight}px`;
}

$('formulario').addEventListener('submit', (e) => {
  e.preventDefault();
  const texto = entrada.value;
  entrada.value = '';
  ajustarAltura();
  enviar(texto);
});

entrada.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    $('formulario').requestSubmit();
  }
});
entrada.addEventListener('input', ajustarAltura);

$('novo-projeto').addEventListener('click', () => {
  if (location.hash === '#/novo') abrirNovo();
  else location.hash = '#/novo';
});

document.querySelectorAll('.botao-menu').forEach((b) => b.addEventListener('click', () => {
  document.body.classList.add('menu-aberto');
  $('fundo-menu').hidden = false;
}));
$('fundo-menu').addEventListener('click', () => {
  document.body.classList.remove('menu-aberto');
  $('fundo-menu').hidden = true;
});

// --- Painel de fluxo: lado a lado em telas largas, sobreposto em telas estreitas ---
function mostrarFluxo(visivel) {
  document.body.classList.toggle('fluxo-visivel', visivel);
  $('alternar-fluxo').setAttribute('aria-pressed', String(visivel));
  if (TELA_LARGA.matches) {
    try { localStorage.setItem('equipe.fluxo', visivel ? '1' : '0'); } catch { /* sem storage */ }
  }
}

function preferenciaFluxo() {
  if (!TELA_LARGA.matches) return false;
  try { return localStorage.getItem('equipe.fluxo') !== '0'; } catch { return true; }
}

$('alternar-fluxo').addEventListener('click', () => mostrarFluxo(!document.body.classList.contains('fluxo-visivel')));
$('fechar-fluxo').addEventListener('click', () => mostrarFluxo(false));
TELA_LARGA.addEventListener('change', () => mostrarFluxo(preferenciaFluxo()));
mostrarFluxo(preferenciaFluxo());

// O painel de fluxo fica grudado logo abaixo do cabeçalho do projeto, qualquer que seja a altura dele.
new ResizeObserver(([e]) => document.documentElement.style.setProperty('--altura-topo', `${Math.ceil(e.target.offsetHeight)}px`))
  .observe(document.querySelector('.topo'));

window.addEventListener('hashchange', () => {
  if (ocupado) definirOcupado(false); // o streaming antigo segue no servidor, mas a tela muda
  rotear();
});

(async function iniciar() {
  try {
    const saude = await (await api('/api/saude')).json();
    $('modelo').textContent = saude.modelo;
  } catch {
    $('modelo').textContent = 'backend indisponível';
  }
  rotear();
})();
