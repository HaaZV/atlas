"""
atlas/ui/cards.py
Renderização de cards de análise, bilhetes e helpers visuais.
"""

from __future__ import annotations
import streamlit as st
from atlas.config import (
    Jogo, HIERARQUIA_LIGAS,
    PROB_MINIMA_APROVACAO, RANGE_BILHETE_MIN, RANGE_BILHETE_MAX,
)
from atlas.parsers import parsear_desfalques_superbet
from atlas.utils import gerar_bilhetes

def cor_score(score: int) -> str:
    if score >= 85: return "#6ee7b7"
    if score >= 70: return "#fbbf24"
    return "#f87171"

def cor_status(status: str) -> str:
    mapa = {
        "APROVADO": "#6ee7b7",
        "ATENÇÃO": "#fbbf24",
        "REJEITADO": "#f87171",
        "DADOS INSUFICIENTES": "#a5b4fc",
        "PENDENTE": "#94a3b8"
    }
    return mapa.get(status, "#94a3b8")

def badge_status(status: str) -> str:
    cls = {
        "APROVADO": "badge-aprovado",
        "ATENÇÃO": "badge-atencao",
        "REJEITADO": "badge-rejeitado",
        "DADOS INSUFICIENTES": "badge-dados-insuf",
    }.get(status, "badge-dados-insuf")
    return f'<span class="{cls}">{status}</span>'

def icone_alerta(tipo: str) -> str:
    return {"critico": "alerta-critico", "aviso": "alerta-aviso",
            "ok": "alerta-ok", "info": "alerta-info"}.get(tipo, "alerta-info")

def renderizar_barra(valor: int, cor: str):
    st.markdown(f"""
    <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:{valor}%;background:{cor};"></div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────
#  SIDEBAR — CONFIGURAÇÃO DO JOGO
# ──────────────────────────────────────────
def renderizar_card(jogo: Jogo, resultado: dict, idx: int):
    status = resultado["status"]
    score = resultado["score"]
    alertas = resultado["alertas"]
    motivos = resultado["motivos_rejeicao"]
    dados_insuf = resultado["dados_insuficientes"]
    cobertura = resultado["cobertura"]

    cor = cor_score(score)
    tier = HIERARQUIA_LIGAS.get(jogo.liga, {}).get("tier", "?")
    taxa_liga = HIERARQUIA_LIGAS.get(jogo.liga, {}).get("taxa", 0)

    with st.container():
        st.markdown(f"""
        <div class="jogo-card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div>
                <div style="font-size:17px;font-weight:600;color:#f1f5f9">
                    {jogo.time_casa} <span style="color:#475569;font-size:13px">vs</span> {jogo.time_fora}
                </div>
                <div style="font-size:12px;color:#475569;margin-top:2px;font-family:'JetBrains Mono',monospace">
                    {jogo.liga} &nbsp;·&nbsp; Tier {tier} ({taxa_liga*100:.0f}%) &nbsp;·&nbsp;
                    Odd <strong style="color:#e2e8f0">{jogo.odd}</strong> &nbsp;·&nbsp;
                    {jogo.tipo_competicao}
                </div>
            </div>
            <div style="text-align:right">
                {badge_status(status)}
                <div style="margin-top:6px">
                    <span class="score-num" style="color:{cor}">{score}</span>
                    <div class="score-label">SCORE ATLAS</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Barra de score
        renderizar_barra(score, cor)

        # Cobertura de dados — com alerta visual quando < 75%
        _cob_cor = "#f87171" if cobertura < 75 else ("#fbbf24" if cobertura < 85 else "#3b82f6")
        _cob_alerta = ""
        if cobertura < 75:
            _cob_alerta = (
                f'<div style="background:rgba(248,113,113,.10);border-left:3px solid #f87171;'
                f'padding:6px 10px;border-radius:0 6px 6px 0;margin-bottom:6px;'
                f'font-size:11px;color:#f87171;font-weight:700">'
                f'⚠️ COBERTURA BAIXA ({cobertura}%) — score pode estar inflado por dados insuficientes'
                f'</div>'
            )
        st.markdown(f"""
        {_cob_alerta}
        <div style="display:flex;align-items:center;gap:8px;margin-top:6px;margin-bottom:10px">
            <span style="font-size:10px;color:#475569;letter-spacing:1px;text-transform:uppercase">
                Cobertura de dados
            </span>
            <div class="progress-bar-bg" style="flex:1">
                <div class="progress-bar-fill" style="width:{cobertura}%;background:{_cob_cor}"></div>
            </div>
            <span style="font-size:11px;color:{_cob_cor};font-family:'JetBrains Mono',monospace">
                {cobertura}%
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # D12 — linha compacta de forma recente (visível sem abrir o card)
    _uj = jogo.ultimos_jogos
    if _uj.n_jogos_casa > 0 or _uj.n_jogos_fora > 0:
        _partes = []
        if _uj.n_jogos_casa > 0:
            _o15c = f"{_uj.over15_casa*100:.0f}%" if _uj.over15_casa is not None else "—"
            _mpc  = f"{_uj.media_gols_pro_casa:.1f}" if _uj.media_gols_pro_casa is not None else "—"
            _resultados_c = "".join(
                f"<span style='color:{'#6ee7b7' if j.resultado=='V' else '#fbbf24' if j.resultado=='E' else '#f87171'}'>{j.resultado}</span>"
                for j in _uj.jogos_casa[-5:]
            )
            _partes.append(
                f"<span style='color:#94a3b8'>{jogo.time_casa}</span> "
                f"{_resultados_c} "
                f"<span style='color:#475569'>· Over1.5 {_o15c} · {_mpc}m</span>"
            )
        if _uj.n_jogos_fora > 0:
            _o15f = f"{_uj.over15_fora*100:.0f}%" if _uj.over15_fora is not None else "—"
            _mpf  = f"{_uj.media_gols_pro_fora:.1f}" if _uj.media_gols_pro_fora is not None else "—"
            _resultados_f = "".join(
                f"<span style='color:{'#6ee7b7' if j.resultado=='V' else '#fbbf24' if j.resultado=='E' else '#f87171'}'>{j.resultado}</span>"
                for j in _uj.jogos_fora[-5:]
            )
            _partes.append(
                f"<span style='color:#94a3b8'>{jogo.time_fora}</span> "
                f"{_resultados_f} "
                f"<span style='color:#475569'>· Over1.5 {_o15f} · {_mpf}m</span>"
            )
        st.markdown(
            "<div style='font-size:10px;font-family:monospace;color:#475569;"
            "padding:4px 0 6px 0;display:flex;gap:24px;flex-wrap:wrap'>"
            "📅 " + " &nbsp;|&nbsp; ".join(_partes) + "</div>",
            unsafe_allow_html=True
        )

    # D16 — Radiografia do score (bandeja, colapsável)
    _fases = resultado.get("detalhes_fases", {})
    _fases_exibir = [
        ("base_liga", "Base Liga"),
        ("fase5",     "Over Indiv."),
        ("fase6",     "H2H"),
        ("fase7",     "Superbet"),
        ("fase8",     "Contexto"),
        ("fase8b",    "Forma"),
        ("fase2",     "Odd"),
        ("fase3",     "Calendário"),
        ("fase4",     "Rebaixamento"),
    ]
    _itens_validos = []
    for _key, _label in _fases_exibir:
        _entry = _fases.get(_key)
        if isinstance(_entry, tuple) and _entry[1] != 0:
            _itens_validos.append((_label, _entry[1]))

    if _itens_validos:
        # D1 — Transparência obrigatória: score < 75 abre radiografia automaticamente
        _radio_expanded = score < 75
        with st.expander("📊 Radiografia do score", expanded=_radio_expanded):
            _max_abs = max(abs(v) for _, v in _itens_validos) or 1
            for _label, _val in _itens_validos:
                _cor   = "#6ee7b7" if _val > 0 else "#f87171"
                _sinal = "+" if _val > 0 else ""
                _pct   = min(100, int(abs(_val) / _max_abs * 100))
                _dir   = "right" if _val > 0 else "left"
                # Barra cresce para direita (positivo) ou esquerda (negativo)
                _bar_style = (
                    f"height:6px;border-radius:3px;background:{_cor};"
                    f"width:{_pct}%;margin-left:{'0' if _val>0 else 'auto'}"
                )
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:8px;"
                    f"padding:3px 0;border-bottom:1px solid #0f172a'>"
                    f"<div style='width:80px;font-size:10px;color:#475569;"
                    f"font-family:monospace;flex-shrink:0'>{_label}</div>"
                    f"<div style='flex:1;background:#0f172a;border-radius:3px;height:6px'>"
                    f"<div style='{_bar_style}'></div></div>"
                    f"<div style='width:36px;text-align:right;font-size:10px;"
                    f"font-family:monospace;color:{_cor};flex-shrink:0'>"
                    f"{_sinal}{_val:.1f}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

    # Detalhes expansíveis
    with st.expander(f"🔍 Ver análise completa — {jogo.time_casa} × {jogo.time_fora}"):

        # Métricas rápidas — text_input readonly com help= (padrão dos outros campos)
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            v = jogo.betano.over15_casa_pct
            st.text_input(
                "Over 1.5 Casa",
                value=f"{v*100:.0f}%" if v is not None else "—",
                disabled=True,
                key=f"_m_o15c_{idx}",
                help=(
                    "% de jogos do mandante em casa com Over 1.5 na temporada.\n\n"
                    "Fonte: Betano → Estatísticas → Over/Under → 1.5\n\n"
                    "✅ ≥ 70%\n⚠️ 50–69%\n❌ < 50% — filtro crítico V6.9"
                )
            )
        with mc2:
            v = jogo.betano.over15_fora_pct
            st.text_input(
                "Over 1.5 Fora",
                value=f"{v*100:.0f}%" if v is not None else "—",
                disabled=True,
                key=f"_m_o15f_{idx}",
                help=(
                    "% de jogos do visitante fora de casa com Over 1.5 na temporada.\n\n"
                    "Fonte: Betano → Estatísticas → Over/Under → 1.5\n\n"
                    "✅ ≥ 70%\n⚠️ 50–69%\n❌ < 50% — penaliza score"
                )
            )
        with mc3:
            v = jogo.h2h.media_gols
            st.text_input(
                "H2H Média Gols",
                value=f"{v:.2f}" if v is not None else "—",
                disabled=True,
                key=f"_m_h2h_{idx}",
                help=(
                    "Média de gols por jogo nos confrontos diretos.\n\n"
                    "Fonte: H2H → Confronto direto\n\n"
                    "✅ ≥ 2.5\n⚠️ 2.0–2.4\n❌ < 2.0 — histórico defensivo"
                )
            )
        with mc4:
            v  = jogo.superbet.xg_casa
            vf = jogo.superbet.xg_fora
            xg_total = (v or 0) + (vf or 0)
            st.text_input(
                "xG Combinado",
                value=f"{xg_total:.2f}" if xg_total > 0 else "—",
                disabled=True,
                key=f"_m_xg_{idx}",
                help=(
                    "Soma dos Gols Esperados (xG) casa + fora.\n\n"
                    "Fonte: Superbet → Estatísticas → Gols esperados (xG)\n\n"
                    "✅ ≥ 3.0\n⚠️ 2.0–2.9\n❌ < 2.0 — jogo travado esperado"
                )
            )

        st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # H2H resultados recentes — D11: movido para antes dos alertas
        if jogo.h2h.resultados_recentes:
            _h2h_meta = []
            if jogo.h2h.total_jogos:   _h2h_meta.append(f"{jogo.h2h.total_jogos} jogos")
            if jogo.h2h.media_gols:    _h2h_meta.append(f"média {jogo.h2h.media_gols:.2f}g")
            if jogo.h2h.over15_pct:    _h2h_meta.append(f"Over1.5 {jogo.h2h.over15_pct*100:.0f}%")
            if jogo.h2h.btts_pct:      _h2h_meta.append(f"BTTS {jogo.h2h.btts_pct*100:.0f}%")
            _meta_str = " · ".join(_h2h_meta)
            st.markdown(
                f"**H2H recente**"
                + (f"<span style='font-size:10px;color:#475569;margin-left:8px'>{_meta_str}</span>" if _meta_str else ""),
                unsafe_allow_html=True
            )
            cols = st.columns(min(len(jogo.h2h.resultados_recentes), 10))
            for i, r in enumerate(jogo.h2h.resultados_recentes):
                with cols[i]:
                    partes = r.split("-")
                    total = int(partes[0]) + int(partes[1]) if len(partes) == 2 else 0
                    cor_res = "#6ee7b7" if total >= 2 else "#f87171"
                    st.markdown(f"""
                    <div style="text-align:center;background:#0a0a0f;border:1px solid #1e1e2e;
                         border-radius:6px;padding:8px 4px">
                        <div style="font-family:'JetBrains Mono';font-size:16px;font-weight:600;color:{cor_res}">{r}</div>
                        <div style="font-size:9px;color:#475569">{'✅' if total >= 2 else '❌'} Over 1.5</div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)

        # Alertas
        col_al, col_rej = st.columns([2, 1])

        with col_al:
            st.markdown("**Alertas por fase:**")
            for tipo, msg in alertas:
                cls = icone_alerta(tipo)
                st.markdown(f'<div class="{cls}">{msg}</div>', unsafe_allow_html=True)

        with col_rej:
            if motivos:
                st.markdown("**Motivos de rejeição:**")
                for m in motivos:
                    st.markdown(f'<div class="alerta-critico">🚫 {m}</div>', unsafe_allow_html=True)

            if dados_insuf:
                st.markdown("**Dados ausentes:**")
                for d in dados_insuf:
                    st.markdown(f'<span class="motivo-tag">📭 {d}</span>', unsafe_allow_html=True)

        # Desfalques
        if jogo.desfalques_texto_casa or jogo.desfalques_texto_fora:
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            da, db = st.columns(2)
            if jogo.desfalques_texto_casa:
                with da:
                    st.markdown(f"**🏥 {jogo.time_casa}**")
                    st.markdown(f'<div class="alerta-aviso" style="font-size:12px">{jogo.desfalques_texto_casa}</div>',
                                unsafe_allow_html=True)
            if jogo.desfalques_texto_fora:
                with db:
                    st.markdown(f"**🏥 {jogo.time_fora}**")
                    st.markdown(f'<div class="alerta-aviso" style="font-size:12px">{jogo.desfalques_texto_fora}</div>',
                                unsafe_allow_html=True)

        # D7 — Desfalques Superbet (complementar ao Google IA)
        _dsb_casa = jogo.desfalques_superbet_raw
        if _dsb_casa:
            _dp_card = parsear_desfalques_superbet(_dsb_casa, jogo.time_casa, jogo.time_fora)
            _nc_c, _ni_c, _nomes_c, _nomes_ic = _dp_card["casa"]
            _nc_f, _ni_f, _nomes_f, _nomes_if = _dp_card["fora"]
            if _nc_c + _ni_c + _nc_f + _ni_f > 0:
                st.markdown("<hr class='sep'>", unsafe_allow_html=True)
                st.markdown("**🏥 Desfalques — Superbet**", unsafe_allow_html=False)
                _dsa, _dsb = st.columns(2)
                with _dsa:
                    if _nc_c + _ni_c > 0:
                        _linhas_c = [f"🔴 {n}" for n in _nomes_c] + [f"🟡 {n}" for n in _nomes_ic]
                        st.markdown(
                            f"<div style='font-size:11px;font-weight:600;color:#94a3b8;"
                            f"margin-bottom:4px'>{jogo.time_casa}</div>"
                            + "".join(f"<div style='font-size:11px;color:#f1f5f9'>{l}</div>" for l in _linhas_c),
                            unsafe_allow_html=True
                        )
                with _dsb:
                    if _nc_f + _ni_f > 0:
                        _linhas_f = [f"🔴 {n}" for n in _nomes_f] + [f"🟡 {n}" for n in _nomes_if]
                        st.markdown(
                            f"<div style='font-size:11px;font-weight:600;color:#94a3b8;"
                            f"margin-bottom:4px'>{jogo.time_fora}</div>"
                            + "".join(f"<div style='font-size:11px;color:#f1f5f9'>{l}</div>" for l in _linhas_f),
                            unsafe_allow_html=True
                        )

        # D12 — Últimos jogos Superbet
        _uj = jogo.ultimos_jogos
        if _uj.n_jogos_casa > 0 or _uj.n_jogos_fora > 0:
            st.markdown("<hr class='sep'>", unsafe_allow_html=True)
            st.markdown("**📅 Últimos Jogos — Superbet**")
            _uja, _ujb = st.columns(2)

            def _render_ultimos(col, time_nome, jogos_list, over15, media_pro, media_contra, n):
                with col:
                    if not jogos_list:
                        return
                    # Métricas resumo
                    _over_str = f"{over15*100:.0f}%" if over15 is not None else "—"
                    _pro_str  = f"{media_pro:.1f}" if media_pro is not None else "—"
                    _con_str  = f"{media_contra:.1f}" if media_contra is not None else "—"
                    st.markdown(
                        f"<div style='font-size:11px;font-weight:600;color:#94a3b8;"
                        f"margin-bottom:6px'>{time_nome} "
                        f"<span style='color:#475569;font-weight:400'>({n} jogos)</span></div>"
                        f"<div style='font-size:10px;color:#7dd3fc;margin-bottom:6px;"
                        f"font-family:monospace'>Over 1.5: {_over_str} · Marcados: {_pro_str} · Sofridos: {_con_str}</div>",
                        unsafe_allow_html=True
                    )
                    # Tabela de jogos
                    for j in jogos_list:
                        _total = (j.gols_pro or 0) + (j.gols_contra or 0)
                        _over_icon = "✅" if _total > 1 else "❌"
                        _res_color = {"V": "#6ee7b7", "E": "#fbbf24", "D": "#f87171"}.get(j.resultado, "#94a3b8")
                        _loc = "🏠" if j.em_casa else "✈️"
                        _placar = f"{j.gols_pro}-{j.gols_contra}" if j.gols_pro is not None else "?-?"
                        st.markdown(
                            f"<div style='font-size:10px;font-family:monospace;padding:2px 0;"
                            f"border-bottom:1px solid #1e2640'>"
                            f"{_over_icon} {_loc} <span style='color:#94a3b8'>{j.data}</span> "
                            f"<span style='color:#e2e8f0'>{j.adversario[:14]}</span> "
                            f"<strong>{_placar}</strong> "
                            f"<span style='color:{_res_color};font-weight:600'>{j.resultado}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

            _render_ultimos(_uja, jogo.time_casa, _uj.jogos_casa,
                            _uj.over15_casa, _uj.media_gols_pro_casa,
                            _uj.media_gols_contra_casa, _uj.n_jogos_casa)
            _render_ultimos(_ujb, jogo.time_fora, _uj.jogos_fora,
                            _uj.over15_fora, _uj.media_gols_pro_fora,
                            _uj.media_gols_contra_fora, _uj.n_jogos_fora)

        # Banner decisão final
        st.markdown("""
        <div class="decisao-final-banner">
            🤖 <strong>DECISÃO FINAL:</strong> Este score é orientativo.
            Cole estes dados para o Claude validar e tomar a decisão definitiva de aprovação.
        </div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────
#  SEÇÃO DE BILHETES
# ──────────────────────────────────────────
def renderizar_bilhetes(jogos_com_resultado: list):
    aprovados = [
        {"nome": f"{j.time_casa} × {j.time_fora}", "odd": j.odd, "score": r["score"],
         "liga": j.liga, "status": r["status"]}
        for j, r in jogos_com_resultado
        if r["status"] in ("APROVADO", "ATENÇÃO") and r["score"] >= PROB_MINIMA_APROVACAO
    ]

    st.markdown("---")
    st.markdown('<div class="atlas-title">🎯 Bilhetes Sugeridos</div>', unsafe_allow_html=True)
    st.markdown('<div class="atlas-sub" style="margin-bottom:16px">range alvo: 1.50 – 1.60 | decisão final: claude</div>',
                unsafe_allow_html=True)

    if len(aprovados) < 2:
        st.markdown("""
        <div class="alerta-info">
            🔵 Menos de 2 jogos aprovados — não é possível montar bilhetes dentro do range.
            Forneça dados completos ou aguarde análise do Claude.
        </div>
        """, unsafe_allow_html=True)
        return

    bilhetes = gerar_bilhetes(aprovados)

    if not bilhetes:
        # Mostrar combinações mais próximas mesmo fora do range
        st.markdown("""
        <div class="alerta-aviso">
            ⚠️ Nenhuma combinação atingiu o range 1.50–1.60.
            Abaixo estão as melhores combinações disponíveis — Claude avalia viabilidade.
        </div>
        """, unsafe_allow_html=True)

        combos_extras = []
        for n in range(2, min(4, len(aprovados) + 1)):
            for combo in combinations(aprovados, n):
                odd_c = round(np.prod([j["odd"] for j in combo]), 3)
                combos_extras.append({"jogos": combo, "odd": odd_c,
                                      "score_medio": round(np.mean([j["score"] for j in combo]), 1),
                                      "n_jogos": n})
        combos_extras.sort(key=lambda x: abs(x["odd"] - 1.55))
        bilhetes = combos_extras[:3]

    nomes = ["🥇 OURO", "💎 DIAMANTE", "🥉 PLATINA"]
    stakes = ["60%", "25%", "15%"]
    classes = ["bilhete-ouro", "bilhete-diamante", "bilhete-platina"]

    bordas = ["#d97706", "#3b82f6", "#6366f1"]  # ouro, diamante, platina
    cols = st.columns(min(3, len(bilhetes)))
    for i, (col, bilhete) in enumerate(zip(cols, bilhetes[:3])):
        with col:
            nome       = nomes[i]  if i < len(nomes)   else f"BILHETE {i+1}"
            stake      = stakes[i] if i < len(stakes)  else "—"
            borda      = bordas[i] if i < len(bordas)  else "#3b82f6"
            dentro     = RANGE_BILHETE_MIN <= bilhete["odd"] <= RANGE_BILHETE_MAX
            cor_odd    = "#6ee7b7" if dentro else "#fbbf24"
            label_range = "✅ Dentro do range" if dentro else "⚠️ Fora do range"

            # Card container (HTML seguro, sem variáveis dinâmicas dentro de tags)
            st.markdown(
                f'''<div style="background:linear-gradient(135deg,#111827,#0d1226);
                    border:1.5px solid {borda};border-radius:12px;padding:16px 18px;
                    min-height:200px">''',
                unsafe_allow_html=True
            )

            # Cabeçalho: nome + stake
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{nome}**")
            c2.markdown(
                f'''<div style="text-align:right;font-size:11px;color:#475569;
                    font-family:monospace">Stake {stake}</div>''',
                unsafe_allow_html=True
            )

            # Jogos do bilhete
            for jg in bilhete["jogos"]:
                st.markdown(
                    f'''<div style="margin:5px 0;padding:7px 10px;background:#0a0e1a;
                        border-radius:6px;border-left:2px solid #3b82f6">
                        <div style="font-size:13px;font-weight:600;color:#e2e8f0">
                            {jg["nome"]}</div>
                        <div style="font-size:10px;color:#475569;font-family:monospace">
                            {jg["liga"]} &nbsp;·&nbsp; Odd {jg["odd"]} &nbsp;·&nbsp; Score {jg["score"]}
                        </div></div>''',
                    unsafe_allow_html=True
                )

            # Odd + score médio
            ca, cb = st.columns(2)
            ca.markdown(
                f'''<div style="font-family:monospace;font-size:26px;font-weight:700;
                    color:{cor_odd};margin-top:8px">{bilhete["odd"]}</div>
                <div style="font-size:9px;color:#475569;letter-spacing:1px">ODD COMBINADA</div>''',
                unsafe_allow_html=True
            )
            cb.markdown(
                f'''<div style="font-family:monospace;font-size:20px;color:#94a3b8;
                    margin-top:8px;text-align:right">{bilhete["score_medio"]}</div>
                <div style="font-size:9px;color:#475569;letter-spacing:1px;text-align:right">
                    SCORE MÉDIO</div>''',
                unsafe_allow_html=True
            )

            cor_range = "#6ee7b7" if dentro else "#fbbf24"
            st.markdown(
                f'''<div style="margin-top:8px;font-size:10px;color:{cor_range};text-align:center">
                    {label_range}</div></div>''',
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════
#  GERADOR DE RELATÓRIO PARA CLAUDE
