"""
atlas/relatorio.py
Geração e exportação do relatório texto para o Claude.
"""

from __future__ import annotations
import os
import re
import streamlit as st
from atlas.parsers import parsear_desfalques
from atlas.utils import gerar_bilhetes
from atlas.config import (
    Jogo, PROB_MINIMA_APROVACAO, RANGE_BILHETE_MIN, RANGE_BILHETE_MAX,
)

def gerar_relatorio_txt(jogos_com_resultado: list, data_analise: str = "") -> str:
    """
    Gera relatório estruturado para ser lido pelo Claude.
    Formato otimizado para que o Claude entenda o estado completo
    da análise sem precisar de contexto adicional.
    """
    from datetime import datetime
    data = data_analise or datetime.now().strftime("%d/%m/%Y")

    aprovados  = [(j, r) for j, r in jogos_com_resultado if r["status"] in ("APROVADO", "ATENÇÃO") and r["score"] >= PROB_MINIMA_APROVACAO]
    rejeitados = [(j, r) for j, r in jogos_com_resultado if r["status"] == "REJEITADO"]
    sem_dados  = [(j, r) for j, r in jogos_com_resultado if r["status"] == "DADOS INSUFICIENTES"]
    # P5 V7.2.3 — jogos com score abaixo do mínimo mas acima de 0 (ex: score 63)
    # Antes ficavam em nenhuma seção — sumiam do relatório completamente
    intermediarios = [(j, r) for j, r in jogos_com_resultado
                      if r["status"] == "ATENÇÃO" and r["score"] < PROB_MINIMA_APROVACAO]

    linhas = []
    def L(txt=""):
        linhas.append(txt)

    # ── CABEÇALHO ─────────────────────────────────────────────────
    L("╔══════════════════════════════════════════════════════════════════╗")
    L("║  ATLAS V6.9 — RELATÓRIO PRÉ-ANÁLISE PARA CLAUDE               ║")
    L("║  Assistente Analítico · Over 1.5 Gols                          ║")
    L("╚══════════════════════════════════════════════════════════════════╝")
    L()
    L(f"  Data da análise : {data}")
    L(f"  Total de jogos  : {len(jogos_com_resultado)}")
    L(f"  Candidatos      : {len(aprovados)}")
    L(f"  Atenção (abaixo mín.): {len(intermediarios)}")
    L(f"  Rejeitados      : {len(rejeitados)}")
    L(f"  Dados insuf.    : {len(sem_dados)}")
    L()
    L("  IMPORTANTE: Este relatório é resultado do pré-processamento")
    L("  automático do Dashboard ATLAS V6.9. A DECISÃO FINAL de")
    L("  aprovação dos bilhetes é SEMPRE do Claude.")
    L()

    # ── SEÇÃO 1: CANDIDATOS ───────────────────────────────────────
    L("══════════════════════════════════════════════════════════════════")
    L("  SEÇÃO 1 — CANDIDATOS (requerem decisão final do Claude)")
    L("══════════════════════════════════════════════════════════════════")
    L()

    if not aprovados:
        L("  Nenhum candidato identificado neste dia.")
        L()
    else:
        for jogo, resultado in sorted(aprovados, key=lambda x: -x[1]["score"]):
            L(f"  ┌─ {jogo.time_casa.upper()} × {jogo.time_fora.upper()}")
            L(f"  │  Liga        : {jogo.liga}")
            L(f"  │  Competição  : {jogo.tipo_competicao}")
            L(f"  │  Odd Over 1.5: {jogo.odd}")
            L(f"  │  Status      : {resultado['status']}")
            L(f"  │  Score ATLAS : {resultado['score']}/100")
            L(f"  │  Cobertura   : {resultado['cobertura']}% dos dados")
            L("  │")

            # Dados quantitativos disponíveis
            L("  │  ── DADOS QUANTITATIVOS ──")
            b = jogo.betano
            s = jogo.superbet
            h = jogo.h2h

            def fmt(v, sufixo="%", mult=100):
                return f"{v*mult:.0f}{sufixo}" if v is not None else "n/d"

            def fmtf(v, dec=2):
                return f"{v:.{dec}f}" if v is not None else "n/d"

            L(f"  │  Over 1.5 Casa       : {fmt(b.over15_casa_pct)}")
            L(f"  │  Over 1.5 Fora       : {fmt(b.over15_fora_pct)}")
            L(f"  │  Over 2.5 Casa       : {fmt(b.over25_casa_pct)}")
            L(f"  │  Over 2.5 Fora       : {fmt(b.over25_fora_pct)}")
            L(f"  │  BTTS Casa           : {fmt(b.btts_casa_pct)}")
            L(f"  │  BTTS Fora           : {fmt(b.btts_fora_pct)}")
            L(f"  │  Clean Sheet Casa    : {fmt(b.clean_sheet_casa_pct)}")
            L(f"  │  Clean Sheet Fora    : {fmt(b.clean_sheet_fora_pct)}")
            L(f"  │  Forma Casa (ult.5)  : {b.forma_casa or 'n/d'}")
            L(f"  │  Forma Fora (ult.5)  : {b.forma_fora or 'n/d'}")
            L(f"  │  xG Casa             : {fmtf(s.xg_casa)}")
            L(f"  │  xG Fora             : {fmtf(s.xg_fora)}")
            if s.xg_casa and s.xg_fora:
                L(f"  │  xG Combinado        : {fmtf(s.xg_casa + s.xg_fora)}")
            L(f"  │  Gr. Chances Casa    : {fmtf(s.grandes_chances_casa, 1)}")
            L(f"  │  Gr. Chances Fora    : {fmtf(s.grandes_chances_fora, 1)}")
            L(f"  │  Chutes Gol Casa     : {fmtf(s.chutes_gol_casa, 1)}")
            L(f"  │  Chutes Gol Fora     : {fmtf(s.chutes_gol_fora, 1)}")
            L("  │")

            # H2H
            if h.total_jogos:
                L("  │  ── H2H DIRETO ──")
                L(f"  │  Jogos analisados    : {h.total_jogos}")
                L(f"  │  Média gols/jogo     : {fmtf(h.media_gols)}")
                L(f"  │  Over 1.5 H2H        : {fmt(h.over15_pct)}")
                L(f"  │  Over 2.5 H2H        : {fmt(h.over25_pct)}")
                L(f"  │  BTTS H2H            : {fmt(h.btts_pct)}")
                if h.resultados_recentes:
                    L(f"  │  Últimos resultados  : {' | '.join(h.resultados_recentes)}")
                if h.vitorias_casa is not None:
                    L(f"  │  Balanço H2H        : {h.vitorias_casa}V / {h.empates}E / {h.vitorias_fora}D (perspectiva casa)")
                L("  │")
            else:
                L("  │  ── H2H DIRETO ── n/d")
                L("  │")

            # Contexto
            ctx = jogo.contexto
            L("  │  ── CONTEXTO ──")
            if ctx.tem_cl_proximos_3_dias:
                L("  │  ⚠️  CL/EL nos próximos 3 dias — verificar poupança")
            if ctx.tem_el_proximos_4_dias:
                L("  │  ⚠️  Europa League nos próximos 4 dias")
            if ctx.casa_zona_rebaixamento:
                L("  │  ⚠️  Mandante em zona de rebaixamento")
            if ctx.fora_zona_rebaixamento:
                L("  │  ⚠️  Visitante em zona de rebaixamento")
            if ctx.e_derby:
                L("  │  ℹ️  Jogo classificado como derby")
            if ctx.desfalques_casa > 0:
                L(f"  │  🏥  Desfalques mandante: {ctx.desfalques_casa}")
            if ctx.desfalques_fora > 0:
                L(f"  │  🏥  Desfalques visitante: {ctx.desfalques_fora}")
            labels_sub = ["sem substituto", "queda técnica", "substituto competente", "artilheiro disponível"]
            if ctx.atacante_titular_casa_out:
                lbl = labels_sub[min(ctx.qualidade_sub_atk_casa, 3)]
                L(f"  │  🏥  Atacante titular mandante ausente — Sub: {lbl}")
            if ctx.atacante_titular_fora_out:
                lbl = labels_sub[min(ctx.qualidade_sub_atk_fora, 3)]
                L(f"  │  🏥  Atacante titular visitante ausente — Sub: {lbl}")
            if ctx.agregado_cl:
                L(f"  │  🏆  Agregado CL/Copa: {ctx.agregado_cl}")
            if jogo.desfalques_texto_casa:
                n_c, n_ci, nomes_c, nomes_ci = parsear_desfalques(jogo.desfalques_texto_casa)
                if nomes_c:
                    L(f"  │  🏥  Lesionados {jogo.time_casa} ({n_c}): {', '.join(nomes_c)}")
                if nomes_ci:
                    L(f"  │  ❓  Incertos {jogo.time_casa} ({n_ci}): {', '.join(nomes_ci)}")
            if jogo.desfalques_texto_fora:
                n_f, n_fi, nomes_f, nomes_fi = parsear_desfalques(jogo.desfalques_texto_fora)
                if nomes_f:
                    L(f"  │  🏥  Lesionados {jogo.time_fora} ({n_f}): {', '.join(nomes_f)}")
                if nomes_fi:
                    L(f"  │  ❓  Incertos {jogo.time_fora} ({n_fi}): {', '.join(nomes_fi)}")
            L("  │")

            # Alertas do motor (críticos, avisos + info CONTEXTO V7.2.5)
            alertas_relevantes = [
                (t, m) for t, m in resultado["alertas"]
                if t in ("critico", "aviso") or (t == "info" and m.startswith("🔵 CONTEXTO"))
            ]
            if alertas_relevantes:
                L("  │  ── ALERTAS DO MOTOR ──")
                for tipo, msg in alertas_relevantes:
                    if tipo == "critico":
                        prefixo = "  ❌"
                    elif tipo == "info":
                        prefixo = ""   # msg já começa com 🔵
                    else:
                        prefixo = "  ⚠️"
                    # Alerta multilinha (CONTEXTO V7.2.5): indenta corretamente
                    _msg_linhas = msg.split("\n")
                    L(f"  │ {prefixo} {_msg_linhas[0]}" if prefixo else f"  │ {_msg_linhas[0]}")
                    for _ml in _msg_linhas[1:]:
                        L(f"  │     {_ml}")
                L("  │")

            # Dados ausentes
            if resultado["dados_insuficientes"]:
                L("  │  ── DADOS NÃO FORNECIDOS ──")
                for d in resultado["dados_insuficientes"]:
                    L(f"  │  📭 {d}")
                L("  │")

            L(f"  └──────────────────────────────────────────────")
            L()

    # ── SEÇÃO 2: REJEITADOS ───────────────────────────────────────
    L("══════════════════════════════════════════════════════════════════")
    L("  SEÇÃO 2 — REJEITADOS (validar vetos + identificar exceções)")
    L("══════════════════════════════════════════════════════════════════")
    L()
    L("  INSTRUÇÃO: Para cada rejeitado, confirme se o veto é adequado")
    L("  ou se os dados ofensivos justificam exceção. Jogos marcados com")
    L("  ⚠️ ZONA CRÍTICA OFENSIVA merecem atenção especial.")
    L()

    if not rejeitados:
        L("  Nenhuma rejeição neste dia.")
        L()
    else:
        for jogo, resultado in rejeitados:
            score_rej = resultado.get("score", 0)
            b = jogo.betano
            s = jogo.superbet
            h = jogo.h2h
            motivos = resultado["motivos_rejeicao"]

            # Detectar zona crítica com dados ofensivos altos
            zona_critica_ofensiva = (
                any("zona crítica" in m.lower() or "odd" in m.lower() for m in motivos)
                and score_rej >= 60
            )

            prefixo = "⚠️  ZONA CRÍTICA OFENSIVA —" if zona_critica_ofensiva else "✗  "
            L(f"  {prefixo} {jogo.time_casa.upper()} × {jogo.time_fora.upper()}")
            L(f"     Liga: {jogo.liga}  |  Odd: {jogo.odd}  |  Score real: {score_rej}/100")
            L()

            # Motivos do veto
            L("     MOTIVO(S) DO VETO:")
            for motivo in motivos:
                L(f"     🚫 {motivo}")
            L()

            # Dados ofensivos chave (para Claude avaliar o veto)
            L("     DADOS OFENSIVOS:")
            def _f(v, mult=100, suf="%"):
                return f"{v*mult:.0f}{suf}" if v is not None else "n/d"
            def _ff(v):
                return f"{v:.2f}" if v is not None else "n/d"

            L(f"     Over 1.5 Casa : {_f(b.over15_casa_pct)}")
            L(f"     Over 1.5 Fora : {_f(b.over15_fora_pct)}")
            L(f"     xG Combinado  : {_ff((s.xg_casa or 0) + (s.xg_fora or 0)) if s.xg_casa or s.xg_fora else 'n/d'}")
            if h.total_jogos:
                L(f"     H2H Média Gols: {_ff(h.media_gols)}  |  Over 1.5 H2H: {_f(h.over15_pct)}")
                if h.resultados_recentes:
                    L(f"     H2H Recente   : {' | '.join(h.resultados_recentes)}")
            L()

            if zona_critica_ofensiva:
                L("     ► PERGUNTA PARA CLAUDE: Os dados ofensivos acima justificam")
                L("       exceção ao veto de zona crítica? Considere o contexto específico")
                L("       (derby ofensivo? times atípicos para esta liga? etc.)")
            L()
            L("     " + "─" * 60)
            L()

    # ── SEÇÃO 2B: ATENÇÃO ABAIXO DO MÍNIMO (P5 V7.2.3) ──────────
    # Jogos com ATENÇÃO mas score < 70 — antes sumiam do relatório
    if intermediarios:
        L("══════════════════════════════════════════════════════════════════")
        L("  SEÇÃO 2B — ATENÇÃO (score abaixo do mínimo — contexto explícito)")
        L("══════════════════════════════════════════════════════════════════")
        L()
        for jogo, resultado in sorted(intermediarios, key=lambda x: -x[1]["score"]):
            L(f"  ~  {jogo.time_casa} × {jogo.time_fora}")
            L(f"     Liga: {jogo.liga}  |  Odd: {jogo.odd}  |  Score: {resultado['score']}/100")
            L(f"     Cobertura: {resultado['cobertura']}%")
            L()

            # Bloco quantitativo completo (igual à Seção 1)
            b = jogo.betano
            s = jogo.superbet
            h = jogo.h2h

            def fmt2b(v, sufixo="%", mult=100):
                return f"{v*mult:.0f}{sufixo}" if v is not None else "n/d"

            def fmtf2b(v, dec=2):
                return f"{v:.{dec}f}" if v is not None else "n/d"

            L("     ── DADOS QUANTITATIVOS ──")
            L(f"     Over 1.5 Casa   : {fmt2b(b.over15_casa_pct)}")
            L(f"     Over 1.5 Fora   : {fmt2b(b.over15_fora_pct)}")
            L(f"     Over 2.5 Casa   : {fmt2b(b.over25_casa_pct)}")
            L(f"     Over 2.5 Fora   : {fmt2b(b.over25_fora_pct)}")
            L(f"     BTTS Casa       : {fmt2b(b.btts_casa_pct)}")
            L(f"     BTTS Fora       : {fmt2b(b.btts_fora_pct)}")
            L(f"     Forma Casa (5)  : {b.forma_casa or 'n/d'}")
            L(f"     Forma Fora (5)  : {b.forma_fora or 'n/d'}")
            L(f"     xG Casa         : {fmtf2b(s.xg_casa)}")
            L(f"     xG Fora         : {fmtf2b(s.xg_fora)}")
            if s.xg_casa and s.xg_fora:
                L(f"     xG Combinado    : {fmtf2b(s.xg_casa + s.xg_fora)}")
            L(f"     Gr. Chances C   : {fmtf2b(s.grandes_chances_casa, 1)}")
            L(f"     Gr. Chances F   : {fmtf2b(s.grandes_chances_fora, 1)}")
            L()

            # H2H
            if h.total_jogos:
                L("     ── H2H DIRETO ──")
                L(f"     Jogos           : {h.total_jogos}")
                L(f"     Média gols/jogo : {fmtf2b(h.media_gols)}")
                L(f"     Over 1.5 H2H    : {fmt2b(h.over15_pct)}")
                L(f"     Over 2.5 H2H    : {fmt2b(h.over25_pct)}")
                L(f"     BTTS H2H        : {fmt2b(h.btts_pct)}")
                if h.resultados_recentes:
                    L(f"     Últimos H2H     : {' | '.join(h.resultados_recentes)}")
                L()

            # Alertas do motor — positivos primeiro, negativos depois
            alertas_ok = [(t, m) for t, m in resultado.get("alertas", []) if t == "ok"]
            alertas_neg = [
                (t, m) for t, m in resultado.get("alertas", [])
                if t in ("aviso", "critico") or (t == "info" and m.startswith("🔵 CONTEXTO"))
            ]
            if alertas_ok:
                L("     ── FATORES POSITIVOS ──")
                for _, msg in alertas_ok[:6]:
                    L(f"       {msg}")
                L()
            if alertas_neg:
                L("     ── ALERTAS DO MOTOR ──")
                for tipo, msg in alertas_neg[:6]:
                    _msg_linhas = msg.split("\n")
                    L(f"       {_msg_linhas[0]}")
                    for _ml in _msg_linhas[1:]:
                        L(f"         {_ml}")
            L()

    # ── SEÇÃO 3: DADOS INSUFICIENTES ─────────────────────────────
    if sem_dados:
        L("══════════════════════════════════════════════════════════════════")
        L("  SEÇÃO 3 — DADOS INSUFICIENTES (aguardam busca manual)")
        L("══════════════════════════════════════════════════════════════════")
        L()
        for jogo, resultado in sem_dados:
            L(f"  ?  {jogo.time_casa} × {jogo.time_fora}  |  {jogo.liga}  |  Odd {jogo.odd}")
            L(f"     Score parcial: {resultado['score']}/100 — Cobertura: {resultado['cobertura']}%")
            for d in resultado["dados_insuficientes"]:
                L(f"     → Faltando: {d}")
            L()

    # ── SEÇÃO 4: BILHETES SUGERIDOS ───────────────────────────────
    L("══════════════════════════════════════════════════════════════════")
    L("  SEÇÃO 4 — BILHETES SUGERIDOS (range alvo 1.50–1.60)")
    L("══════════════════════════════════════════════════════════════════")
    L()

    if len(aprovados) >= 2:
        bilhetes = gerar_bilhetes([
            {"nome": f"{j.time_casa} × {j.time_fora}", "odd": j.odd,
             "score": r["score"], "liga": j.liga, "status": r["status"]}
            for j, r in aprovados
        ])

        if bilhetes:
            nomes_bilhete = ["OURO (60%)", "DIAMANTE (25%)", "PLATINA (15%)"]
            for i, b in enumerate(bilhetes[:3]):
                nome = nomes_bilhete[i] if i < len(nomes_bilhete) else f"BILHETE {i+1}"
                dentro = "✅ Dentro do range" if RANGE_BILHETE_MIN <= b["odd"] <= RANGE_BILHETE_MAX else "⚠️ Fora do range"
                L(f"  {nome}")
                L(f"  Odd combinada : {b['odd']}  {dentro}")
                L(f"  Score médio   : {b['score_medio']}")
                L(f"  Jogos         :")
                for jg in b["jogos"]:
                    L(f"    • {jg['nome']}  ({jg['liga']})  Odd {jg['odd']}  Score {jg['score']}")
                L()
        else:
            L("  Nenhuma combinação atingiu o range 1.50–1.60.")
            L("  Aguardar análise do Claude para definição dos bilhetes.")
            L()
    else:
        L("  Menos de 2 candidatos — não é possível montar bilhetes.")
        L()

    # ── RODAPÉ ────────────────────────────────────────────────────
    L("══════════════════════════════════════════════════════════════════")
    L("  INSTRUÇÃO AO CLAUDE")
    L("══════════════════════════════════════════════════════════════════")
    L()
    L("  Com base nos dados acima:")
    L("  1. Valide ou refute cada candidato da Seção 1")
    L("  2. Confirme ou questione as rejeições da Seção 2")
    L("  3. Solicite busca manual para itens da Seção 3 se necessário")
    L("  4. Defina os bilhetes finais do dia com stakes")
    L()
    L("  ⚠️  NUNCA aposte com base apenas neste relatório.")
    L("      A decisão final é sempre do Claude.")
    L()
    L(f"  Gerado por: ATLAS V6.9 Dashboard")
    L(f"  Patches: V6.9 · V6.9.1 · V6.9.7 · V6.9.8 · V6.9.9 · V6.9.10 · V6.9.12")
    L("══════════════════════════════════════════════════════════════════")

    return "\n".join(linhas)


def exportar_relatorio(jogos_com_resultado: list):
    """Renderiza a seção de exportação no Streamlit."""
    from datetime import datetime

    st.markdown("""
    <div style="background:linear-gradient(90deg,#0d1226,#111827);border:1px solid #1e1e2e;
         border-radius:12px;padding:20px 24px;margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
            <span style="font-size:20px">📄</span>
            <div>
                <div style="font-weight:700;font-size:15px;color:#f1f5f9">
                    Exportar relatório para o Claude
                </div>
                <div style="font-size:12px;color:#475569;margin-top:2px">
                    Gera um arquivo .txt estruturado com todos os dados analisados,
                    pronto para ser colado no chat do Claude para decisão final.
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_data, col_btn = st.columns([2, 3])

    with col_data:
        data_input = st.text_input(
            "Data da análise",
            value=datetime.now().strftime("%d/%m/%Y"),
            key="data_relatorio",
            placeholder="DD/MM/AAAA"
        )

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⬇️  Gerar relatório para o Claude", use_container_width=True,
                     type="primary", key="btn_export"):

            _data_rel = st.session_state.get("data_global", data_input) or data_input
            # jogos_com_resultado já vem consolidado (lotes salvos + lote atual) do app.py
            relatorio = gerar_relatorio_txt(jogos_com_resultado, data_analise=_data_rel)
            nome_arquivo = f"atlas_relatorio_{data_input.replace('/', '-')}.txt"

            st.download_button(
                label="📥  Baixar arquivo .txt",
                data=relatorio.encode("utf-8"),
                file_name=nome_arquivo,
                mime="text/plain",
                use_container_width=True,
                key="btn_download"
            )

            # Preview do relatório
            with st.expander("👁️  Preview do relatório gerado", expanded=True):
                st.code(relatorio, language=None)

            st.markdown("""
            <div style="background:#064e3b22;border:1px solid #10b981;border-radius:8px;
                 padding:12px 16px;margin-top:8px;font-size:12px;color:#6ee7b7">
                ✅ Relatório gerado. Baixe o arquivo e cole o conteúdo no chat do Claude
                com a mensagem: <strong>"Analise o relatório do Atlas e tome a decisão final."</strong>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
