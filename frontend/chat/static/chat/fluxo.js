// Painel de fluxo (estilo n8n): grafo de nós da execução e inspetor do nó selecionado.
// Recebe os mesmos eventos NDJSON do chat; cada evento traz o id do nó (`no`).
// Todo texto entra com textContent, nunca como HTML.

const Fluxo = (() => {
  const ICONES = { pedido: '✉', planejamento: '🧭', desenvolvimento: '⌨', revisao: '🔍',
    decisao: '⚖', versionamento: '🏷', resultado: '🏁' };
  const ESTADOS = { aguardando: 'aguardando', executando: 'executando', concluido: 'concluído',
    reprovado: 'reprovado', pulado: 'pulado', erro: 'erro' };

  let nos = new Map();       // id → { el, info, estado, dados }
  let agentes = [];
  let selecionado = null;
  let relogio = null;
  let aoVivo = false;

  const $ = (id) => document.getElementById(id);

  function criar(tag, classe, texto) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined && texto !== null) el.textContent = texto;
    return el;
  }

  const segundos = (ms) => `${(ms / 1000).toFixed(1)}s`;
  const seguindo = () => aoVivo && $('seguir').checked;

  // --- Grafo ------------------------------------------------------------------
  function criarNo(id, info) {
    const el = criar('button', 'no');
    el.type = 'button';
    el.dataset.etapa = info.etapa;
    el.dataset.estado = 'aguardando';
    el.append(criar('span', 'no-icone', ICONES[info.etapa] || '•'),
      criar('span', 'no-titulo', info.titulo), criar('span', 'no-sub', info.sub), criar('span', 'no-tempo', ''));
    el.setAttribute('aria-label', `${info.titulo} (${info.sub})`);
    el.addEventListener('click', () => selecionar(id));
    nos.set(id, { el, info, estado: 'aguardando', dados: {} });
    return el;
  }

  function criarLinha(rotulo, ids, chave) {
    const linha = criar('div', 'linha');
    if (chave) linha.dataset.linha = chave;
    linha.appendChild(criar('span', 'linha-rotulo', rotulo));
    const trilha = criar('div', 'trilha');
    ids.forEach(([id, info], i) => {
      if (i) trilha.appendChild(criar('span', 'conector', '→'));
      trilha.appendChild(criarNo(id, info));
    });
    linha.appendChild(trilha);
    return linha;
  }

  function garantirRodada(n) {
    if (!n || $('grafo').querySelector(`[data-linha="r${n}"]`)) return;
    const da = (etapa) => agentes.filter((a) => a.etapa === etapa);
    const ids = [
      ...da('desenvolvimento').map((a, i) => [`r${n}-dev-${i}`, { titulo: a.nome, sub: 'desenvolvimento', etapa: 'desenvolvimento' }]),
      ...da('revisao').map((a, i) => [`r${n}-rev-${i}`, { titulo: a.nome, sub: 'revisão', etapa: 'revisao' }]),
      [`r${n}-decisao`, { titulo: 'Decisão', sub: 'ast + votos', etapa: 'decisao' }],
    ];
    const linha = criarLinha(`Rodada ${n}`, ids, `r${n}`);
    $('grafo').insertBefore(linha, $('grafo').querySelector('[data-linha="saida"]'));
  }

  function montar(agentesProjeto, pedido, vivo = true) {
    limpar();
    aoVivo = vivo;
    agentes = agentesProjeto;
    $('fluxo-pedido').textContent = pedido;
    const planejador = agentes.find((a) => a.etapa === 'planejamento') || { nome: 'Planejador' };
    const versionador = agentes.find((a) => a.etapa === 'versionamento') || { nome: 'Versionador' };
    const grafo = $('grafo');
    grafo.appendChild(criarLinha('Entrada', [
      ['pedido', { titulo: 'Pedido', sub: 'usuário', etapa: 'pedido' }],
      ['plano', { titulo: planejador.nome, sub: 'planejamento', etapa: 'planejamento' }],
    ], 'entrada'));
    grafo.appendChild(criarLinha('Saída', [
      ['versao', { titulo: versionador.nome, sub: 'versionamento', etapa: 'versionamento' }],
      ['resultado', { titulo: 'Resultado', sub: 'versão final', etapa: 'resultado' }],
    ], 'saida'));
    garantirRodada(1);
    definir('pedido', 'concluido', { saida: pedido });
    if (vivo) {
      relogio = setInterval(atualizarTempos, 200);
      selecionar('pedido');
    }
  }

  function definir(id, estado, dados = {}) {
    const no = nos.get(id);
    if (!no) return;
    no.estado = estado;
    Object.assign(no.dados, dados);
    no.el.dataset.estado = estado;
    if (no.dados.duracao_ms !== undefined) no.el.querySelector('.no-tempo').textContent = segundos(no.dados.duracao_ms);
    if (selecionado === id) inspecionar(id);
  }

  function pularRestantes(estadoDosAtivos) {
    for (const [id, no] of nos) {
      if (no.estado === 'aguardando') definir(id, 'pulado');
      if (no.estado === 'executando' && estadoDosAtivos) definir(id, estadoDosAtivos);
    }
  }

  function atualizarTempos() {
    for (const no of nos.values()) {
      if (no.estado === 'executando') {
        no.el.querySelector('.no-tempo').textContent = segundos(performance.now() - no.dados.comeco);
      }
    }
    if (selecionado && nos.get(selecionado)?.estado === 'executando') {
      const espera = $('inspetor').querySelector('.espera');
      if (espera) espera.textContent = `Aguardando resposta do modelo… ${segundos(performance.now() - nos.get(selecionado).dados.comeco)}`;
    }
  }

  // --- Eventos ----------------------------------------------------------------
  function evento(ev) {
    if (!ev.no && !['erro', 'resultado'].includes(ev.tipo)) return; // execuções antigas, sem rastro
    switch (ev.tipo) {
      case 'inicio':
        garantirRodada(ev.rodada);
        definir(ev.no, 'executando', { entrada: ev.entrada, comeco: performance.now(), agente: ev.agente, papel: ev.papel });
        if (seguindo()) selecionar(ev.no);
        break;
      case 'etapa':
        garantirRodada(ev.rodada);
        definir(ev.no, ev.aprovado === false ? 'reprovado' : 'concluido', { ...ev, saida: ev.conteudo });
        if (seguindo()) selecionar(ev.no);
        break;
      case 'conversa':
        definir(ev.no, 'concluido', { ...ev, saida: ev.conteudo });
        pularRestantes();
        definir('resultado', 'concluido', { saida: 'Só conversa: a equipe não foi acionada.' });
        if (seguindo()) selecionar(ev.no);
        break;
      case 'decisao':
        definir(ev.no, ev.aprovado ? 'concluido' : 'reprovado', ev);
        if (!ev.aprovado && !ev.ultima) {
          garantirRodada(ev.rodada + 1);
          nos.get(ev.no).el.closest('.linha').dataset.volta = '↩ reprovado: volta para o desenvolvimento';
        }
        if (seguindo()) selecionar(ev.no);
        break;
      case 'resultado':
        if (!ev.aprovado) definir('versao', 'pulado');
        definir('resultado', ev.aprovado ? 'concluido' : 'reprovado', ev);
        pularRestantes();
        finalizar();
        if (seguindo() || !aoVivo) selecionar('resultado');
        break;
      case 'erro':
        for (const [id, no] of nos) if (no.estado === 'executando') definir(id, 'erro', { erro: ev.mensagem });
        pularRestantes();
        finalizar();
        break;
    }
  }

  function finalizar() {
    clearInterval(relogio);
    relogio = null;
  }

  function carregar(agentesProjeto, pedido, eventos) {
    montar(agentesProjeto, pedido, false);
    eventos.forEach(evento);
    if (!eventos.some((e) => e.no)) {
      $('inspetor').replaceChildren(criar('p', 'sutil', 'Esta execução é anterior ao painel de fluxo e não tem rastro.'));
      return;
    }
    const ultimo = [...nos.keys()].reverse().find((id) => nos.get(id).estado !== 'pulado' && nos.get(id).estado !== 'aguardando');
    selecionar(nos.get('resultado').estado === 'pulado' ? ultimo : 'resultado');
  }

  function limpar() {
    finalizar();
    nos = new Map();
    selecionado = null;
    $('grafo').replaceChildren();
    $('fluxo-pedido').textContent = 'Envie um pedido ou clique em "Ver fluxo" no histórico.';
    $('inspetor').replaceChildren(criar('p', 'sutil', 'Clique em um nó para ver a entrada, a saída, as ferramentas e o código.'));
  }

  // --- Inspetor ---------------------------------------------------------------
  function selecionar(id) {
    if (!nos.has(id)) return;
    if (selecionado) nos.get(selecionado)?.el.removeAttribute('aria-current');
    selecionado = id;
    nos.get(id).el.setAttribute('aria-current', 'true');
    nos.get(id).el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    inspecionar(id);
  }

  function secao(titulo, conteudo, aberta = true) {
    const det = criar('details', 'secao');
    det.open = aberta;
    det.append(criar('summary', '', titulo), conteudo);
    return det;
  }

  function pre(texto, classe = 'pre') {
    const el = criar('pre', classe);
    el.textContent = texto;
    return el;
  }

  function inspecionar(id) {
    const { info, estado, dados } = nos.get(id);
    const painel = $('inspetor');
    const topo = criar('header', 'insp-topo');
    topo.dataset.etapa = info.etapa;
    topo.append(criar('span', 'no-icone', ICONES[info.etapa] || '•'), criar('strong', '', info.titulo),
      criar('span', 'sutil', info.sub), criar('span', `estado estado-${estado}`, ESTADOS[estado]));
    const metricas = [];
    if (dados.duracao_ms !== undefined) metricas.push(`⏱ ${segundos(dados.duracao_ms)}`);
    if (dados.tokens) metricas.push(`🔤 ${dados.tokens.entrada} → ${dados.tokens.saida} tokens`);
    if (dados.rodada) metricas.push(`rodada ${dados.rodada}`);
    const partes = [topo];
    if (metricas.length) partes.push(criar('p', 'metricas', metricas.join('  ·  ')));
    if (estado === 'executando') partes.push(criar('p', 'espera', 'Aguardando resposta do modelo…'));
    if (dados.erro) partes.push(criar('p', 'insp-erro', `⚠️ ${dados.erro}`));

    if (info.etapa === 'decisao' && dados.sintaxe) partes.push(...detalhesDecisao(dados));
    if (info.etapa === 'resultado' && dados.versao) partes.push(detalhesResultado(dados));

    if (dados.saida !== undefined && info.etapa !== 'resultado') {
      partes.push(secao(dados.formato === 'codigo' ? 'Saída (código)' : 'Saída', pre(dados.saida, dados.formato === 'codigo' ? 'pre codigo' : 'pre')));
    }
    if (dados.formato === 'codigo') partes.push(secao('Alterações no código', blocoDiff(dados.codigo_anterior || '', dados.saida)));
    if (dados.ferramentas?.length) partes.push(secao(`Ferramentas (${dados.ferramentas.length})`, listaFerramentas(dados.ferramentas)));
    if (dados.entrada) partes.push(secao('Entrada (prompt enviado ao agente)', pre(dados.entrada), estado === 'executando'));
    if (info.etapa === 'resultado' && dados.codigo) partes.push(secao('Código final', pre(dados.codigo, 'pre codigo'), false));
    painel.replaceChildren(...partes);
  }

  function detalhesDecisao(d) {
    const lista = criar('ul', 'votos');
    lista.appendChild(criar('li', d.sintaxe === 'SINTAXE_OK' ? 'ok' : 'falha', `${d.sintaxe === 'SINTAXE_OK' ? '✓' : '✗'} ast: ${d.sintaxe}`));
    for (const v of d.votos) lista.appendChild(criar('li', v.aprovado ? 'ok' : 'falha', `${v.aprovado ? '✓' : '✗'} ${v.agente}: ${v.aprovado ? 'APROVADO' : 'REPROVADO'}`));
    const conclusao = d.aprovado ? 'Aprovado: segue para o versionamento.'
      : d.ultima ? 'Reprovado na última rodada: a versão não muda.' : 'Reprovado: o código volta para o desenvolvimento com as revisões.';
    return [lista, criar('p', d.aprovado ? 'ok' : 'falha', conclusao)];
  }

  function detalhesResultado(d) {
    const caixa = criar('div', 'resumo');
    caixa.appendChild(criar('p', d.aprovado ? 'ok' : 'falha', d.aprovado
      ? `✔ Aprovado em ${d.rodadas} rodada(s): v${d.versao_anterior || '?'} → v${d.versao}`
      : `✘ Reprovado após ${d.rodadas} rodada(s); versão mantida em v${d.versao}`));
    if (d.commit) caixa.appendChild(pre(d.commit));
    return caixa;
  }

  function listaFerramentas(ferramentas) {
    const lista = criar('ol', 'ferramentas');
    for (const f of ferramentas) {
      const item = criar('li');
      item.append(criar('code', '', `${f.nome}(${f.argumentos})`), criar('span', 'seta', '→'),
        pre(f.resultado ?? `(${f.status})`, 'pre curto'));
      lista.appendChild(item);
    }
    return lista;
  }

  // --- Diff de linhas (LCS) ---------------------------------------------------
  function diff(antes, depois) {
    const a = antes ? antes.split('\n') : [];
    const b = depois ? depois.split('\n') : [];
    if (a.length * b.length > 600000) return null; // grande demais para comparar no navegador
    const t = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1));
    for (let i = a.length - 1; i >= 0; i--) {
      for (let j = b.length - 1; j >= 0; j--) {
        t[i][j] = a[i] === b[j] ? t[i + 1][j + 1] + 1 : Math.max(t[i + 1][j], t[i][j + 1]);
      }
    }
    const linhas = [];
    let i = 0, j = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { linhas.push([' ', a[i]]); i++; j++; }
      else if (t[i + 1][j] >= t[i][j + 1]) linhas.push(['-', a[i++]]);
      else linhas.push(['+', b[j++]]);
    }
    while (i < a.length) linhas.push(['-', a[i++]]);
    while (j < b.length) linhas.push(['+', b[j++]]);
    return linhas;
  }

  function blocoDiff(antes, depois) {
    const linhas = diff(antes, depois);
    if (!linhas) return criar('p', 'sutil', 'Código grande demais para comparar aqui; veja a saída completa.');
    const add = linhas.filter((l) => l[0] === '+').length;
    const rem = linhas.filter((l) => l[0] === '-').length;
    const caixa = criar('div', 'diff');
    caixa.appendChild(criar('p', 'diff-resumo', !antes ? `Código novo: ${add} linhas`
      : add || rem ? `+${add} −${rem} linhas` : 'Nenhuma alteração.'));
    const codigo = criar('pre', 'pre codigo');
    const CONTEXTO = 2;
    const mudou = linhas.map((l) => l[0] !== ' ');
    const perto = (k) => mudou.slice(Math.max(0, k - CONTEXTO), k + CONTEXTO + 1).some(Boolean);
    let omitidas = 0;
    const descarregar = () => {
      if (omitidas) codigo.appendChild(criar('span', 'diff-omitido', `… ${omitidas} linhas iguais\n`));
      omitidas = 0;
    };
    linhas.forEach(([sinal, texto], k) => {
      if (antes && sinal === ' ' && !perto(k)) { omitidas++; return; }
      descarregar();
      codigo.appendChild(criar('span', sinal === '+' ? 'diff-add' : sinal === '-' ? 'diff-rem' : '', `${sinal} ${texto}\n`));
    });
    descarregar();
    caixa.appendChild(codigo);
    return caixa;
  }

  return { montar, evento, carregar, limpar };
})();
