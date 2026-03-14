"""
atlas/ui/inserir_jogo.py
Formulário de inserção de um jogo (ex-sidebar_jogo).
Renderiza na área principal dentro de uma aba.
"""

from __future__ import annotations
import os
import re
import streamlit as st
from typing import Optional

from atlas.config import (
    Jogo, DadosBetano, DadosSuperbet, DadosH2H, DadosContexto,
    FormaRecente, UltimosJogosSuperbet, HIERARQUIA_LIGAS,
    TIPO_COMPETICAO_LIGA, BLACKLIST_TIMES_VISITANTE, BLACKLIST_LIGAS,
)
from atlas.parsers import (
    parsear_betano, parsear_superbet, parsear_h2h,
    parsear_desfalques, parsear_forma_recente,
    parsear_resposta_google_ia, parsear_desfalques_superbet,
    parsear_ultimos_jogos_superbet,
    gerar_prompt_google, gerar_url_google,
    InfoDesfalqueIA,
)
from atlas.motor import detectar_derby

def inserir_jogo(idx: int, import_data: dict = None) -> Optional[Jogo]:

    # Defaults: vêm da importação ou ficam em branco
    _d = import_data or {}
    _casa_default = _d.get("time_casa", "")
    _fora_default = _d.get("time_fora", "")
    _odd_default  = float(_d.get("odd", 1.25))

    # Badge de liga detectada automaticamente
    if _d.get("liga_detectada"):
        st.markdown(
            f"""<div style="background:#052e16;border-left:3px solid #16a34a;
                padding:4px 8px;font-size:10px;color:#86efac;
                border-radius:0 4px 4px 0;margin-bottom:4px">
                🔍 Liga detectada: <strong>{_d.get("liga","")}</strong>
                &nbsp;·&nbsp; {_d.get("n_times",18)} times
            </div>""",
            unsafe_allow_html=True
        )
    elif _d:
        st.markdown(
            """<div style="background:#431407;border-left:3px solid #c2410c;
                padding:4px 8px;font-size:10px;color:#fb923c;
                border-radius:0 4px 4px 0;margin-bottom:4px">
                ⚠️ Liga não detectada — selecione abaixo
            </div>""",
            unsafe_allow_html=True
        )

    # Fix — não sobrescrever session_state com value= quando já há dados.
    # value= em widget com key= reseta o estado a cada rerun, apagando
    # o que o usuário digitou ao navegar entre slots.
    # Só usar value= (via default) se o slot ainda não tem dados no session_state.
    if _casa_default and not st.session_state.get(f"casa_{idx}"):
        st.session_state[f"casa_{idx}"] = _casa_default
    if _fora_default and not st.session_state.get(f"fora_{idx}"):
        st.session_state[f"fora_{idx}"] = _fora_default

    col1, col2 = st.columns(2)
    time_casa = col1.text_input("Casa", key=f"casa_{idx}",
                                 placeholder="Ex: Sporting")
    time_fora = col2.text_input("Fora", key=f"fora_{idx}",
                                 placeholder="Ex: Estoril")

    if not time_casa or not time_fora:
        return None

    # Liga: lista organizada por tipo (ligas / copas nacionais / copas internacionais)
    _ligas_apenas   = sorted([l for l, t in TIPO_COMPETICAO_LIGA.items()
                               if t == "liga" and l in HIERARQUIA_LIGAS])
    _copas_nac      = sorted([l for l, t in TIPO_COMPETICAO_LIGA.items()
                               if t == "copa" and l in HIERARQUIA_LIGAS])
    _copas_inter    = sorted([l for l, t in TIPO_COMPETICAO_LIGA.items()
                               if t == "copa_inter" and l in HIERARQUIA_LIGAS])
    _ligas_list = (
        _ligas_apenas +
        ["── Copas Nacionais ──"] + _copas_nac +
        ["── Copas Internacionais ──"] + _copas_inter +
        ["Outra"]
    )

    _liga_import = _d.get("liga", "")
    # BUG FIX — sincronizar liga do session_state quando importação muda.
    # Se importação traz uma liga diferente da que está no session_state,
    # atualizar o estado ANTES de renderizar o selectbox.
    _liga_ss_atual = st.session_state.get(f"liga_{idx}", "")
    if _liga_import and _liga_import in _ligas_list and _liga_import != _liga_ss_atual:
        st.session_state[f"liga_{idx}"] = _liga_import
    elif not st.session_state.get(f"liga_{idx}") or st.session_state.get(f"liga_{idx}") not in _ligas_list:
        # Valor inválido no estado — resetar para Liga Portugal (default)
        _default_liga = "Liga Portugal" if "Liga Portugal" in _ligas_list else _ligas_list[0]
        st.session_state[f"liga_{idx}"] = _default_liga

    liga = st.selectbox(
        "Liga / Competição", key=f"liga_{idx}",
        options=_ligas_list,
    )

    # Liga válida — separadores não são ligas reais
    if liga.startswith("──"):
        liga = "Outra"

    # Auto-detectar tipo de competição com base na liga selecionada
    # BUG FIX: o selectbox com key persiste no session_state entre jogos.
    # Quando a liga muda, forçar atualização do session_state ANTES de renderizar
    # o widget — caso contrário o Streamlit ignora o index= e usa o valor antigo.
    _tipo_auto = TIPO_COMPETICAO_LIGA.get(liga, "liga")
    # CL_Volta fundido em copa_inter + jogo_volta [Item 1+8 V7.2]
    _tipo_labels = ["Campeonato", "Copa Nacional", "Copa Internacional"]
    _tipo_valores = ["Campeonato", "Copa",          "copa_inter"]
    _tipo_default_label = {
        "liga":       "Campeonato",
        "copa":       "Copa Nacional",
        "copa_inter": "Copa Internacional",
    }.get(_tipo_auto, "Campeonato")

    # Chave de rastreamento: liga que estava ativa na última renderização deste slot
    _liga_anterior_key = f"_liga_anterior_{idx}"
    _liga_anterior = st.session_state.get(_liga_anterior_key, "")

    # Se a liga mudou desde a última renderização, sincronizar tipo no session_state
    if liga != _liga_anterior:
        st.session_state[f"tipo_{idx}"] = _tipo_default_label
        st.session_state[_liga_anterior_key] = liga

    # Garantir que o valor no session_state é um label válido
    _tipo_atual_ss = st.session_state.get(f"tipo_{idx}", _tipo_default_label)
    if _tipo_atual_ss not in _tipo_labels:
        st.session_state[f"tipo_{idx}"] = _tipo_default_label

    # Fix — odd: só inicializar se slot ainda não tem valor no session_state
    if f"odd_{idx}" not in st.session_state:
        st.session_state[f"odd_{idx}"] = _odd_default

    col_odd, col_tipo = st.columns(2)
    odd = col_odd.number_input("Odd Over 1.5", min_value=1.01, max_value=5.0,
                                step=0.01, key=f"odd_{idx}")
    _tipo_label_sel = col_tipo.selectbox("Tipo", _tipo_labels,
                                          key=f"tipo_{idx}")
    tipo_comp = _tipo_valores[_tipo_labels.index(_tipo_label_sel)]

    # Detecção automática de derby (antes do expander para mostrar aviso)
    derby_auto, derby_of_auto = detectar_derby(time_casa, time_fora)

    # Contexto rápido
    with st.expander("⚙️ Contexto", expanded=False):

        if derby_auto:
            st.markdown(
                f'''<div style="background:#451a03;border:1px solid #d97706;border-radius:6px;
                padding:7px 10px;font-size:11px;color:#fbbf24;margin-bottom:8px">
                🔶 Derby detectado: <strong>{time_casa} × {time_fora}</strong>
                </div>''', unsafe_allow_html=True)

        tem_cl = st.checkbox("CL/EL nos próx. 3 dias", key=f"cl_{idx}")
        tem_el = st.checkbox("EL nos próx. 4 dias", key=f"el_{idx}")
        agregado_cl = st.text_input("Agregado CL (ex: 0-2)", key=f"ag_{idx}", placeholder="0-2")

        # Item 1+8 V7.2 — Fase eliminatória (visível apenas em copa_inter)
        _fase_elim = None
        _jogo_volta = False
        _ag_ida = None
        if tipo_comp == "copa_inter":
            st.markdown(
                """<div style="font-size:10px;color:#6366f1;letter-spacing:1px;
                margin-top:8px;margin-bottom:4px">🏆 COPA INTERNACIONAL — FASE</div>""",
                unsafe_allow_html=True
            )
            _FASES_LABELS  = ["Grupos", "Oitavas", "Quartas", "Semis", "Final"]
            _FASES_VALORES = ["grupos", "oitavas", "quartas", "semis", "final"]

            # BUG FIX — mesmo padrão do tipo_competicao:
            # session_state pode ter valor antigo de outro jogo/sessão.
            # Garantir que o valor atual é um label válido.
            _fase_ss = st.session_state.get(f"fase_elim_{idx}", "Grupos")
            # Normalizar: se vier valor interno ("grupos"), converter para label ("Grupos")
            if _fase_ss in _FASES_VALORES:
                _fase_ss = _FASES_LABELS[_FASES_VALORES.index(_fase_ss)]
            if _fase_ss not in _FASES_LABELS:
                _fase_ss = "Grupos"
            st.session_state[f"fase_elim_{idx}"] = _fase_ss

            _fase_label_sel = st.selectbox(
                "Fase", _FASES_LABELS, key=f"fase_elim_{idx}",
                help="Grupos = tratar como liga · Oitavas→Final = penalidade crescente"
            )
            # selectbox armazena o label — converter para valor interno com fallback seguro
            _fase_elim = _FASES_VALORES[_FASES_LABELS.index(_fase_label_sel)] if _fase_label_sel in _FASES_LABELS else "grupos"

            if _fase_elim != "grupos":
                _jogo_volta = st.checkbox(
                    "Jogo de volta", key=f"jogo_volta_{idx}",
                    help="Marcar quando este é o segundo jogo do confronto"
                )
                if _jogo_volta:
                    _ag_ida = st.text_input(
                        "Placar da ida (casa × fora)",
                        key=f"ag_ida_{idx}",
                        placeholder="ex: 1-2",
                        help="Placar do jogo de ida — usado para calcular ajuste de volta"
                    )
                    # Preview do ajuste
                    if _ag_ida and "-" in _ag_ida:
                        try:
                            _g_ida = [int(x.strip()) for x in _ag_ida.split("-")]
                            _diff = _g_ida[0] - _g_ida[1]  # gols casa − gols fora na ida
                            if _diff == -1:  # casa perdeu por 1 na ida → precisa atacar
                                st.caption("✅ Perdendo por 1 gol — ataque esperado (+5 pts)")
                            elif _diff <= -2:  # casa perdeu por 2+ → pode administrar visitante
                                st.caption("⚠️ Vantagem de 2+ gols para o visitante — anestesia possível (-5 pts)")
                            elif _diff >= 2:  # casa ganhou por 2+ na ida → pode administrar
                                st.caption("⚠️ Vantagem de 2+ gols para mandante — anestesia possível (-5 pts)")
                            elif _diff == 1:  # visitante perdeu por 1 → precisa atacar
                                st.caption("✅ Visitante perdendo por 1 gol — ataque esperado (+5 pts)")
                        except (ValueError, IndexError):
                            pass

        # D8 — n_times automático pela liga
        _liga_info  = HIERARQUIA_LIGAS.get(liga, {})
        _nt_liga    = _liga_info.get("n_times")
        _nt_default = _nt_liga or max(10, int(_d.get("n_times", 18) or 18))
        _nt_max     = _nt_default  # limite correto = total de times da liga
        n_times     = _nt_default

        st.markdown("**Posição na tabela:**")
        col_pc, col_pf = st.columns(2)
        with col_pc:
            pos_casa = st.number_input("Pos. casa", 1, _nt_max, 1, step=1, key=f"pc_{idx}")
        with col_pf:
            pos_fora = st.number_input("Pos. fora", 1, _nt_max, 1, step=1, key=f"pf_{idx}")

        # D9 — rebaixamento automático pela posição + zona da liga
        _reb_direto  = _liga_info.get("reb_direto", 0)
        _reb_playoff = _liga_info.get("reb_playoff", 0)

        def _calc_risco_sb(pos, n, rd, rp):
            if not pos or pos <= 1: return "desconhecido"
            if rd and pos >= rd: return "rebaixamento"
            if rp and pos >= rp: return "playoff"
            if n and pos / n > 0.78: return "atencao"
            return "ok"

        _risco_casa = _calc_risco_sb(pos_casa if pos_casa > 1 else None, _nt_default, _reb_direto, _reb_playoff)
        _risco_fora = _calc_risco_sb(pos_fora if pos_fora > 1 else None, _nt_default, _reb_direto, _reb_playoff)
        casa_reb = (_risco_casa == "rebaixamento")
        fora_reb = (_risco_fora == "rebaixamento")

        for _tn, _risco, _pos in [(time_casa, _risco_casa, pos_casa), (time_fora, _risco_fora, pos_fora)]:
            if _risco == "rebaixamento":
                st.markdown(
                    f'<div style="background:#450a0a;border-left:3px solid #ef4444;'
                    f'border-radius:0 4px 4px 0;padding:4px 8px;font-size:10px;'
                    f'color:#fca5a5;margin-top:4px">'
                    f'❌ {_tn} em rebaixamento ({_pos}º/{_nt_default})</div>',
                    unsafe_allow_html=True)
            elif _risco == "playoff":
                st.markdown(
                    f'<div style="background:#431407;border-left:3px solid #f97316;'
                    f'border-radius:0 4px 4px 0;padding:4px 8px;font-size:10px;'
                    f'color:#fdba74;margin-top:4px">'
                    f'⚠️ {_tn} zona play-off ({_pos}º/{_nt_default})</div>',
                    unsafe_allow_html=True)

        # D9 — checkboxes manuais só se posição desconhecida (= 1)
        if pos_casa <= 1 or pos_fora <= 1:
            st.markdown(
                "<div style='font-size:10px;color:#475569;margin-top:6px'>"
                "Posição desconhecida → rebaixamento manual:</div>",
                unsafe_allow_html=True)
            _col_cr, _col_fr = st.columns(2)
            with _col_cr:
                if pos_casa <= 1:
                    casa_reb = st.checkbox("Casa reb.", key=f"creb_{idx}")
            with _col_fr:
                if pos_fora <= 1:
                    fora_reb = st.checkbox("Fora reb.", key=f"freb_{idx}")
        else:
            st.session_state.setdefault(f"creb_{idx}", False)
            st.session_state.setdefault(f"freb_{idx}", False)

        # D10 — Derby via Google IA (derby_auto pré-preenche, não substitui)
        # D10 — derby_ofensivo será definido pelo H2H nativo (futuro)
        # Por agora: Google IA confirma só se é derby sim/não
        derby_of_manual = False  # sempre False até H2H nativo implementado
        st.session_state.setdefault(f"derbyof_{idx}", False)

        with st.expander(
            f"🔶 Derby — {'detectado automaticamente' if derby_auto else 'confirmar via Google IA'}",
            expanded=False
        ):
            if derby_auto:
                st.markdown(
                    '<div style="background:#451a03;border-left:3px solid #d97706;'
                    'border-radius:0 4px 4px 0;padding:4px 8px;font-size:10px;'
                    'color:#fbbf24;margin-bottom:6px">'
                    f'🔶 Lista interna: {time_casa} × {time_fora}</div>',
                    unsafe_allow_html=True)

            e_derby_manual = st.checkbox("É derby / clássico", key=f"derby_{idx}",
                                         value=derby_auto)

            # Google IA para derbys não conhecidos — só pergunta sim/não
            if not derby_auto:
                st.markdown("---")
                _prompt_derby = (
                    f"{time_casa} x {time_fora} é clássico / derby?\n"
                    f"Responda EXATAMENTE neste formato (sem texto extra):\n"
                    f"DERBY: sim"
                )
                from urllib.parse import quote_plus as _qp
                _url_derby = f"https://www.google.com/search?q={_qp(_prompt_derby)}"
                st.text_area("Prompt derby", value=_prompt_derby, height=80,
                             key=f"prompt_derby_{idx}", label_visibility="collapsed",
                             help="Copie e cole diretamente no Google Modo IA")
                st.markdown(
                    f'<a href="{_url_derby}" target="_blank" style="display:block;'
                    f'background:#1c1917;border:1px solid #78350f;color:#fbbf24;'
                    f'text-decoration:none;border-radius:6px;padding:6px 10px;'
                    f'font-size:11px;font-weight:600;text-align:center;margin-bottom:6px">'
                    f'🔶 Abrir Google com prompt derby</a>',
                    unsafe_allow_html=True)
                resposta_derby_ia = st.text_area(
                    "Resposta Google IA (derby)", key=f"resp_derby_{idx}", height=60,
                    placeholder="DERBY: sim")
                if resposta_derby_ia.strip():
                    _rl = resposta_derby_ia.lower()
                    _id = any(p in _rl for p in ["derby: sim","derby:sim","clássico: sim","classico: sim"])
                    if _id:
                        e_derby_manual = True  # derby confirmado via IA
                        e_derby_manual = True
                        st.markdown(
                            '<div style="border-left:3px solid #fbbf24;padding:4px 8px;'
                            'font-size:10px;color:#fbbf24">🔶 Derby confirmado</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            '<div style="font-size:10px;color:#6ee7b7;padding:4px 0">'
                            '✅ Confirmado: não é derby</div>',
                            unsafe_allow_html=True)

        # Desfalques movidos para expander 🏥 Desfalques — Google IA

    # ── FOOTYSTATS POR COMPETIÇÃO (Item 9 V7.2) ───────────────────
    # Visível apenas em copa_inter — dado global da Betano mistura ligas.
    # Dado GERAL do time nesta competição (FootyStats não separa casa/fora).
    _o15m_comp = _o25m_comp = _btts_m_comp = _avg_m_comp = None
    _o15v_comp = _o25v_comp = _btts_v_comp = _avg_v_comp = None

    if tipo_comp == "copa_inter":
        with st.expander("🏆 FootyStats — dados por competição (opcional)", expanded=False):
            st.caption("Formato: BTTS%, xGF, Over1.5%, Over2.5%, AVG — ex: 64%,1.74,100%,73%,3.45")

            def _parse_footy_linha(linha):
                """Parseia linha 'btts,xGF,1.5+,2.5+,AVG' → (btts, xgf, o15, o25, avg)"""
                if not linha.strip(): return None, None, None, None, None
                partes = [p.strip().replace("%","").replace(",",".") for p in linha.replace(",", " ").split()]
                # aceita separação por espaço ou vírgula, remove % inline
                # reparse após normalizar
                partes = [p for p in linha.strip().replace(",", " ").split() if p]
                def _pct(s):
                    try:
                        v = float(s.replace("%","").replace(",","."))
                        return v / 100 if v > 1 else v
                    except: return None
                def _num(s):
                    try: return float(s.replace(",",".").replace("%",""))
                    except: return None
                btts = _pct(partes[0]) if len(partes) > 0 else None
                xgf  = _num(partes[1]) if len(partes) > 1 else None
                o15  = _pct(partes[2]) if len(partes) > 2 else None
                o25  = _pct(partes[3]) if len(partes) > 3 else None
                avg  = _num(partes[4]) if len(partes) > 4 else None
                return btts, xgf, o15, o25, avg

            _raw_m = st.text_input(
                f"🏠 {time_casa}", key=f"footy_m_{idx}",
                placeholder="64%  1.74  100%  73%  3.45"
            )
            _raw_v = st.text_input(
                f"✈️ {time_fora}", key=f"footy_v_{idx}",
                placeholder="50%  1.20  80%  40%  2.10"
            )

            _btts_m_comp, _xgf_m, _o15m_comp, _o25m_comp, _avg_m_comp = _parse_footy_linha(_raw_m)
            _btts_v_comp, _xgf_v, _o15v_comp, _o25v_comp, _avg_v_comp = _parse_footy_linha(_raw_v)

            # Preview
            _prev = []
            if _o15m_comp is not None:
                _prev.append(f"{time_casa}: O1.5={_o15m_comp*100:.0f}% O2.5={_o25m_comp*100:.0f}% BTTS={_btts_m_comp*100:.0f}% AVG={_avg_m_comp:.2f}" if _o25m_comp and _btts_m_comp and _avg_m_comp else f"{time_casa} O1.5={_o15m_comp*100:.0f}%")
            if _o15v_comp is not None:
                _prev.append(f"{time_fora}: O1.5={_o15v_comp*100:.0f}% O2.5={_o25v_comp*100:.0f}% BTTS={_btts_v_comp*100:.0f}% AVG={_avg_v_comp:.2f}" if _o25v_comp and _btts_v_comp and _avg_v_comp else f"{time_fora} O1.5={_o15v_comp*100:.0f}%")
            if _avg_m_comp and _avg_v_comp:
                _prev.append(f"AVG combinado: {_avg_m_comp + _avg_v_comp:.2f}")
            if _prev:
                st.caption("✅ " + " · ".join(_prev))

    # ── BETANO ────────────────────────────────────────────────────
    with st.expander("📊 BETANO — cole o bruto", expanded=False):

        betano_raw = st.text_area(
            "Betano — texto bruto",
            key=f"betano_{idx}",
            height=220,
            help=(
                "O QUE COPIAR — em ordem:\n\n"
                "① Bloco Época (topo da página do jogo)\n"
                "→ Copiar o bloco 'Estatísticas da época / Por partida'\n"
                "→ Contém: Vitórias%, Golos, BTTS, Sem marcar, Baliza inviolada\n\n"
                "② Mais/Menos → aba LOCAL (para dados do mandante)\n"
                "→ Copiar linha 'Mais de 1.5' da aba Local\n\n"
                "③ Mais/Menos → aba VISITANTE (para dados do visitante)\n"
                "→ Copiar linha 'Mais de 1.5' da aba Visitante\n\n"
                "Cole tudo junto — o parser separa automaticamente."
            ),
            placeholder=(
                "Cole tudo junto. Exemplo:\n\n"
                "33%Vitórias25%\n"
                "1.75Golos1.42\n"
                "58%Ambas as equipas para marcar83%\n"
                "33%Sem marcar8%\n\n"
                "— Local (mandante) —\n"
                "Mais de 1.5  82%  3.4\n\n"
                "— Visitante —\n"
                "Mais de 1.5  60%  1.2\n\n"
                "V V E V V\nD V E D V"
            )
        )

    # ── FORMA RECENTE — BETANO (V7.2.1 — campo único) ───────────
    with st.expander("📈 FORMA RECENTE — Betano últimos 6", expanded=False):

        forma_recente_raw = st.text_area(
            "Forma recente — Marcados + Concedidos (ambos os times)",
            key=f"forma_recente_{idx}",
            height=200,
            help=(
                "O QUE COPIAR (campo único — dois times juntos):\n\n"
                "Selecionar Últimos 6 e copiar dois blocos em sequência:\n"
                "① Marcados / Total / Últimos 6 — tabela completa\n"
                "② Concedidos / Total / Últimos 6 — tabela completa\n\n"
                "Cole tudo junto — o parser separa automaticamente mandante e visitante."
            ),
            placeholder=(
                "Cole aqui os blocos Marcados/Total/6 + Concedidos/Total/6 juntos.\n\n"
                "Exemplo:\n"
                "Matches Scored at FT\n"
                "5\n5 / 6\n5\n5 / 6\n"
                "Matches Scored at HT\n"
                "4\n4 / 6\n5\n5 / 6\n"
                "Média Gols Marcados\n"
                "2.00\n12 / 6\n2.17\n13 / 6\n"
                "Sem marcar\n"
                "17%\n1 / 6\n17%\n1 / 6\n"
                "Média Gols Concedidos\n"
                "1.50\n9 / 6\n0.33\n2 / 6\n"
                "Média Total Gols Concedidos 1ª Parte\n"
                "0.67\n4 / 6\n0.17\n1 / 6"
            )
        )

        # Parse em tempo real — retorna (casa, fora)
        _fc, _ff = parsear_forma_recente(forma_recente_raw) if forma_recente_raw.strip() else (FormaRecente(), FormaRecente())
        forma_casa_raw = forma_recente_raw   # passar o mesmo texto para o Jogo — parser interno distingue
        forma_fora_raw = forma_recente_raw   # idem

        def _preview_forma(label: str, fr: FormaRecente, cor: str):
            n = fr.total_jogos_amostra or 6
            linhas_prev = []
            if fr.jogos_com_gol is not None:
                linhas_prev.append(f"Gols: {fr.jogos_com_gol}/{n} jogos")
            if fr.jogos_com_gol_1t is not None:
                linhas_prev.append(f"Gols 1T: {fr.jogos_com_gol_1t}/{n}")
            if fr.media_gols_marcados is not None:
                linhas_prev.append(f"Média marcados: {fr.media_gols_marcados:.2f}")
            if fr.jogos_sem_marcar is not None:
                linhas_prev.append(f"Sem marcar: {fr.jogos_sem_marcar}/{n}")
            if fr.media_gols_concedidos is not None:
                linhas_prev.append(f"Média concedidos: {fr.media_gols_concedidos:.2f}")
            if fr.media_gols_concedidos_1t is not None:
                linhas_prev.append(f"Concedidos 1T: {fr.media_gols_concedidos_1t:.2f}")
            if linhas_prev:
                st.markdown(
                    f"""<div style="background:#0d1226;border-left:3px solid {cor};
                    padding:6px 10px;border-radius:0 6px 6px 0;font-size:10px;
                    font-family:monospace;color:{cor};margin-bottom:4px">
                    <strong>{label}</strong><br>{"<br>".join(linhas_prev)}
                    </div>""",
                    unsafe_allow_html=True
                )

        if forma_recente_raw.strip():
            _preview_forma(time_casa or "Mandante", _fc, "#a78bfa")
            _preview_forma(time_fora or "Visitante", _ff, "#60a5fa")

    # ── SUPERBET ──────────────────────────────────────────────────
    # ── H2H ───────────────────────────────────────────────────────
    with st.expander("📊 H2H — cole o bruto", expanded=False):
        h2h_raw = st.text_area(
            "H2H — texto bruto",
            key=f"h2h_{idx}",
            height=180,
            help=(
                "COMO COLAR O H2H\n\n"
                "Cole apenas confrontos DIRETOS entre os dois times.\n"
                "O parser detecta qualquer formato com X - Y.\n\n"
                "Superbet (aba H2H → Confronto direto):\n"
                "2025. Estoril-Sporting 0 - 1\n"
                "2025. Sporting-Estoril 3 - 1\n\n"
                "Betano ou texto livre:\n"
                "3-1, 0-3, 5-1, 0-1, 0-3\n\n"
                "⚠️ NÃO cole a tabela geral de forma recente —\n"
                "distorce o cálculo do H2H."
            ),
            placeholder="Cole aqui. Exemplo:\n\n2025. Estoril - Sporting 0 - 1\n2025. Sporting - Estoril 3 - 1\n2024. Estoril - Sporting 0 - 3\n2024. Estoril - Sporting 0 - 1\n2024. Sporting - Estoril 5 - 1"
        )

    # ── SUPERBET ──────────────────────────────────────────────────
    with st.expander("📊 SUPERBET — cole o bruto", expanded=False):
        superbet_raw = st.text_area(
            "Superbet — texto bruto",
            key=f"superbet_{idx}",
            height=220,
            help=(
                "O QUE COPIAR DO SUPERBET\n\n"
                "Aba Dados → Estatísticas Principais\n\n"
                "Formato vertical (padrão):\n"
                "2.6\nGols\n2.0\n"
                "2.1\nGols esperados (xG)\n1.5\n"
                "18.3\nFinalizações Totais\n12.4\n\n"
                "Formato inline (também aceito):\n"
                "2.1 Gols esperados (xG) 1.5\n\n"
                "Cole todas as abas — o parser filtra."
            ),
            placeholder="Cole aqui. Exemplo:\n\n2.6\nGols\n2.0\n2.1\nGols esperados (xG)\n1.5\n18.3\nFinalizações Totais\n12.4\n7.0\nChutes no gol\n4.6\n3.8\nGrandes chances criadas\n2.5"
        )

        # D12 — Últimos jogos (campo único — primeiro bloco = casa, segundo = fora)
        st.markdown(
            """<div style="font-size:10px;color:#7dd3fc;margin-top:12px;margin-bottom:4px;
                font-weight:600;letter-spacing:0.05em">📅 ÚLTIMOS JOGOS</div>
            <div style="font-size:9px;color:#475569;margin-bottom:4px">
                Primeiro bloco = Mandante · Segundo bloco = Visitante · Separe com linha em branco
            </div>""",
            unsafe_allow_html=True
        )
        ultimos_raw = st.text_area(
            "Últimos jogos",
            key=f"ultimos_raw_{idx}",
            height=260,
            label_visibility="collapsed",
            help=(
                "Cole os dois blocos juntos — separe com UMA linha em branco.\n\n"
                "Primeiro bloco = Mandante, segundo bloco = Visitante.\n\n"
                "Formato:\n"
                "07.03.\nAtalanta-Udinese\n2 - 2\nE\n"
                "25.02.\nAtalanta-Dortmund\n4 - 1\nV\n\n"
                "28.02.\nDortmund-Bayern\n2 - 3\nV\n"
                "14.02.\nWerder-Bayern\n0 - 3\nV"
            ),
            placeholder=(
                "07.03.\nAtalanta-Udinese\n2 - 2\nE\n"
                "25.02.\nAtalanta-Dortmund\n4 - 1\nV\n\n"
                "28.02.\nDortmund-Bayern\n2 - 3\nV\n"
                "14.02.\nWerder-Bayern\n0 - 3\nV"
            )
        )

    # ── DESFALQUES — GOOGLE IA ────────────────────────────────────
    # Defaults — garantem que as variáveis existem mesmo se expander fechado
    desfalques_casa_ia = 0
    desfalques_fora_ia = 0
    atk_casa_ia  = False
    atk_fora_ia  = False
    cri_casa_ia  = False
    cri_fora_ia  = False
    criativo_sub_casa = False
    criativo_sub_fora = False
    qualidade_sub_atk_casa = 0
    qualidade_sub_atk_fora = 0
    desf_casa_txt = ""
    desf_fora_txt = ""
    info_casa_ia  = InfoDesfalqueIA()
    info_fora_ia  = InfoDesfalqueIA()

    with st.expander("🏥 Desfalques — Google IA", expanded=False):

        # D7 — Desfalques Superbet (dentro do expander para alimentar o prompt)
        st.markdown(
            """<div style="font-size:10px;color:#fbbf24;margin-bottom:4px;
                font-weight:600;letter-spacing:0.05em">🏥 DESFALQUES — Superbet</div>
            <div style="font-size:9px;color:#475569;margin-bottom:6px">
                Cole primeiro — o prompt de pesquisa incluirá os jogadores automaticamente
            </div>""",
            unsafe_allow_html=True
        )
        desf_superbet_raw = st.text_area(
            "Desfalques Superbet",
            key=f"desf_superbet_{idx}",
            height=180,
            label_visibility="collapsed",
            help=(
                "Cole a aba Lesionados/Suspensos da Superbet.\\n\\n"
                "Aceita dois times juntos ou um só.\\n\\n"
                "Formato:\\n"
                "Atalanta\\nJogadores ausentes\\n17\\nDe Ketelaere\\nLesionado\\n"
                "42\\nScalvini\\nSuspenso\\n\\n"
                "Bayern de Munique\\nJogadores ausentes\\n1\\nNeuer\\nLesionado"
            ),
            placeholder=(
                "Atalanta\\nJogadores ausentes\\n17\\nDe Ketelaere\\nLesionado\\n"
                "42\\nScalvini\\nSuspenso\\n\\n"
                "Bayern de Munique\\nJogadores ausentes\\n1\\nNeuer\\nLesionado"
            )
        )
        # Preview inline
        if desf_superbet_raw.strip():
            _dp = parsear_desfalques_superbet(desf_superbet_raw, time_casa, time_fora)
            _dc_s, _di_s, _nc_s, _ni_s = _dp["casa"]
            _df_s, _dif_s, _nf_s, _nif_s = _dp["fora"]
            _prev = []
            if _nc_s or _ni_s:
                _prev.append(f"🏠 {time_casa or 'Casa'}: {_dc_s}🔴 {_di_s}🟡")
                if _nc_s: _prev.append("  " + ", ".join(_nc_s))
                if _ni_s: _prev.append("  ❓ " + ", ".join(_ni_s))
            if _nf_s or _nif_s:
                _prev.append(f"✈️ {time_fora or 'Fora'}: {_df_s}🔴 {_dif_s}🟡")
                if _nf_s: _prev.append("  " + ", ".join(_nf_s))
                if _nif_s: _prev.append("  ❓ " + ", ".join(_nif_s))
            if _prev:
                st.markdown(
                    "<div style='background:#0d1226;border-left:3px solid #f59e0b;"
                    "padding:6px 10px;border-radius:0 6px 6px 0;font-size:10px;"
                    "font-family:monospace;color:#fbbf24;margin-top:4px;margin-bottom:8px;"
                    "white-space:pre'>" + "\n".join(_prev) + "</div>",
                    unsafe_allow_html=True
                )
        st.markdown("<hr style='border-color:#1e2640;margin:8px 0'>", unsafe_allow_html=True)

        # Data vem direto da data_global (campo único no topo do app)
        _data_prompt = st.session_state.get("data_global", "")
        data_jogo = _data_prompt

        # Gerar prompt base
        prompt_txt = gerar_prompt_google(time_casa, time_fora, liga, _data_prompt)

        # ── Enriquecer prompt com desfalques Superbet já parseados ────
        # Os nomes extraídos da Superbet são injetados como contexto adicional
        # para que o Google IA já saiba quem verificar / confirmar.
        _sb_raw_prompt = st.session_state.get(f"desf_superbet_{idx}", "")
        if _sb_raw_prompt.strip():
            _dp_p = parsear_desfalques_superbet(_sb_raw_prompt, time_casa, time_fora)
            _nc_p, _ni_p = _dp_p["casa"][2], _dp_p["casa"][3]
            _nf_p, _nif_p = _dp_p["fora"][2], _dp_p["fora"][3]
            _linhas_sb = []
            _header_sb = "\n\n⚠️ DESFALQUES JÁ IDENTIFICADOS pela Superbet — confirme e complemente:"
            if _nc_p or _ni_p:
                _ausentes_c = [f"{n} (confirmado)" for n in _nc_p] +                               [f"{n} (incerto)" for n in _ni_p]
                _linhas_sb.append(_header_sb)
                _linhas_sb.append(f"{time_casa}: {', '.join(_ausentes_c)}")
            if _nf_p or _nif_p:
                _ausentes_f = [f"{n} (confirmado)" for n in _nf_p] +                               [f"{n} (incerto)" for n in _nif_p]
                if not _linhas_sb:
                    _linhas_sb.append(_header_sb)
                _linhas_sb.append(f"{time_fora}: {', '.join(_ausentes_f)}")
            if _linhas_sb:
                prompt_txt = prompt_txt + "".join(_linhas_sb)

        url_google = gerar_url_google(time_casa, time_fora, liga, _data_prompt)
        # Reconstruir URL com prompt enriquecido (inclui nomes Superbet)
        from urllib.parse import quote_plus as _qp_url
        url_google = f"https://www.google.com/search?q={_qp_url(prompt_txt)}"

        # ── Prompt gerado (copiável) ──────────────────────────────────
        st.text_area(
            "Prompt para o Google Modo IA",
            value=prompt_txt,
            height=210,
            key=f"prompt_display_{idx}",
            help="Copie e cole na barra de pesquisa do Google, ou use o botão abaixo",
            disabled=False,
            label_visibility="collapsed"
        )

        # ── Botão de link direto ──────────────────────────────────────
        # Link simples sem title="" (evita vazamento de HTML)
        st.markdown(
            f'''<a href="{url_google}" target="_blank"
               style="display:block;background:linear-gradient(90deg,#1e40af,#1d4ed8);
               color:#fff;text-decoration:none;border-radius:8px;padding:9px 14px;
               font-size:12px;font-weight:600;text-align:center;margin-bottom:10px">
               🔍 Abrir Google — Modo IA
            </a>''',
            unsafe_allow_html=True
        )
        # Instrução compacta em caption nativo (sem HTML, sem vazamento)
        st.caption(
            "① Copie o prompt acima · ② Abra o Google · "
            "③ Leia o Modo IA · ④ Cole a resposta abaixo"
        )



        resposta_ia = st.text_area(
            "Resposta Google IA",
            key=f"googleia_{idx}",
            height=200,
            placeholder=(
                "Cole aqui a resposta do Google Modo IA no formato:\n\n"
                "TIME CASA:\n"
                "- Adam Hlozek | atacante titular | Lesionado | Sub: Kramaric (qualidade: titular)\n"
                "- Tim Lemperle | atacante titular | Lesionado | Sub: Asllani (qualidade: reserva)\n\n"
                "TIME FORA:\n"
                "- Ricky Jones | atacante titular | Lesionado | Sub: Kaars (qualidade: reserva)\n"
                "- Connor Metcalfe | meia criativo | Suspenso | Sub: Rasmussen (qualidade: reserva)\n\n"
                "Nível ofensivo casa: queda leve\n"
                "Nível ofensivo fora: queda drástica"
            )
        )

        # Parsear resposta do Google IA em tempo real
        info_casa_ia = InfoDesfalqueIA()
        info_fora_ia = InfoDesfalqueIA()
        if resposta_ia.strip():
            info_casa_ia, info_fora_ia = parsear_resposta_google_ia(
                resposta_ia, time_casa, time_fora
            )

        # Exibir resultado do parser — D7 com minutagem
        if resposta_ia.strip() and (info_casa_ia.lesionados or info_fora_ia.lesionados
                                    or info_casa_ia.incertos or info_fora_ia.incertos):
            st.markdown(
                """<div style="font-size:10px;color:#475569;letter-spacing:1px;
                margin-top:8px;margin-bottom:4px">🏥 DESFALQUES DETECTADOS — PREENCHIMENTO AUTOMÁTICO</div>""",
                unsafe_allow_html=True
            )
            for label, info in [(time_casa, info_casa_ia), (time_fora, info_fora_ia)]:
                ausentes = info.lesionados + info.incertos
                if not ausentes:
                    continue
                n_total = len(info.lesionados)
                cor = "#f87171" if n_total >= 2 else "#fbbf24" if n_total >= 1 else "#94a3b8"
                _gols_str = (f" · {info.gols_ausente}G {info.assists_ausente}A"
                             if info.gols_ausente or info.assists_ausente else "")

                # Linha de minutagem do ausente
                _min_aus_str = ""
                if info.min_ausente_atk is not None:
                    _min_aus_str = f" · <strong>Ausente: {info.min_ausente_atk*100:.0f}% min</strong>"
                    _rot = " ← rotação" if info.min_ausente_atk < 0.70 else " ← titular real"
                    _min_aus_str += _rot

                # Linha de minutagem do sub
                _min_sub_str = ""
                if info.min_melhor_sub is not None:
                    _sub_cor = "#6ee7b7" if info.min_melhor_sub >= 0.70 else "#fbbf24" if info.min_melhor_sub >= 0.50 else "#f87171"
                    _sub_label = "nível equivalente" if info.min_melhor_sub >= 0.70 else "competente" if info.min_melhor_sub >= 0.50 else "sem substituto direto"
                    _min_sub_str = f'<span style="color:{_sub_cor}">Sub: {info.min_melhor_sub*100:.0f}% min — {_sub_label}</span>'

                # Flag linha comprometida
                _lc_str = ' <span style="color:#f87171;font-weight:700">⚠️ LINHA COMPROMETIDA</span>' if info.linha_comprometida else ""

                linhas_html = []
                if info.lesionados:
                    linhas_html.append(f"Fora: {', '.join(info.lesionados)}")
                if info.incertos:
                    linhas_html.append(f"Incerto: {', '.join(info.incertos)}")
                if info.substitutos:
                    linhas_html.append(f"Melhor sub disponível: {', '.join(info.substitutos)}")
                if _min_sub_str:
                    linhas_html.append(_min_sub_str)

                st.markdown(
                    f"""<div style="background:#0d1226;border-left:3px solid {cor};
                        padding:7px 10px;border-radius:0 6px 6px 0;
                        margin-bottom:5px;font-size:11px;font-family:monospace;color:{cor}">
                        <strong>{label}{_gols_str}{_min_aus_str}</strong>{_lc_str}<br>
                        {"<br>".join(linhas_html)}
                    </div>""",
                    unsafe_allow_html=True
                )



        # Contagens pré-preenchidas pelo parser (editáveis)
        n_casa_sugerido = len(info_casa_ia.lesionados)
        n_fora_sugerido = len(info_fora_ia.lesionados)

        col_dc, col_df = st.columns(2)
        with col_dc:
            desfalques_casa_ia = st.number_input(
                f"Desf. {time_casa[:10]}",
                min_value=0, max_value=20,
                value=n_casa_sugerido,
                key=f"dc_ia_{idx}",
                help="Pré-preenchido pelo parser — ajuste se necessário"
            )
        with col_df:
            desfalques_fora_ia = st.number_input(
                f"Desf. {time_fora[:10]}",
                min_value=0, max_value=20,
                value=n_fora_sugerido,
                key=f"df_ia_{idx}",
                help="Pré-preenchido pelo parser — ajuste se necessário"
            )



        # ── D7 — auto-preenchimento minutagem quando resposta muda ──
        _ia_hash_key = f"_resp_hash_{idx}"
        _ia_hash_val = str(hash(resposta_ia.strip()))
        if st.session_state.get(_ia_hash_key) != _ia_hash_val:
            st.session_state[_ia_hash_key] = _ia_hash_val
            # Auto-preencher minutagem do parser
            if info_casa_ia.min_ausente_atk is not None:
                st.session_state[f"min_aus_atk_c_{idx}"] = str(int(info_casa_ia.min_ausente_atk * 100))
            if info_casa_ia.min_melhor_sub is not None:
                st.session_state[f"min_sub_atk_c_{idx}"] = str(int(info_casa_ia.min_melhor_sub * 100))
            if info_fora_ia.min_ausente_atk is not None:
                st.session_state[f"min_aus_atk_f_{idx}"] = str(int(info_fora_ia.min_ausente_atk * 100))
            if info_fora_ia.min_melhor_sub is not None:
                st.session_state[f"min_sub_atk_f_{idx}"] = str(int(info_fora_ia.min_melhor_sub * 100))
            if info_casa_ia.linha_comprometida:
                st.session_state[f"lc_casa_{idx}"] = True
            if info_fora_ia.linha_comprometida:
                st.session_state[f"lc_fora_{idx}"] = True

        # ── CASA ─────────────────────────────────────────────────────
        st.caption(f"🏠 {time_casa}")
        atk_casa_ia = st.checkbox(
            "Atacante ausente",
            value=info_casa_ia.tem_atacante_out,
            key=f"atk_c_ia_{idx}",
            help="Centroavante, ponta titular, atacante pelo lado"
        )
        atk_casa_duvida = False
        qualidade_sub_atk_casa = 0
        if atk_casa_ia:
            atk_casa_duvida = st.checkbox(
                "🟡 Status dúvida (penalidade máx. -10 pts)",
                key=f"atk_c_duvida_{idx}",
                help="Marcar se o jogador está como dúvida no Superbet — penalidade reduzida vs ausência confirmada"
            )
            col_mc1, col_mc2 = st.columns(2)
            _min_aus_c_raw = col_mc1.text_input(
                "% min. ausente",
                key=f"min_aus_atk_c_{idx}",
                placeholder="ex: 87",
                help="% de minutos do ausente na temporada (Transfermarkt)"
            )
            _min_sub_c_raw = col_mc2.text_input(
                "% min. melhor sub",
                key=f"min_sub_atk_c_{idx}",
                placeholder="ex: 34",
                help="% de minutos do melhor substituto disponível"
            )
            # Converter para float 0-1
            try:
                _min_aus_c = float(_min_aus_c_raw) / 100 if _min_aus_c_raw.strip() else None
            except ValueError:
                _min_aus_c = None
            try:
                _min_sub_c = float(_min_sub_c_raw) / 100 if _min_sub_c_raw.strip() else None
            except ValueError:
                _min_sub_c = None
            # Preview do impacto calculado
            if _min_aus_c is not None and _min_aus_c < 0.70:
                st.caption("🔵 Rotação — impacto reduzido (-5 pts)")
            elif _min_sub_c is not None:
                if _min_sub_c >= 0.70:
                    st.caption("✅ Sub de nível — impacto baixo (-3 pts)")
                elif _min_sub_c >= 0.50:
                    st.caption("⚠️ Sub competente — impacto moderado (-10 pts)")
                else:
                    st.caption("❌ Sem sub direto — impacto alto (-18 pts)")
            lc_casa = st.checkbox("⚠️ Linha comprometida (2+ atacantes ausentes)",
                                  key=f"lc_casa_{idx}")
        else:
            _min_aus_c = None
            _min_sub_c = None
            lc_casa = False

        cri_casa_ia = st.checkbox(
            "Meia criativo ausente",
            value=info_casa_ia.tem_criativo_out,
            key=f"cri_c_ia_{idx}",
            help="Armador, meia-atacante, playmaker"
        )
        criativo_sub_casa = False
        if cri_casa_ia:
            criativo_sub_casa = st.checkbox(
                "↳ Sub mantém função criativa",
                value=info_casa_ia.tem_substituto_atacante,
                key=f"cri_sub_c_{idx}",
                help="Sub assume papel de criação no ataque"
            )

        st.markdown(
            "<hr style='border:0;border-top:1px solid #1e2640;margin:6px 0'>",
            unsafe_allow_html=True
        )

        # ── FORA ─────────────────────────────────────────────────────
        st.caption(f"✈️ {time_fora}")

        atk_fora_ia = st.checkbox(
            "Atacante ausente",
            value=info_fora_ia.tem_atacante_out,
            key=f"atk_f_ia_{idx}",
            help="Centroavante, ponta titular, atacante pelo lado"
        )
        atk_fora_duvida = False
        qualidade_sub_atk_fora = 0  # legado mantido
        if atk_fora_ia:
            atk_fora_duvida = st.checkbox(
                "🟡 Status dúvida (penalidade máx. -10 pts)",
                key=f"atk_f_duvida_{idx}",
                help="Marcar se o jogador está como dúvida no Superbet — penalidade reduzida vs ausência confirmada"
            )
            col_mf1, col_mf2 = st.columns(2)
            _min_aus_f_raw = col_mf1.text_input(
                "% min. ausente",
                key=f"min_aus_atk_f_{idx}",
                placeholder="ex: 87",
                help="% de minutos do ausente na temporada (Transfermarkt)"
            )
            _min_sub_f_raw = col_mf2.text_input(
                "% min. melhor sub",
                key=f"min_sub_atk_f_{idx}",
                placeholder="ex: 34",
                help="% de minutos do melhor substituto disponível"
            )
            try:
                _min_aus_f = float(_min_aus_f_raw) / 100 if _min_aus_f_raw.strip() else None
            except ValueError:
                _min_aus_f = None
            try:
                _min_sub_f = float(_min_sub_f_raw) / 100 if _min_sub_f_raw.strip() else None
            except ValueError:
                _min_sub_f = None
            if _min_aus_f is not None and _min_aus_f < 0.70:
                st.caption("🔵 Rotação — impacto reduzido (-5 pts)")
            elif _min_sub_f is not None:
                if _min_sub_f >= 0.70:
                    st.caption("✅ Sub de nível — impacto baixo (-3 pts)")
                elif _min_sub_f >= 0.50:
                    st.caption("⚠️ Sub competente — impacto moderado (-10 pts)")
                else:
                    st.caption("❌ Sem sub direto — impacto alto (-18 pts)")
            lc_fora = st.checkbox("⚠️ Linha comprometida (2+ atacantes ausentes)",
                                  key=f"lc_fora_{idx}")
        else:
            _min_aus_f = None
            _min_sub_f = None
            lc_fora = False

        cri_fora_ia = st.checkbox(
            "Meia criativo ausente",
            value=info_fora_ia.tem_criativo_out,
            key=f"cri_f_ia_{idx}",
            help="Armador, meia-atacante, playmaker"
        )
        criativo_sub_fora = False
        if cri_fora_ia:
            criativo_sub_fora = st.checkbox(
                "↳ Sub mantém função criativa",
                value=False,
                key=f"cri_sub_f_{idx}",
                help="Sub assume papel de criação no ataque"
            )

        # Texto bruto combinado para o relatório (lesionados + incertos parseados)
        def montar_texto_desf(info: InfoDesfalqueIA) -> str:
            partes = []
            if info.lesionados:
                partes.append("\n".join(
                    f"{n}\nLesionado" for n in info.lesionados
                ))
            if info.incertos:
                partes.append("\n".join(
                    f"{n}\nIncerto" for n in info.incertos
                ))
            return "\n".join(partes)

        desf_casa_txt = montar_texto_desf(info_casa_ia)
        desf_fora_txt = montar_texto_desf(info_fora_ia)

    # ctx construído APÓS o expander, usando valores do expander (ou defaults)
    ctx = DadosContexto(
        tipo_competicao=tipo_comp,
        tem_cl_proximos_3_dias=tem_cl,
        tem_el_proximos_4_dias=tem_el,
        total_times_liga=int(n_times),
        casa_posicao=int(pos_casa) if pos_casa > 1 else None,
        fora_posicao=int(pos_fora) if pos_fora > 1 else None,
        casa_zona_rebaixamento=casa_reb,
        fora_zona_rebaixamento=fora_reb,
        desfalques_casa=desfalques_casa_ia,
        desfalques_fora=desfalques_fora_ia,
        atacante_titular_casa_out=atk_casa_ia,
        atacante_titular_fora_out=atk_fora_ia,
        atacante_titular_casa_duvida=atk_casa_duvida,
        atacante_titular_fora_duvida=atk_fora_duvida,
        criativo_central_casa_out=cri_casa_ia,
        criativo_central_fora_out=cri_fora_ia,
        criativo_sub_casa=criativo_sub_casa,
        criativo_sub_fora=criativo_sub_fora,
        qualidade_sub_atk_casa=qualidade_sub_atk_casa,
        qualidade_sub_atk_fora=qualidade_sub_atk_fora,
        e_derby=e_derby_manual or derby_auto,
        derby_ofensivo=derby_of_manual or derby_of_auto,
        agregado_cl=agregado_cl if agregado_cl else None,
        # D7 — minutagem real
        min_ausente_atk_casa=_min_aus_c,
        min_sub_atk_casa=_min_sub_c,
        min_ausente_atk_fora=_min_aus_f,
        min_sub_atk_fora=_min_sub_f,
        linha_comprometida_casa=lc_casa,
        linha_comprometida_fora=lc_fora,
        # Item 1+8 V7.2 — fase eliminatória
        fase_eliminatoria=_fase_elim,
        jogo_volta=_jogo_volta,
        agregado_gols_ida=_ag_ida if _ag_ida else None,
    )

    # ── PARSEAR ───────────────────────────────────────────────────
    betano   = parsear_betano(betano_raw)
    superbet = parsear_superbet(superbet_raw)
    h2h      = parsear_h2h(h2h_raw)

    # Item 9 V7.2 — injetar dados por competição no betano
    if tipo_comp == "copa_inter":
        if _o15m_comp  is not None: betano.over15_mandante_comp  = _o15m_comp
        if _o25m_comp  is not None: betano.over25_mandante_comp  = _o25m_comp
        if _btts_m_comp is not None: betano.btts_mandante_comp   = _btts_m_comp
        if _avg_m_comp  is not None: betano.avg_gols_mandante_comp = _avg_m_comp
        if _o15v_comp  is not None: betano.over15_visitante_comp  = _o15v_comp
        if _o25v_comp  is not None: betano.over25_visitante_comp  = _o25v_comp
        if _btts_v_comp is not None: betano.btts_visitante_comp   = _btts_v_comp
        if _avg_v_comp  is not None: betano.avg_gols_visitante_comp = _avg_v_comp

    # ── DEBUG VISUAL (expansível) ─────────────────────────────────
    with st.expander("🔬 Debug — valores lidos pelo parser", expanded=False):
        st.markdown("**Betano:**")
        betano_debug = {
            "Over 1.5 Casa":  f"{betano.over15_casa_pct*100:.0f}%" if betano.over15_casa_pct is not None else "❌ não lido",
            "Over 1.5 Fora":  f"{betano.over15_fora_pct*100:.0f}%" if betano.over15_fora_pct is not None else "❌ não lido",
            "Over 2.5 Casa":  f"{betano.over25_casa_pct*100:.0f}%" if betano.over25_casa_pct is not None else "❌ não lido",
            "Over 2.5 Fora":  f"{betano.over25_fora_pct*100:.0f}%" if betano.over25_fora_pct is not None else "❌ não lido",
            "BTTS Casa":      f"{betano.btts_casa_pct*100:.0f}%" if betano.btts_casa_pct is not None else "❌ não lido",
            "BTTS Fora":      f"{betano.btts_fora_pct*100:.0f}%" if betano.btts_fora_pct is not None else "❌ não lido",
            "CS Casa":        f"{betano.clean_sheet_casa_pct*100:.0f}%" if betano.clean_sheet_casa_pct is not None else "— não lido",
            "Forma Casa":     betano.forma_casa or "❌ não lida",
            "Forma Fora":     betano.forma_fora or "❌ não lida",
        }
        for k, v in betano_debug.items():
            cor = "#6ee7b7" if "❌" not in v and "—" not in v else "#f87171" if "❌" in v else "#64748b"
            st.markdown(f'<span style="font-size:11px;font-family:monospace;color:{cor}">{k}: <strong>{v}</strong></span>', unsafe_allow_html=True)

        st.markdown("**Superbet:**")
        sb_debug = {
            "xG Casa":   f"{superbet.xg_casa:.2f}" if superbet.xg_casa else "❌ não lido",
            "xG Fora":   f"{superbet.xg_fora:.2f}" if superbet.xg_fora else "❌ não lido",
            "Gols/jogo Casa": f"{superbet.gols_media_casa:.2f}" if superbet.gols_media_casa else "— não lido",
            "Gols/jogo Fora": f"{superbet.gols_media_fora:.2f}" if superbet.gols_media_fora else "— não lido",
            "Grandes Chances Casa": f"{superbet.grandes_chances_casa:.1f}" if superbet.grandes_chances_casa else "— não lido",
            "Chutes Gol Casa": f"{superbet.chutes_gol_casa:.1f}" if superbet.chutes_gol_casa else "— não lido",
        }
        for k, v in sb_debug.items():
            cor = "#6ee7b7" if "❌" not in v and "—" not in v else "#f87171" if "❌" in v else "#64748b"
            st.markdown(f'<span style="font-size:11px;font-family:monospace;color:{cor}">{k}: <strong>{v}</strong></span>', unsafe_allow_html=True)

        # Debug desfalques parseados
        if 'desf_casa_txt' in dir() or True:
            desf_c_txt = st.session_state.get(f"desftxt_c_{idx}", "")
            desf_f_txt = st.session_state.get(f"desftxt_f_{idx}", "")
            if desf_c_txt or desf_f_txt:
                st.markdown("**Desfalques parseados:**")
                for label, txt in [(f"{time_casa}", desf_c_txt), (f"{time_fora}", desf_f_txt)]:
                    if txt:
                        n_c, n_ci, nomes_c, nomes_ci = parsear_desfalques(txt)
                        if nomes_c or nomes_ci:
                            certos_str = f"{n_c} certos: {', '.join(nomes_c)}" if nomes_c else ""
                            incertos_str = f"{n_ci} incertos: {', '.join(nomes_ci)}" if nomes_ci else ""
                            resumo = " | ".join(filter(None, [certos_str, incertos_str]))
                            cor = "#f87171" if n_c >= 3 else "#fbbf24" if n_ci >= 2 else "#6ee7b7"
                            st.markdown(
                                f'''<span style="font-size:11px;font-family:monospace;color:{cor}">
                                {label}: {resumo}</span>''', unsafe_allow_html=True)

        st.markdown("**H2H:**")
        h2h_debug = {
            "Jogos lidos": str(h2h.total_jogos) if h2h.total_jogos else "❌ 0",
            "Média gols":  f"{h2h.media_gols:.2f}" if h2h.media_gols is not None else "❌ não calculado",
            "Over 1.5 %":  f"{h2h.over15_pct*100:.0f}%" if h2h.over15_pct is not None else "❌ não calculado",
            "BTTS %":      f"{h2h.btts_pct*100:.0f}%" if h2h.btts_pct is not None else "❌ não calculado",
            "Resultados":  str(h2h.resultados_recentes) if h2h.resultados_recentes else "❌ nenhum",
        }
        for k, v in h2h_debug.items():
            cor = "#6ee7b7" if "❌" not in v else "#f87171"
            st.markdown(f'<span style="font-size:11px;font-family:monospace;color:{cor}">{k}: <strong>{v}</strong></span>', unsafe_allow_html=True)

    # D7 — Parsear desfalques Superbet
    _desf_sb_raw = st.session_state.get(f"desf_superbet_{idx}", "")
    _dp_sb = parsear_desfalques_superbet(_desf_sb_raw, time_casa, time_fora)
    # Mesclar com desfalques do Google IA (Google IA prevalece se preenchido)
    if ctx.desfalques_casa == 0 and _dp_sb["casa"][0] > 0:
        ctx.desfalques_casa = _dp_sb["casa"][0]
    if ctx.desfalques_fora == 0 and _dp_sb["fora"][0] > 0:
        ctx.desfalques_fora = _dp_sb["fora"][0]
    # Complementar texto de desfalques
    _desf_txt_casa = desf_casa_txt if 'desf_casa_txt' in dir() and desf_casa_txt else _dp_sb["texto_casa"]
    _desf_txt_fora = desf_fora_txt if 'desf_fora_txt' in dir() and desf_fora_txt else _dp_sb["texto_fora"]

    # D12 — Parsear últimos jogos Superbet (campo único, split por linha em branco)
    _uj_raw = st.session_state.get(f"ultimos_raw_{idx}", "")
    _uj_blocos = re.split(r'\n\s*\n', _uj_raw.strip())
    _uj_casa_raw = _uj_blocos[0].strip() if len(_uj_blocos) >= 1 else ""
    _uj_fora_raw = _uj_blocos[1].strip() if len(_uj_blocos) >= 2 else ""
    _ultimos_jogos = parsear_ultimos_jogos_superbet(_uj_casa_raw, _uj_fora_raw, time_casa, time_fora)

    return Jogo(
        time_casa=time_casa,
        time_fora=time_fora,
        liga=liga if liga != "Outra" else "Outra",
        odd=odd,
        tipo_competicao=tipo_comp,
        superbet=superbet,
        betano=betano,
        h2h=h2h,
        contexto=ctx,
        forma_casa=_fc if 'forma_recente_raw' in dir() and forma_recente_raw.strip() else FormaRecente(),
        forma_fora=_ff if 'forma_recente_raw' in dir() and forma_recente_raw.strip() else FormaRecente(),
        desfalques_texto_casa=_desf_txt_casa,
        desfalques_texto_fora=_desf_txt_fora,
        ultimos_jogos=_ultimos_jogos,
        desfalques_superbet_raw=_desf_sb_raw
    )


# ──────────────────────────────────────────
#  RENDERIZAR CARD DE JOGO
# ──────────────────────────────────────────