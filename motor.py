"""
atlas/motor.py
Motor de análise ATLAS V7.2 — Over 1.5 Gols.
Entrada: objeto Jogo. Saída: dict com score, status, motivos, detalhes.
"""

from __future__ import annotations
import re
from typing import Optional
from itertools import combinations

from atlas.config import (
    Jogo, DadosBetano, DadosSuperbet, DadosH2H,
    DadosContexto, FormaRecente, UltimosJogosSuperbet,
    HIERARQUIA_LIGAS, BLACKLIST_TIMES_VISITANTE, BLACKLIST_LIGAS,
    EXCECAO_ZONA_CRITICA, TIMES_ULTRA_OFENSIVOS_HOLANDA,
    LIGAS_OVER_INDIVIDUAL_OBRIGATORIO, OVER_CASA_MIN_SCORE_100,
    RANGE_ODD_MIN, RANGE_ODD_MAX, OVER_INDIVIDUAL_MIN,
    PROB_MINIMA_APROVACAO, _is_visitante_t1,
)

# ══════════════════════════════════════════════════════════════════
#  MOTOR DE ANÁLISE ATLAS V6.9
# ══════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────
#  DERBIES CONHECIDOS — (time_a, time_b, ofensivo)
#  Detecção automática: se ambos os times do jogo estiverem na lista
#  o derby é marcado automaticamente. O usuário pode sobrescrever.
# ─────────────────────────────────────────────────────────────────
DERBIES_CONHECIDOS = [
    # ── HOLANDA — ofensivos (validados: 100% Over histórico em derbies) ──────
    ("Ajax", "Feyenoord",           True),
    ("Ajax", "PSV",                 True),
    ("Feyenoord", "PSV",            True),
    ("Ajax", "Utrecht",             True),
    ("Feyenoord", "Sparta Rotterdam", True),
    ("PSV", "FC Eindhoven",         True),
    ("AZ", "Heerenveen",            True),
    ("Twente", "NEC Nijmegen",      True),
    # ── TURQUIA — ofensivos (Süper Lig Tier S+, clássicos historicamente abertos) ──
    ("Galatasaray", "Fenerbahce",   True),
    ("Galatasaray", "Besiktas",     True),
    ("Fenerbahce", "Besiktas",      True),
    # ── ESPANHA — derbies premium individuais validados ───────────────────────
    # V7.1.5: Derby de Sevilha promovido para ofensivo (2-2 em 01/03/2026,
    # histórico consistente de gols no clássico andaluz)
    ("Sevilla", "Real Betis",       True),   # Derby de Sevilha — ofensivo confirmado
    ("Betis", "Sevilla",            True),
    ("Real Betis", "Sevilla FC",    True),
    ("Real Madrid", "Atletico Madrid",  False),
    ("Real Madrid", "Barcelona",        False),
    ("Barcelona", "Espanyol",           False),
    ("Valencia", "Villarreal",          False),
    ("Athletic Club", "Real Sociedad",  False),
    # ── INGLATERRA — derbies premium (buscar H2H antes de aplicar -10, V6.9.5) ─
    # Marcados False mas Claude deve verificar H2H específico antes de confirmar
    ("Arsenal", "Tottenham",        False),   # North London — histórico ofensivo (V6.9.5)
    ("Chelsea", "Tottenham",        False),
    ("Chelsea", "Arsenal",          False),
    ("Manchester City", "Manchester United", False),
    ("Liverpool", "Everton",        False),
    ("Newcastle", "Sunderland",     False),
    ("Aston Villa", "Birmingham City", False),
    ("Leeds United", "Sheffield United", False),
    ("West Ham", "Millwall",        False),
    # ── ITÁLIA ────────────────────────────────────────────────────────────────
    ("Inter", "AC Milan",           False),
    ("Inter de Milão", "AC Milan",  False),
    ("Roma", "Lazio",               False),
    ("Juventus", "Torino",          False),
    ("Napoli", "Roma",              False),
    ("Genoa", "Sampdoria",          False),
    # ── ALEMANHA ──────────────────────────────────────────────────────────────
    ("Borussia Dortmund", "Schalke 04", False),
    ("Borussia Dortmund", "Bayer Leverkusen", False),
    ("Bayern Munich", "1860 Munich", False),
    ("Hamburg", "Werder Bremen",    False),
    ("Stuttgart", "Karlsruher SC",  False),
    ("Köln", "Borussia Monchengladbach", False),
    # ── FRANÇA ────────────────────────────────────────────────────────────────
    ("Paris Saint Germain", "Marseille", False),
    ("PSG", "Marseille",            False),
    ("Lyon", "Saint-Etienne",       False),
    ("Nice", "Monaco",              False),
    # ── PORTUGAL ──────────────────────────────────────────────────────────────
    ("Benfica", "Sporting Lisboa",  False),
    ("Benfica", "Porto",            False),
    ("Sporting Lisboa", "Porto",    False),
    # ── BRASIL ────────────────────────────────────────────────────────────────
    ("Flamengo", "Fluminense",      False),
    ("Flamengo", "Vasco da Gama",   False),
    ("Corinthians", "Palmeiras",    False),
    ("Corinthians", "São Paulo",    False),
    ("Grêmio", "Internacional",     False),
    ("Atletico Mineiro", "Cruzeiro", False),
    # ── DINAMARCA — padrão conservador até documentar histórico ───────────────
    # V7.1.2: Derbies da Superliga Dinamarca marcados como False (padrão)
    # até atingir ≥ 5 derbies analisados com taxa ≥ 80%.
    # Evidência negativa: Midtjylland × Brøndby 0-0 (01/03/2026) — Derby marcado
    # erroneamente como ofensivo → resultado: 0-0.
    ("FC Midtjylland", "Brøndby IF",    False),
    ("Brøndby IF", "FC Copenhagen",     False),
    ("FC Copenhagen", "FC Midtjylland", False),
]

def detectar_derby(time_casa: str, time_fora: str):
    """
    Retorna (e_derby, derby_ofensivo) detectando automaticamente
    pelo nome dos times. Case-insensitive e tolerante a variações.
    """
    tc = time_casa.lower().strip()
    tf = time_fora.lower().strip()
    for a, b, ofensivo in DERBIES_CONHECIDOS:
        al, bl = a.lower(), b.lower()
        if (al in tc or tc in al) and (bl in tf or tf in bl):
            return True, ofensivo
        if (bl in tc or tc in bl) and (al in tf or tf in al):
            return True, ofensivo
    return False, False

class MotorAtlas:

    def __init__(self, jogo: Jogo):
        self.jogo = jogo
        self.alertas = []          # (tipo, mensagem) — tipo: critico|aviso|ok|info
        self.motivos_rejeicao = []
        self.pontos = 0
        self.score_final = 0
        self.status = "PENDENTE"   # APROVADO | REJEITADO | ATENÇÃO | DADOS INSUFICIENTES
        self.cobertura_dados = 0   # 0-100% de dados disponíveis
        self.detalhes_fases = {}
        self.dados_insuficientes = []

    # ──────────────────────────────────────────
    #  FASE 1: BLACKLISTS ABSOLUTAS
    # ──────────────────────────────────────────
    def _fase1_blacklists(self) -> bool:
        j = self.jogo

        # Único veto absoluto de odd: matematicamente sem valor
        if j.odd < 1.05:
            self.motivos_rejeicao.append(f"Odd {j.odd} — sem valor matemático (<1.05)")
            self.alertas.append(("critico", f"❌ Odd {j.odd} — impossível ter valor esperado positivo"))
            return False

        # Alertas informativos de odd (não rejeitam)
        if j.odd < 1.10:
            self.alertas.append(("aviso", f"⚠️ Odd {j.odd} muito baixa — avaliar com cuidado"))
        elif j.odd < 1.18:
            self.alertas.append(("info", f"🔵 Odd {j.odd} — zona de atenção, dados ofensivos são decisivos"))
        elif j.odd > 1.50:
            self.alertas.append(("aviso", f"⚠️ Odd {j.odd} alta para Over 1.5 — verificar H2H e xG"))
        else:
            self.alertas.append(("ok", f"✅ Odd {j.odd} — range adequado"))

        # Liga blacklist — intacta
        liga_info = BLACKLIST_LIGAS.get(j.liga)
        if liga_info:
            self.motivos_rejeicao.append(f"Liga {j.liga} — {liga_info}")
            self.alertas.append(("critico", f"❌ {j.liga} — Blacklist de liga"))
            return False

        # Time visitante blacklist — intacta
        visitante_bl = BLACKLIST_TIMES_VISITANTE.get(j.time_fora)
        if visitante_bl:
            if j.time_fora == "Freiburg" and j.tipo_competicao == "Copa":
                self.alertas.append(("aviso", "⚠️ Freiburg visitante em Copa — pode atacar"))
            else:
                self.motivos_rejeicao.append(f"{j.time_fora} — {visitante_bl}")
                self.alertas.append(("critico", f"❌ {j.time_fora} visitante — Blacklist de time"))
                return False

        return True

    # ──────────────────────────────────────────
    #  FASE 2: ZONA CRÍTICA (1.08–1.18)
    # ──────────────────────────────────────────
    def _fase2_zona_critica(self) -> int:
        """
        Odd baixa vira penalidade de score (0 a -20), não rejeição.
        Claude decide com base no score total + contexto.
        """
        j = self.jogo
        if j.odd >= 1.18:
            return 0  # Sem penalidade

        liga_taxa = HIERARQUIA_LIGAS.get(j.liga, {}).get("taxa", 0)

        # Contextos sem penalidade
        # Holanda: time ultra ofensivo + H2H alto
        if j.liga in {"Eredivisie", "Eerste Divisie"}:
            time_ultra = j.time_casa in TIMES_ULTRA_OFENSIVOS_HOLANDA
            h2h_ok = (j.h2h.media_gols or 0) >= 2.5
            if time_ultra and h2h_ok:
                self.alertas.append(("ok",
                    f"✅ Holanda: time ultra ofensivo + H2H {j.h2h.media_gols} — odd baixa justificada"))
                return 0
            pen = -5 if time_ultra else -12
            self.alertas.append(("info",
                f"🔵 Odd {j.odd} Holanda — {'time documentado mas H2H baixo' if time_ultra else 'time não documentado como ultra ofensivo'}"))
            return pen

        # CL volta obrigado a atacar
        if j.tipo_competicao == "CL_Volta":
            situacao = self._classificar_situacao_cl()
            if situacao in ("A", "A_EXTREMA", "BORDERLINE_A"):
                self.alertas.append(("ok", f"✅ CL Volta Situação {situacao} — odd baixa justificada"))
                return 0

        # Ligas de alto tier com favoritos naturais: penalidade leve
        if j.liga in {"Bundesliga", "Serie A", "La Liga", "Premier League",
                      "Eredivisie", "Süper Lig", "Liga Portugal"}:
            self.alertas.append(("info",
                f"🔵 Odd {j.odd} em {j.liga} — normal para favoritos. Score reflete risco."))
            return -8

        # Liga com taxa histórica ≥ 82%: penalidade moderada
        if liga_taxa >= 0.82:
            self.alertas.append(("info",
                f"🔵 Odd {j.odd} em liga com taxa {liga_taxa*100:.0f}% — penalidade reduzida"))
            return -10

        # Outros casos: penalidade maior mas não rejeição
        self.alertas.append(("aviso",
            f"⚠️ Odd {j.odd} em {j.liga} (taxa {liga_taxa*100:.0f}%) — risco elevado, score penalizado"))
        return -18

    # ──────────────────────────────────────────
    #  CLASSIFICAÇÃO SITUAÇÃO CL VOLTA
    # ──────────────────────────────────────────
    def _classificar_situacao_cl(self) -> str:
        ag = self.jogo.contexto.agregado_cl
        if not ag:
            return "DESCONHECIDA"
        try:
            partes = ag.replace(" ", "").split("-")
            gols_casa_ag = int(partes[0])
            gols_fora_ag = int(partes[1])
            diff = gols_casa_ag - gols_fora_ag
            # diff > 0 = casa vencendo no agregado
            if diff <= -1:   return "A"           # Perdendo — obrigado a atacar
            if diff == 0:    return "A"           # Empatado — jogo aberto
            if diff == 1:    return "BORDERLINE_A"  # Vencendo por 1
            if diff == 2:    return "BORDERLINE_B"  # Vencendo por 2 — cautela
            return "B"                            # Vencendo por 3+ — vai poupar
        except:
            return "DESCONHECIDA"

    # ──────────────────────────────────────────
    #  FASE 3: CALENDÁRIO EUROPEU
    # ──────────────────────────────────────────
    def _fase3_calendario(self):
        j = self.jogo
        penalidade = 0

        if j.contexto.tem_cl_proximos_3_dias:
            penalidade -= 25
            self.alertas.append(("critico", "❌ CL/EL nos próximos 3 dias — poupança esperada (-25 pts)"))
        if j.contexto.tem_el_proximos_4_dias:
            penalidade -= 15
            self.alertas.append(("aviso", "⚠️ Europa League nos próximos 4 dias (-15 pts)"))

        if penalidade == 0:
            self.alertas.append(("ok", "✅ Calendário europeu: sem conflito"))

        return penalidade

    # ──────────────────────────────────────────
    #  FASE 4: CONTEXTO REBAIXAMENTO
    # ──────────────────────────────────────────
    def _fase4_rebaixamento(self) -> tuple:
        """
        Rebaixamento adaptativo — calcula risco por % da tabela.

        Regras:
          - Se posição + total_times_liga informados: calcula % automaticamente
            - Último 22%  → zona de rebaixamento (ex: 16º-18º na Bundesliga)
            - Penúltimo 33% → zona de atenção (estressado mas não rebaixamento)
          - Se não informados: usa flag manual casa_zona_rebaixamento / fora_zona_rebaixamento
          - Ambos em rebaixamento real → rejeição imediata

        Início de temporada (tabela provisória):
          - ≤ 4 jogos: veto suspenso, penalidades eliminadas, aviso informativo
          - 5–8 jogos: penalidades reduzidas a 50%, veto mantido apenas se ambos
                       tiverem ≤ 1 vitória combinada
          - > 8 jogos: comportamento padrão completo
        """
        j = self.jogo
        ctx = j.contexto
        n = ctx.total_times_liga

        # ── Detectar início de temporada ─────────────────────────────
        # Fonte primária: denominador Betano (over15_casa_n / over15_fora_n)
        #   → número exato de jogos usados para calcular o %, máx 5-6 pela Betano
        # Fonte secundária: n_jogos D12 Superbet
        # Conservador: se nenhuma fonte disponível → assume consolidada (não relaxa)
        _nj_bet_c = j.betano.over15_casa_n if j.betano.over15_casa_n else 0
        _nj_bet_f = j.betano.over15_fora_n if j.betano.over15_fora_n else 0
        _nj_d12_c = j.ultimos_jogos.n_jogos_casa if j.ultimos_jogos else 0
        _nj_d12_f = j.ultimos_jogos.n_jogos_fora if j.ultimos_jogos else 0

        # Usar o maior valor disponível por time (Betano ou D12)
        _nj_c = max(_nj_bet_c or 0, _nj_d12_c or 0)
        _nj_f = max(_nj_bet_f or 0, _nj_d12_f or 0)
        # Maturidade pela melhor fonte disponível
        _nj_max = max(_nj_c, _nj_f)
        _tem_fonte = _nj_max > 0

        if not _tem_fonte:
            _maturidade = "consolidada"  # sem dados → conservador, aplica penalidades
        elif _nj_max <= 4:
            _maturidade = "provisoria"   # tabela sem sinal real (≤4 jogos)
        elif _nj_max <= 8:
            _maturidade = "formacao"     # tabela em formação (5–8 jogos)
        else:
            _maturidade = "consolidada"

        def calcular_risco(posicao):
            if posicao is None or n is None:
                return "desconhecido"
            pct = posicao / n
            if pct >= 0.78:  # últimos 22%
                return "rebaixamento"
            elif pct >= 0.67:  # 67-78%
                return "atencao"
            elif pct >= 0.56:  # 56-67%
                return "baixo"
            return "ok"

        risco_casa = calcular_risco(ctx.casa_posicao)
        risco_fora = calcular_risco(ctx.fora_posicao)

        # Usar flag manual como fallback
        if risco_casa == "desconhecido" and ctx.casa_zona_rebaixamento:
            risco_casa = "rebaixamento"
        if risco_fora == "desconhecido" and ctx.fora_zona_rebaixamento:
            risco_fora = "rebaixamento"

        # Exibir posição contextual se disponível
        if ctx.casa_posicao and n:
            self.alertas.append(("info", f"🔵 Mandante: {ctx.casa_posicao}º/{n} ({ctx.casa_posicao/n*100:.0f}% da tabela)"))
        if ctx.fora_posicao and n:
            self.alertas.append(("info", f"🔵 Visitante: {ctx.fora_posicao}º/{n} ({ctx.fora_posicao/n*100:.0f}% da tabela)"))

        # ── Tabela provisória (≤ 4 jogos): ignorar posição ──────────
        if _maturidade == "provisoria":
            _ambos = risco_casa == "rebaixamento" and risco_fora == "rebaixamento"
            if _ambos:
                self.alertas.append(("aviso",
                    f"⚠️ Ambos na zona inferior — tabela provisória ({_nj_max} jgs), "
                    f"posição desconsiderada [início de temporada]"))
            elif risco_casa == "rebaixamento" or risco_fora == "rebaixamento":
                self.alertas.append(("info",
                    f"🔵 Zona inferior na tabela provisória ({_nj_max} jgs) — "
                    f"posição irrelevante, dado desconsiderado [início de temporada]"))
            else:
                self.alertas.append(("ok", "✅ Contexto de tabela: sem alerta"))
            return True, 0  # sem veto, sem penalidade

        # ── Tabela em formação (5–8 jogos): penalidades 50% ─────────
        fator = 1.0 if _maturidade == "consolidada" else 0.5

        # Ambos em rebaixamento — veto apenas se temporada consolidada
        if risco_casa == "rebaixamento" and risco_fora == "rebaixamento":
            if _maturidade == "consolidada":
                self.motivos_rejeicao.append("Ambos em zona de rebaixamento — jogo truncado (Nottingham 0-0, Düsseldorf 0-0)")
                self.alertas.append(("critico", "❌ Ambos em rebaixamento — rejeição imediata"))
                return False, 0
            else:
                self.alertas.append(("aviso",
                    f"⚠️ Ambos na zona de rebaixamento — tabela em formação ({_nj_max} jgs), "
                    f"penalidades reduzidas a 50% [V7.2]"))

        penalidade = 0
        # Item 4 V7.2: mandante rebaixado = neutro para Over.
        if risco_casa == "rebaixamento":
            self.alertas.append(("info",
                f"🔵 Mandante em rebaixamento ({ctx.casa_posicao}º/{n}) — neutro para Over "
                f"(pressão por pontos em casa) [V7.2 Item 4]"))
        elif risco_casa == "atencao":
            pen = round(-8 * fator)
            penalidade += pen
            self.alertas.append(("aviso",
                f"⚠️ Mandante em zona de atenção ({ctx.casa_posicao}º/{n}) ({pen} pts"
                + (" — tabela em formação" if fator < 1 else "") + ")"))
        elif risco_casa == "baixo":
            pen = round(-3 * fator)
            penalidade += pen
            self.alertas.append(("info", f"🔵 Mandante na metade inferior ({ctx.casa_posicao}º/{n}) ({pen} pts)"))

        if risco_fora == "rebaixamento":
            pen = round(-8 * fator)
            # [V7.2 Fix] Se Over fora do visitante ≥ 70%, a hipótese de retrança
            # é refutada pelo dado empírico — penalidade neutralizada.
            over_fora_visit = j.betano.over15_fora_pct
            if over_fora_visit is not None and over_fora_visit >= 0.70:
                self.alertas.append(("info",
                    f"🔵 Visitante em rebaixamento ({ctx.fora_posicao}º/{n}), mas Over fora "
                    f"{over_fora_visit*100:.0f}% ≥ 70% — retrança refutada, penalidade neutralizada (V7.2 Fix)"))
            else:
                penalidade += pen
                self.alertas.append(("aviso",
                    f"⚠️ Visitante em rebaixamento ({ctx.fora_posicao}º/{n}) — pode retrançar ({pen} pts"
                    + (" — tabela em formação" if fator < 1 else "") + ")"))
        elif risco_fora == "atencao":
            pen = round(-4 * fator)
            penalidade += pen
            self.alertas.append(("info",
                f"🔵 Visitante em zona de atenção ({ctx.fora_posicao}º/{n}) ({pen} pts)"))

        if penalidade == 0:
            self.alertas.append(("ok", "✅ Contexto de tabela: sem alerta"))

        return True, penalidade

    # ──────────────────────────────────────────
    #  FASE 5: OVER INDIVIDUAL (V6.9 CRÍTICO)
    # ──────────────────────────────────────────
    def _fase5_over_individual(self) -> tuple:
        """
        Fase 5 — Over Individual (V6.9 crítico + patches V7.1.1 e V7.1.3)

        V6.9  : Over casa < 70% → rejeição mandatória (regra base)
        V7.1.1: Exceção se visitante T1 ultra ofensivo (Over fora ≥ 85% + xG fora ≥ 1.8)
                → não rejeita, aplica penalidade de -25 pts
                Evidências: Roma 54%→3-3 Juventus, Cremonese 65%→0-2 Milan (01/03/2026)
        V7.1.3: Para ligas Tier S+ (Süper Lig, Eredivisie, Copa del Rey),
                Over individual desconhecido = rejeição conservadora.
                Taxa histórica da liga NÃO compensa dado ausente.
                Evidências: Genclerbirligi e Samsunspor 0-0 (01/03/2026)
        Item 9 V7.2: Quando copa_inter, usar dado por competição (FootyStats) se disponível.
                Caso Atlético Madrid UCL=100% vs La Liga=74% — dado global inútil.
        """
        j = self.jogo

        # Item 9 V7.2 — preferir dado por competição quando disponível
        _tem_comp_casa = j.betano.over15_mandante_comp is not None
        _tem_comp_fora = j.betano.over15_visitante_comp is not None

        over_casa = j.betano.over15_mandante_comp if _tem_comp_casa else j.betano.over15_casa_pct
        over_fora = j.betano.over15_visitante_comp if _tem_comp_fora else j.betano.over15_fora_pct

        if _tem_comp_casa:
            self.alertas.append(("ok",
                f"✅ Over 1.5 mandante — dado geral nesta competição (FootyStats): "
                f"{over_casa*100:.0f}% [substitui global da Betano — V7.2 Item 9] "
                f"⚠️ Dado geral (sem separar casa/fora)"))
        elif j.tipo_competicao == "copa_inter" and j.betano.over15_casa_pct is not None:
            self.alertas.append(("aviso",
                f"⚠️ Over 1.5 mandante — dado global da Betano ({j.betano.over15_casa_pct*100:.0f}%) "
                f"pode incluir campeonato doméstico. Verifique FootyStats [V7.2 Item 9]"))

        if _tem_comp_fora:
            self.alertas.append(("ok",
                f"✅ Over 1.5 visitante — dado geral nesta competição (FootyStats): "
                f"{over_fora*100:.0f}% [substitui global da Betano — V7.2 Item 9] "
                f"⚠️ Dado geral (sem separar casa/fora)"))
        elif j.tipo_competicao == "copa_inter" and j.betano.over15_fora_pct is not None:
            self.alertas.append(("aviso",
                f"⚠️ Over 1.5 visitante — dado global da Betano ({j.betano.over15_fora_pct*100:.0f}%) "
                f"pode incluir jogos de campeonato. Verifique FootyStats [V7.2 Item 9]"))

        penalidade = 0
        bonus = 0

        # ── Over individual do mandante ─────────────────────────────────────
        if over_casa is None:
            # V7.1.3: ligas S+ sem dado = rejeição conservadora
            if j.liga in LIGAS_OVER_INDIVIDUAL_OBRIGATORIO:
                self.motivos_rejeicao.append(
                    f"Over individual do mandante não confirmado em liga Tier S+ ({j.liga}) "
                    f"— rejeição conservadora V7.1.3 (Genclerbirligi/Samsunspor 0-0)"
                )
                self.alertas.append((
                    "critico",
                    f"❌ Over casa ausente em {j.liga} (Tier S+) — V7.1.3 rejeição conservadora"
                ))
                return False, 0
            else:
                # ── P3 V7.2.5 — Dado ausente + análise contextual ──────────────
                # Over casa N/A não é dado negativo — é ausência de informação.
                # Quando contexto é favorável, manter rejeição mas mostrar análise
                # completa para decisão qualitativa do Claude.
                self.dados_insuficientes.append("Over 1.5 casa (Betano — obrigatório V6.9)")
                self.alertas.append(("aviso", "⚠️ Over individual casa não informado — dado ausente (não negativo)"))

                # Avaliar sinais contextuais disponíveis
                _tier = HIERARQUIA_LIGAS.get(j.liga, {}).get("tier", "?")
                _xg_comb = (j.superbet.xg_casa or 0) + (j.superbet.xg_fora or 0)
                _over_fora_val = j.betano.over15_fora_pct
                _ctx_favor = []
                _ctx_contra = []

                if _tier in ("S+", "S", "A"):
                    _ctx_favor.append(f"Liga Tier {_tier} ({j.liga}) — historicamente ofensiva")
                else:
                    _ctx_contra.append(f"Liga Tier {_tier} — contexto ofensivo incerto")

                if _xg_comb >= 3.0:
                    _ctx_favor.append(f"xG combinado {_xg_comb:.1f} ≥ 3.0 — perfil altamente ofensivo")
                elif _xg_comb >= 2.0:
                    _ctx_favor.append(f"xG combinado {_xg_comb:.1f} — perfil ofensivo moderado")
                elif _xg_comb > 0:
                    _ctx_contra.append(f"xG combinado {_xg_comb:.1f} — perfil ofensivo fraco")

                if _over_fora_val is not None:
                    if _over_fora_val >= 0.70:
                        _ctx_favor.append(f"Over fora visitante {_over_fora_val*100:.0f}% ≥ 70% — visitante ofensivo confirmado")
                    elif _over_fora_val >= 0.50:
                        _ctx_favor.append(f"Over fora visitante {_over_fora_val*100:.0f}% — moderado")
                    else:
                        _ctx_contra.append(f"Over fora visitante {_over_fora_val*100:.0f}% — baixo")

                # Forma recente do mandante
                _forma = j.forma_casa
                if _forma and _forma.jogos_com_gol is not None and _forma.total_jogos_amostra:
                    _total_f = _forma.total_jogos_amostra
                    _com_gol_f = _forma.jogos_com_gol
                    _pct_over_forma = _com_gol_f / _total_f
                    if _pct_over_forma >= 0.60:
                        _ctx_favor.append(
                            f"Mandante: {_com_gol_f}/{_total_f} jogos c/ gol "
                            f"({_pct_over_forma*100:.0f}%) — forma ofensiva recente"
                        )
                    elif _pct_over_forma <= 0.30:
                        _ctx_contra.append(
                            f"Mandante: apenas {_com_gol_f}/{_total_f} jogos c/ gol "
                            f"({_pct_over_forma*100:.0f}%) — forma ofensiva fraca"
                        )

                # Montar alerta contextual consolidado
                if _ctx_favor:
                    _linhas = "\n       ".join(f"  ✅ {s}" for s in _ctx_favor)
                    if _ctx_contra:
                        _linhas += "\n       " + "\n       ".join(f"  ⚠️ {s}" for s in _ctx_contra)
                    self.alertas.append((
                        "info",
                        f"🔵 CONTEXTO (V7.2.5) — Over casa ausente mas contexto sugere Over 1.5:\n"
                        f"       {_linhas}\n"
                        f"       → Mantendo rejeição. Decisão qualitativa final: Claude."
                    ))
                else:
                    self.alertas.append(("info", "🔵 CONTEXTO (V7.2.5) — Over casa ausente, contexto não é favorável"))

        elif over_casa < OVER_INDIVIDUAL_MIN:
            # ── P1 V7.2.3 — Copa sem histórico em casa ──────────────────────────
            # Over casa = 0% pode significar "0 jogos em casa nesta Copa"
            # não "jogou e não teve Over". São coisas completamente diferentes.
            # Barcelona × Atlético 03/03/2026: vetado por 0% que era 0 jogos → 3-0
            copa_sem_casa = (
                j.tipo_competicao == "Copa"
                and j.betano.over15_casa_n is not None
                and j.betano.over15_casa_n == 0
            )
            if copa_sem_casa:
                # Usar taxa da liga como proxy + penalidade por dado ausente
                taxa_liga = HIERARQUIA_LIGAS.get(j.liga, {}).get("taxa", 0.75)
                pen_sem_hist = -8
                penalidade += pen_sem_hist
                self.alertas.append((
                    "aviso",
                    f"⚠️ Over casa 0% = SEM JOGOS EM CASA nesta Copa — "
                    f"dado ausente, NÃO é rejeição mandatória (P1 V7.2.3). "
                    f"Usando taxa da liga ({taxa_liga*100:.0f}%) como proxy ({pen_sem_hist} pts)"
                ))
            else:
                # ── P2 V7.2.4 — Copa internacional: threshold reduzido ──────────
                # Copas internacionais (UCL/UEL/UECL) têm poucos jogos em casa
                # por temporada (2-4 no máximo). Over casa 60% com xG combinado
                # alto NÃO é sinal fraco — é amostra mínima + perfil ofensivo real.
                # Evidência: Galatasaray 60% casa UCL → xG 4.40, Osimhen 7 gols UCL.
                # Threshold: 55% (em vez de 70%) + xG combinado ≥ 3.5 → ATENÇÃO
                # Se over_casa ≥ 55% mas < 70% e xG_comb < 3.5 → rejeição normal
                xg_casa  = j.superbet.xg_casa  or 0
                xg_fora_ = j.superbet.xg_fora  or 0
                xg_comb  = xg_casa + xg_fora_
                copa_inter_excecao = (
                    j.tipo_competicao == "copa_inter"
                    and over_casa >= 0.55
                    and xg_comb >= 3.5
                )

                if copa_inter_excecao:
                    pen_copa = -15
                    penalidade += pen_copa
                    self.alertas.append((
                        "aviso",
                        f"⚠️ Over casa {over_casa*100:.0f}% < 70% — copa internacional com "
                        f"xG combinado alto ({xg_comb:.1f} ≥ 3.5). Threshold reduzido para 55% "
                        f"(V7.2.4) — amostra em casa limitada nesta fase. Penalidade {pen_copa} pts."
                    ))
                    # Bloco contextual V7.2.5 — mesmo formato, dado presente mas amostra pequena
                    _tier = HIERARQUIA_LIGAS.get(j.liga, {}).get("tier", "?")
                    _ctx_favor = []
                    _ctx_contra = []
                    if _tier in ("S+", "S", "A"):
                        _ctx_favor.append(f"Liga Tier {_tier} ({j.liga}) — historicamente ofensiva")
                    if xg_comb >= 3.0:
                        _ctx_favor.append(f"xG combinado {xg_comb:.1f} ≥ 3.0 — perfil altamente ofensivo")
                    elif xg_comb >= 2.0:
                        _ctx_favor.append(f"xG combinado {xg_comb:.1f} — perfil ofensivo moderado")
                    _over_fora_v = j.betano.over15_fora_pct
                    if _over_fora_v is not None:
                        if _over_fora_v >= 0.70:
                            _ctx_favor.append(f"Over fora visitante {_over_fora_v*100:.0f}% ≥ 70% — visitante ofensivo confirmado")
                        elif _over_fora_v >= 0.50:
                            _ctx_favor.append(f"Over fora visitante {_over_fora_v*100:.0f}% — moderado")
                        else:
                            _ctx_contra.append(f"Over fora visitante {_over_fora_v*100:.0f}% — baixo")
                    _forma = j.forma_casa
                    if _forma and _forma.jogos_com_gol is not None and _forma.total_jogos_amostra:
                        _total_f = _forma.total_jogos_amostra
                        _com_gol_f = _forma.jogos_com_gol
                        _pct_ov = _com_gol_f / _total_f
                        if _pct_ov >= 0.60:
                            _ctx_favor.append(f"Mandante: {_com_gol_f}/{_total_f} jogos c/ gol ({_pct_ov*100:.0f}%) — forma ofensiva recente")
                        elif _pct_ov <= 0.30:
                            _ctx_contra.append(f"Mandante: apenas {_com_gol_f}/{_total_f} jogos c/ gol ({_pct_ov*100:.0f}%) — forma ofensiva fraca")
                    _n_jogos_casa = j.betano.over15_casa_n or 0
                    _ctx_contra.append(f"Amostra em casa limitada: {_n_jogos_casa} jogo(s) nesta fase — Over {over_casa*100:.0f}% pouco representativo")
                    if _ctx_favor:
                        _linhas_ctx = "\n       ".join(f"  ✅ {s}" for s in _ctx_favor)
                        if _ctx_contra:
                            _linhas_ctx += "\n       " + "\n       ".join(f"  ⚠️ {s}" for s in _ctx_contra)
                        self.alertas.append((
                            "info",
                            f"🔵 CONTEXTO (V7.2.5) — Over casa presente mas amostra pequena — contexto sugere Over 1.5:\n"
                            f"       {_linhas_ctx}\n"
                            f"       → Score com penalidade {pen_copa} pts. Decisão final: Claude."
                        ))
                else:
                    # Verificar exceção V7.1.1 — visitante T1 ultra ofensivo
                    xg_fora = j.superbet.xg_fora or 0
                    visitante_t1 = _is_visitante_t1(j.time_fora, j.liga)
                    excecao_t1 = (
                        visitante_t1
                        and over_fora is not None
                        and over_fora >= 0.85
                        and xg_fora >= 1.8
                    )

                    if excecao_t1:
                        # Não rejeita — penalidade forte de -25 pts
                        pen_t1 = -25
                        penalidade += pen_t1
                        self.alertas.append((
                            "aviso",
                            f"⚠️ Over casa {over_casa*100:.0f}% < 70% MAS visitante T1 ultra ofensivo "
                            f"(Over fora {over_fora*100:.0f}%, xG {xg_fora:.1f}) — "
                            f"penalidade -25 pts ao invés de rejeição (V7.1.1)"
                        ))
                        self.alertas.append((
                            "info",
                            f"🔵 Over depende 100% do visitante — Claude deve validar "
                            f"(evidência: Roma 54%→3-3 Juve, Cremonese 65%→0-2 Milan)"
                        ))
                    else:
                        # Rejeição mandatória V6.9
                        self.motivos_rejeicao.append(
                            f"Over individual casa {over_casa*100:.1f}% < 70% mínimo (V6.9) — rejeição mandatória"
                        )
                        self.alertas.append((
                            "critico",
                            f"❌ Over casa {over_casa*100:.0f}% abaixo de 70% — V6.9 rejeição mandatória "
                            f"(Milan 69.2%→0-1, Konyaspor 57%→0-0, Goztepe 57%→0-0)"
                        ))
                        return False, 0

        else:
            # Over casa ≥ 70% — calcular bônus
            if over_casa >= 0.90:
                bonus += 20
                self.alertas.append(("ok", f"✅ Over casa {over_casa*100:.0f}% — excelente (+20 pts)"))
            elif over_casa >= 0.80:
                bonus += 15
                self.alertas.append(("ok", f"✅ Over casa {over_casa*100:.0f}% — bom (+15 pts)"))
            else:
                bonus += 10
                self.alertas.append(("ok", f"✅ Over casa {over_casa*100:.0f}% — ok (+10 pts)"))

        # ── Over individual do visitante ────────────────────────────────────
        if over_fora is None:
            self.dados_insuficientes.append("Over 1.5 fora (Betano)")
            self.alertas.append(("info", "🔵 Over individual fora não informado"))
        else:
            if over_fora >= 0.80:
                bonus += 15
                self.alertas.append(("ok", f"✅ Over fora {over_fora*100:.0f}% — excelente (+15 pts)"))
            elif over_fora >= 0.60:
                bonus += 10
                self.alertas.append(("ok", f"✅ Over fora {over_fora*100:.0f}% — ok (+10 pts)"))
            elif over_fora <= 0.40:
                penalidade -= 15
                self.alertas.append(("aviso", f"⚠️ Over fora {over_fora*100:.0f}% — baixo (-15 pts)"))

        return True, bonus + penalidade

    # ──────────────────────────────────────────
    #  FASE 6: H2H
    # ──────────────────────────────────────────
    def _fase6_h2h(self) -> int:
        j = self.jogo
        score = 0

        if j.h2h.media_gols is None and j.h2h.over15_pct is None and j.h2h.btts_pct is None:
            self.dados_insuficientes.append("H2H (média gols, Over%, BTTS)")
            self.alertas.append(("aviso", "⚠️ Dados H2H não informados — peso reduzido na análise"))
            return 0

        # Média de gols H2H
        if j.h2h.media_gols is not None:
            if j.h2h.media_gols >= 3.5:
                score += 20
                self.alertas.append(("ok", f"✅ H2H {j.h2h.media_gols:.2f} gols/jogo — explosivo (+20 pts)"))
            elif j.h2h.media_gols >= 2.5:
                score += 12
                self.alertas.append(("ok", f"✅ H2H {j.h2h.media_gols:.2f} gols/jogo — favorável (+12 pts)"))
            elif j.h2h.media_gols >= 2.0:
                score += 5
                self.alertas.append(("info", f"🔵 H2H {j.h2h.media_gols:.2f} gols/jogo — moderado (+5 pts)"))
            else:
                score -= 12
                self.alertas.append(("aviso", f"⚠️ H2H {j.h2h.media_gols:.2f} gols/jogo — baixo (-12 pts)"))

        # Over 1.5% H2H
        if j.h2h.over15_pct is not None:
            if j.h2h.over15_pct >= 0.80:
                score += 12
                self.alertas.append(("ok", f"✅ H2H Over 1.5: {j.h2h.over15_pct*100:.0f}% (+12 pts)"))
            elif j.h2h.over15_pct >= 0.60:
                score += 6
                self.alertas.append(("ok", f"✅ H2H Over 1.5: {j.h2h.over15_pct*100:.0f}% (+6 pts)"))
            elif j.h2h.over15_pct < 0.50:
                _pen_h2h = -20 if j.tipo_competicao == "copa_inter" else -15
                score += _pen_h2h
                _tag = " [copa_inter — peso ampliado V7.2.6]" if j.tipo_competicao == "copa_inter" else " [Patch V6.9.7]"
                self.alertas.append(("critico", f"❌ H2H Over 1.5: {j.h2h.over15_pct*100:.0f}% — Under predominante ({_pen_h2h} pts){_tag}"))

        # V7.2 Bloco 2 — Alerta pênaltis suspeitos no H2H
        if j.h2h.penaltis_suspeitos:
            _ps = ", ".join(j.h2h.penaltis_suspeitos)
            self.alertas.append(("aviso",
                f"⚠️ H2H — placar(es) suspeito(s) de pênaltis: {_ps} — "
                f"verifique o placar do tempo regular [V7.2 Bloco 2]"))

        # BTTS
        if j.h2h.btts_pct is not None:
            if j.h2h.btts_pct >= 0.70:
                score += 8
                self.alertas.append(("ok", f"✅ BTTS H2H: {j.h2h.btts_pct*100:.0f}% (+8 pts)"))
            elif j.h2h.btts_pct < 0.40:
                score -= 5
                self.alertas.append(("info", f"🔵 BTTS H2H: {j.h2h.btts_pct*100:.0f}% — baixo (-5 pts)"))

        return score

    # ──────────────────────────────────────────
    #  FASE 7: DADOS SUPERBET
    # ──────────────────────────────────────────
    def _fase7_superbet(self) -> int:
        j = self.jogo
        s = j.superbet
        score = 0

        if all(v is None for v in [s.xg_casa, s.xg_fora, s.chutes_gol_casa, s.grandes_chances_casa]):
            self.dados_insuficientes.append("Superbet (xG, finalizações)")
            self.alertas.append(("info", "🔵 Dados Superbet não informados"))
            return 0

        # xG combinado
        if s.xg_casa is not None and s.xg_fora is not None:
            xg_total = s.xg_casa + s.xg_fora
            if xg_total >= 3.5:
                score += 18
                self.alertas.append(("ok", f"✅ xG combinado {xg_total:.2f} — alto (+18 pts)"))
            elif xg_total >= 2.5:
                score += 12
                self.alertas.append(("ok", f"✅ xG combinado {xg_total:.2f} — favorável (+12 pts)"))
            elif xg_total >= 1.8:
                score += 6
                self.alertas.append(("info", f"🔵 xG combinado {xg_total:.2f} — moderado (+6 pts)"))
            else:
                score -= 8
                self.alertas.append(("aviso", f"⚠️ xG combinado {xg_total:.2f} — baixo (-8 pts)"))
        elif s.xg_casa is not None:
            if s.xg_casa >= 1.8:
                score += 10
                self.alertas.append(("ok", f"✅ xG casa {s.xg_casa:.2f} (+10 pts)"))

        # Grandes chances criadas
        if s.grandes_chances_casa is not None and s.grandes_chances_fora is not None:
            gc_total = s.grandes_chances_casa + s.grandes_chances_fora
            if gc_total >= 5.0:
                score += 10
                self.alertas.append(("ok", f"✅ Grandes chances combinadas {gc_total:.1f} (+10 pts)"))
            elif gc_total >= 3.5:
                score += 5
                self.alertas.append(("info", f"🔵 Grandes chances {gc_total:.1f} (+5 pts)"))

        # Chutes ao gol
        if s.chutes_gol_casa is not None and s.chutes_gol_fora is not None:
            cg_total = s.chutes_gol_casa + s.chutes_gol_fora
            if cg_total >= 10.0:
                score += 8
                self.alertas.append(("ok", f"✅ Chutes ao gol combinados {cg_total:.1f} (+8 pts)"))

        return score

    # ──────────────────────────────────────────
    #  FASE 8: CONTEXTO ADICIONAL
    # ──────────────────────────────────────────
    def _fase8_contexto(self) -> int:
        j = self.jogo
        score = 0

        # Derby
        if j.contexto.e_derby:
            if j.contexto.derby_ofensivo:
                score += 10
                self.alertas.append(("ok", "✅ Derby ofensivo (histórico de gols) — Over favorável (+10 pts)"))
            else:
                score -= 10
                self.alertas.append(("aviso", "⚠️ Derby — tende a ser truncado (-10 pts)"))

        # Copa jogo único
        if j.tipo_competicao == "Copa":
            score += 10
            self.alertas.append(("ok", "✅ Copa jogo único — times atacam mais (+10 pts)"))

        # Item 1+8 V7.2 — Fase eliminatória copa_inter
        # Grupos = neutro (tratar como liga). Eliminatório = penalidade crescente.
        # Pesos baseados em UCL 2019/20–2024/25 via Gemini.
        ctx_fase = j.contexto
        if j.tipo_competicao == "copa_inter" and ctx_fase.fase_eliminatoria:
            _PENS_FASE = {
                "grupos":  0,
                "oitavas": -3,
                "quartas": -6,
                "semis":   -10,
                "final":   -15,
            }
            _LABELS_FASE = {
                "grupos":  "Grupos",
                "oitavas": "Oitavas de Final",
                "quartas": "Quartas de Final",
                "semis":   "Semifinal",
                "final":   "Final",
            }
            _pen_fase = _PENS_FASE.get(ctx_fase.fase_eliminatoria, 0)
            _label_fase = _LABELS_FASE.get(ctx_fase.fase_eliminatoria, ctx_fase.fase_eliminatoria)

            if _pen_fase < 0:
                score += _pen_fase
                self.alertas.append(("aviso",
                    f"⚠️ {_label_fase} — pressão eliminatória ({_pen_fase} pts) [V7.2 Item 1]"))
            else:
                self.alertas.append(("info",
                    "🔵 Fase de grupos — tratado como liga, sem penalidade eliminatória [V7.2 Item 8]"))

            # Ajuste jogo de volta
            if ctx_fase.jogo_volta and ctx_fase.agregado_gols_ida:
                try:
                    _partes = [int(x.strip()) for x in ctx_fase.agregado_gols_ida.split("-")]
                    _diff_ida = _partes[0] - _partes[1]  # gols_casa_ida − gols_fora_ida
                    # Mandante da volta perdeu por 1 na ida → precisa atacar
                    if _diff_ida == -1:
                        score += 5
                        self.alertas.append(("ok",
                            f"✅ Jogo de volta — mandante perdendo por 1 gol ({ctx_fase.agregado_gols_ida}) → ataque esperado (+5 pts)"))
                    # Mandante da volta ganhou por 1 na ida → visitante precisa atacar
                    elif _diff_ida == 1:
                        score += 5
                        self.alertas.append(("ok",
                            f"✅ Jogo de volta — visitante perdendo por 1 gol ({ctx_fase.agregado_gols_ida}) → ataque esperado (+5 pts)"))
                    # Vantagem de 2+ gols para qualquer lado → anestesia possível
                    elif abs(_diff_ida) >= 2:
                        score -= 5
                        _lider = "mandante" if _diff_ida > 0 else "visitante"
                        self.alertas.append(("aviso",
                            f"⚠️ Jogo de volta — {_lider} com vantagem de {abs(_diff_ida)} gols ({ctx_fase.agregado_gols_ida}) → anestesia possível (-5 pts)"))
                except (ValueError, IndexError):
                    pass

        # Desfalques — casa e fora separados, com granularidade
        ctx = j.contexto
        nd_casa_total = ctx.desfalques_casa
        nd_fora_total = ctx.desfalques_fora

        # Deduplificação: atacantes/criativos já serão penalizados individualmente
        # abaixo. Descontar do contador geral para não contar duas vezes.
        # Cada flag (atacante_out, criativo_out) = ~1 jogador deduzido do total.
        dedup_casa = (1 if ctx.atacante_titular_casa_out else 0) +                      (1 if ctx.criativo_central_casa_out else 0)
        dedup_fora = (1 if ctx.atacante_titular_fora_out else 0) +                      (1 if ctx.criativo_central_fora_out else 0)

        nd_casa = max(0, nd_casa_total - dedup_casa)
        nd_fora = max(0, nd_fora_total - dedup_fora)

        if nd_casa_total > 0:
            self.alertas.append(("info",
                f"🔵 {nd_casa_total} desfalques no mandante "
                f"({dedup_casa} ofensivos penalizados individualmente)"))

        if nd_casa >= 5:
            score -= 20
            self.alertas.append(("critico", f"❌ {nd_casa} desfalques extras no mandante — crítico (-20 pts)"))
        elif nd_casa >= 3:
            score -= 12
            self.alertas.append(("aviso", f"⚠️ {nd_casa} desfalques extras no mandante (-12 pts)"))
        elif nd_casa >= 1:
            score -= 4
            self.alertas.append(("info", f"🔵 {nd_casa} desfalque(s) extra(s) no mandante (-4 pts)"))

        if nd_fora_total > 0:
            self.alertas.append(("info",
                f"🔵 {nd_fora_total} desfalques no visitante "
                f"({dedup_fora} ofensivos penalizados individualmente)"))

        if nd_fora >= 4:
            score -= 8
            self.alertas.append(("aviso", f"⚠️ {nd_fora} desfalques extras no visitante (-8 pts)"))
        elif nd_fora >= 2:
            score -= 4
            self.alertas.append(("info", f"🔵 {nd_fora} desfalques extras no visitante (-4 pts)"))

        # Atacantes titulares fora — penalidade adaptativa pela qualidade do substituto
        #
        # Escala qualidade_sub (0-3):
        #   0 = sem sub / reserva irrelevante  → penalidade cheia
        #   1 = substituto com queda técnica   → penalidade reduzida
        #   2 = substituto competente          → penalidade mínima
        #   3 = artilheiro/estrela disponível  → sem penalidade (apenas aviso)
        #
        # Exemplo real: Hoffenheim perde Hlozek e Lemperle mas tem KRAMARIC disponível
        # → qualidade_sub_atk_casa = 3 → penalidade zerada

        # D7 — Cálculo dinâmico por minutagem real
        # Titular real: ≥ 70% minutagem. Rotação: < 70%.
        # Sub de nível: ≥ 70%. Sub competente: 50–69%. Sem sub direto: < 50%.
        # [V7.2 Fix] Status 🟡 (dúvida): penalidade máxima reduzida a -10 pts.
        def penalidade_atk_d7(
            atacante_out: bool,
            min_ausente: float | None,
            min_sub: float | None,
            linha_comprometida: bool,
            lado: str,
            duvida: bool = False
        ) -> int:
            if not atacante_out:
                return 0

            # D7-A: ausente é rotação → impacto reduzido independente do sub
            if min_ausente is not None and min_ausente < 0.70:
                self.alertas.append(("info",
                    f"🔵 Desfalque {lado} — jogador de rotação ({min_ausente*100:.0f}% min) → impacto reduzido (-5 pts)"))
                return 5

            # Titular real (≥70%) ou minutagem desconhecida → avaliar sub
            _label_aus = f"{min_ausente*100:.0f}% min" if min_ausente is not None else "minutagem não informada"

            # Teto de penalidade para status 🟡 (dúvida): máximo -10 pts
            _pen_max = 10 if duvida else 18
            _status_label = " 🟡 dúvida" if duvida else ""

            if min_sub is None:
                pen = _pen_max
                tipo = "aviso" if duvida else "critico"
                msg = (
                    f"{'⚠️' if duvida else '❌'} Atacante titular {lado} ausente{_status_label} ({_label_aus}) — "
                    f"sem substituto direto identificado (-{pen} pts) [D7]")
            elif min_sub >= 0.70:
                pen, tipo, msg = 3, "ok", (
                    f"✅ Atacante titular {lado} ausente{_status_label} ({_label_aus}) — "
                    f"sub de nível disponível ({min_sub*100:.0f}% min, -3 pts) [D7]")
            elif min_sub >= 0.50:
                pen = min(10, _pen_max)
                tipo, msg = "aviso", (
                    f"⚠️ Atacante titular {lado} ausente{_status_label} ({_label_aus}) — "
                    f"sub competente ({min_sub*100:.0f}% min, -{pen} pts) [D7]")
            else:
                pen = _pen_max
                tipo = "aviso" if duvida else "critico"
                msg = (
                    f"{'⚠️' if duvida else '❌'} Atacante titular {lado} ausente{_status_label} ({_label_aus}) — "
                    f"sem substituto direto ({min_sub*100:.0f}% min, -{pen} pts) [D7]")

            # D7-B: linha comprometida dobra a penalidade (máx 25)
            if linha_comprometida:
                pen = min(pen * 2, 25)
                msg += " ⚠️ LINHA OFENSIVA COMPROMETIDA"
                tipo = "critico"

            self.alertas.append((tipo, msg))
            return pen

        pen_atk_casa = penalidade_atk_d7(
            ctx.atacante_titular_casa_out,
            ctx.min_ausente_atk_casa,
            ctx.min_sub_atk_casa,
            ctx.linha_comprometida_casa,
            "do mandante",
            duvida=ctx.atacante_titular_casa_duvida
        )
        pen_atk_fora = penalidade_atk_d7(
            ctx.atacante_titular_fora_out,
            ctx.min_ausente_atk_fora,
            ctx.min_sub_atk_fora,
            ctx.linha_comprometida_fora,
            "do visitante",
            duvida=ctx.atacante_titular_fora_duvida
        )

        # Bônus: ambos perdem atacante mas coberturas muito diferentes
        if ctx.atacante_titular_casa_out and ctx.atacante_titular_fora_out:
            _mc = ctx.min_sub_atk_casa or 0
            _mf = ctx.min_sub_atk_fora or 0
            if abs(_mc - _mf) >= 0.30:
                lado_melhor = "mandante" if _mc > _mf else "visitante"
                self.alertas.append(("info",
                    f"🔵 {lado_melhor.capitalize()} melhor coberto nos desfalques ofensivos"))

        score -= (pen_atk_casa + pen_atk_fora)

        # Criativos centrais fora — reduz geração de chances
        # Se criativo_sub = True, o substituto assume o papel → penalidade zerada/mínima
        def pen_criativo(out: bool, sub_disponivel: bool, lado: str) -> int:
            if not out:
                return 0
            if sub_disponivel:
                self.alertas.append(("ok",
                    f"✅ Meia criativo {lado} ausente — substituto criativo disponível (0 pts)"))
                return 0
            return None  # sinaliza "calcular no bloco combinado"

        pen_cri_casa = pen_criativo(ctx.criativo_central_casa_out, ctx.criativo_sub_casa, "do mandante")
        pen_cri_fora = pen_criativo(ctx.criativo_central_fora_out, ctx.criativo_sub_fora, "do visitante")

        # Casos onde não há substituto criativo
        ambos_sem_sub = (ctx.criativo_central_casa_out and not ctx.criativo_sub_casa and
                         ctx.criativo_central_fora_out and not ctx.criativo_sub_fora)
        if ambos_sem_sub:
            score -= 12
            self.alertas.append(("aviso", "⚠️ Meia criativo AMBOS os times ausente (-12 pts)"))
        elif pen_cri_casa is None:  # casa sem sub, fora OK
            score -= 7
            self.alertas.append(("info", "🔵 Meia criativo do mandante ausente (-7 pts)"))
        elif pen_cri_fora is None:  # fora sem sub, casa OK
            score -= 5
            self.alertas.append(("info", "🔵 Meia criativo do visitante ausente (-5 pts)"))

        # Forma recente (Betano)
        forma_casa = j.betano.forma_casa
        if forma_casa:
            vitorias = forma_casa.upper().count("V")
            if vitorias == 0:
                # [V7.2 Fix] Só penaliza Over se o mandante realmente não marca em casa.
                # Se média de gols marcados em casa ≥ 1.0, o time perde mas marca —
                # não há impacto negativo para Over 1.5.
                media_marc_casa = j.betano.media_gols_marcados_casa
                if media_marc_casa is not None and media_marc_casa >= 1.0:
                    self.alertas.append(("info",
                        f"🔵 Mandante sem vencer em casa, mas marca em média "
                        f"{media_marc_casa:.1f} gols/jogo — sem impacto no Over (V7.2 Fix)"))
                else:
                    score -= 10
                    _mg_txt = f" (média {media_marc_casa:.1f} gols/jogo)" if media_marc_casa is not None else ""
                    self.alertas.append(("aviso",
                        f"⚠️ Mandante sem vencer em casa e baixa produção ofensiva{_mg_txt} (-10 pts)"))
            elif vitorias >= 4:
                score += 8
                self.alertas.append(("ok", f"✅ Mandante em excelente forma ({vitorias}/5 vitórias) (+8 pts)"))

        # Visitante favorito + mandante em crise (Patch V6.9.8)
        if j.contexto.fora_zona_rebaixamento is False and j.contexto.casa_zona_rebaixamento:
            if j.betano.vitorias_casa_pct and j.betano.vitorias_casa_pct < 0.30:
                score -= 10
                self.alertas.append(("aviso", "⚠️ Visitante favorito + mandante em crise — tende a controlar (Patch V6.9.8)"))

        return score

    # ──────────────────────────────────────────
    #  FASE 8B: FORMA RECENTE (V7.2)
    #  Dados: Betano Marcados+A conceder / Total / Últimos 6
    #  Complementa Over individual (temporada) com momento atual.
    #  Penalidades leves — é sinal de curto prazo, não critério estrutural.
    # ──────────────────────────────────────────
    def _fase8b_forma_recente(self) -> int:
        j = self.jogo
        score = 0
        fc = j.forma_casa
        ff = j.forma_fora
        liga = j.liga

        # Se nenhum dado de forma recente foi inserido, retornar 0 silenciosamente
        if fc.media_gols_marcados is None and ff.media_gols_marcados is None:
            return 0

        total = fc.total_jogos_amostra or 6  # default 6 se não extraído

        # ── MANDANTE — análise ofensiva recente ──────────────────────────
        if fc.jogos_com_gol is not None:
            taxa_gol_casa = fc.jogos_com_gol / total
            if taxa_gol_casa <= 0.33:   # marcou em ≤ 2/6 jogos
                score -= 8
                self.alertas.append(("critico",
                    f"❌ Mandante em crise ofensiva: marcou em {fc.jogos_com_gol}/{total} jogos recentes (-8 pts)"))
            elif taxa_gol_casa <= 0.50:  # marcou em 3/6
                score -= 4
                self.alertas.append(("aviso",
                    f"⚠️ Mandante abaixo da média ofensiva: {fc.jogos_com_gol}/{total} jogos com gol (-4 pts)"))
            else:
                self.alertas.append(("ok",
                    f"✅ Mandante marcou em {fc.jogos_com_gol}/{total} jogos recentes"))

        if fc.jogos_sem_marcar is not None:
            taxa_branco_casa = fc.jogos_sem_marcar / total
            if taxa_branco_casa >= 0.50:  # ficou sem marcar em ≥ 3/6
                score -= 5
                self.alertas.append(("aviso",
                    f"⚠️ Mandante sem marcar em {fc.jogos_sem_marcar}/{total} jogos recentes (-5 pts)"))

        # ── 1T — MANDANTE (experimental: Holanda e Dinamarca) ────────────
        LIGAS_PADRAO_1T = {"Eredivisie", "Eerste Divisie", "Superliga Dinamarca", "Superliga DK"}
        if liga in LIGAS_PADRAO_1T and fc.jogos_com_gol_1t is not None:
            taxa_1t_casa = fc.jogos_com_gol_1t / total
            if taxa_1t_casa == 0.0:
                self.alertas.append(("aviso",
                    f"⚠️ [{liga}] Mandante não marcou no 1T em nenhum dos últimos {total} jogos "
                    f"— padrão de risco monitorado (experimental V7.2)"))
            elif taxa_1t_casa <= 0.17:  # 1/6
                self.alertas.append(("info",
                    f"🔵 [{liga}] Mandante raramente marca no 1T ({fc.jogos_com_gol_1t}/{total}) "
                    f"— alerta experimental"))

        # ── VISITANTE — análise ofensiva recente ─────────────────────────
        if ff.jogos_com_gol is not None:
            taxa_gol_fora = ff.jogos_com_gol / total
            if taxa_gol_fora <= 0.33:
                score -= 5
                self.alertas.append(("aviso",
                    f"⚠️ Visitante em crise ofensiva: marcou em {ff.jogos_com_gol}/{total} jogos recentes (-5 pts)"))
            else:
                self.alertas.append(("ok",
                    f"✅ Visitante marcou em {ff.jogos_com_gol}/{total} jogos recentes"))

        # ── DEFESA — gols concedidos ──────────────────────────────────────
        # Visitante com defesa aberta = reforço de Over
        if ff.media_gols_concedidos is not None and ff.media_gols_concedidos >= 2.5:
            score += 5
            self.alertas.append(("ok",
                f"✅ Visitante concedeu média {ff.media_gols_concedidos:.1f} gols/jogo recente "
                f"— defesa aberta favorece Over (+5 pts)"))

        # Mandante com defesa muito aberta — Over pode vir pelo outro lado
        if fc.media_gols_concedidos is not None and fc.media_gols_concedidos >= 2.5:
            score += 3
            self.alertas.append(("info",
                f"🔵 Mandante concedeu {fc.media_gols_concedidos:.1f} gols/jogo recente (+3 pts)"))

        # ── CRISE BILATERAL — ambos em crise ofensiva ─────────────────────
        if (fc.jogos_com_gol is not None and ff.jogos_com_gol is not None):
            if fc.jogos_com_gol / total <= 0.33 and ff.jogos_com_gol / total <= 0.33:
                score -= 8
                self.alertas.append(("critico",
                    "❌ Ambos em crise ofensiva nos últimos jogos — risco alto de Under (-8 pts adicional)"))

        # ── PADRÃO 1T BILATERAL (experimental Holanda/Dinamarca) ─────────
        if liga in LIGAS_PADRAO_1T:
            if fc.jogos_com_gol_1t == 0 and ff.jogos_com_gol_1t == 0:
                self.alertas.append(("aviso",
                    f"🔬 [{liga}] PADRÃO EXPERIMENTAL: nenhum dos dois times marcou no 1T "
                    f"nos últimos {total} jogos — padrão associado a Under em Holanda/Turquia. "
                    f"Sem penalidade automática — validando amostra."))

        return score
    def _calcular_cobertura(self):
        campos_totais = 12
        campos_presentes = 0
        j = self.jogo

        if j.betano.over15_casa_pct is not None: campos_presentes += 2
        if j.betano.over15_fora_pct is not None: campos_presentes += 1
        if j.betano.btts_casa_pct is not None: campos_presentes += 1
        if j.h2h.media_gols is not None: campos_presentes += 2
        if j.h2h.over15_pct is not None: campos_presentes += 1
        if j.superbet.xg_casa is not None: campos_presentes += 2
        if j.contexto.desfalques_casa is not None: campos_presentes += 1
        if j.betano.forma_casa: campos_presentes += 1
        if j.contexto.casa_posicao is not None: campos_presentes += 1

        self.cobertura_dados = round((campos_presentes / campos_totais) * 100)

    # ──────────────────────────────────────────
    #  FASE 8C: INATIVIDADE OFENSIVA RECENTE (Item 6 V7.2)
    #  Origem: armadilhas da Eredivisie — times com DNA ofensivo histórico
    #  mas padrão recente de 0 gols fora/casa.
    #
    #  Hierarquia: padrão recente prevalece sobre dado de temporada,
    #  mas não veta — quando contradiz H2H forte ou xG alto, penalidade
    #  reduzida + alerta de tensão para análise manual.
    #
    #  Thresholds (flag de observação — calibrar por liga):
    #    3+ jogos consecutivos sem marcar fora (visitante)  → −15 pts
    #    3+ jogos consecutivos sem marcar em casa (mandante) → −15 pts
    #    Ambos inativos                                      → −25 pts total
    #    Inativo + H2H forte (≥4 jogos, ≥75% Over)          → −8 pts
    #    Inativo + xG combinado ≥ 3.5                        → −10 pts
    # ──────────────────────────────────────────
    def _fase8c_inatividade_ofensiva(self) -> int:
        j = self.jogo
        uj = j.ultimos_jogos  # UltimosJogosSuperbet

        def _consecutivos_sem_marcar(jogos: list) -> int:
            """Conta jogos consecutivos mais recentes sem gols marcados."""
            count = 0
            for jogo in jogos:  # lista já está em ordem cronológica inversa (mais recente primeiro)
                if jogo.gols_pro is None:
                    break  # sem placar = dados ausentes, parar contagem
                if jogo.gols_pro == 0:
                    count += 1
                else:
                    break  # marcou — série interrompida
            return count

        # Verificar dados disponíveis
        tem_jogos_fora_visitante = bool(uj.jogos_fora)
        tem_jogos_casa_mandante  = bool(uj.jogos_casa)

        if not tem_jogos_fora_visitante and not tem_jogos_casa_mandante:
            return 0  # sem dados D12 — silencioso

        LIMITE = 3  # jogos consecutivos sem marcar para ativar flag
        score = 0

        # ── Visitante: jogos fora ────────────────────
        seq_fora = _consecutivos_sem_marcar(uj.jogos_fora) if tem_jogos_fora_visitante else 0

        # ── Mandante: jogos em casa ──────────────────
        seq_casa = _consecutivos_sem_marcar(uj.jogos_casa) if tem_jogos_casa_mandante else 0

        # ── Calcular tensão com dados de temporada ───
        h2h_forte = (
            j.h2h.total_jogos is not None and j.h2h.total_jogos >= 4
            and j.h2h.over15_pct is not None and j.h2h.over15_pct >= 0.75
        )
        xg_combinado = (
            (j.superbet.xg_casa or 0) + (j.superbet.xg_fora or 0)
        )
        xg_alto = xg_combinado >= 3.5

        def _penalidade_com_tensao(time_label: str, seq: int) -> int:
            """Retorna penalidade ajustada pela tensão com outros dados."""
            nonlocal score
            if h2h_forte and xg_alto:
                # Dois sinais positivos fortes — penalidade mínima + alerta triplo
                pen = -5
                self.alertas.append(("aviso",
                    f"⚠️ {time_label}: {seq} jogos sem marcar — TENSÃO ALTA: "
                    f"H2H forte ({j.h2h.over15_pct*100:.0f}% Over, {j.h2h.total_jogos} jogos) "
                    f"+ xG combinado {xg_combinado:.1f} contradizem padrão recente. "
                    f"Análise manual obrigatória. ({pen} pts) [V7.2 Item 6]"))
            elif h2h_forte:
                pen = -8
                self.alertas.append(("aviso",
                    f"⚠️ {time_label}: {seq} jogos sem marcar — TENSÃO: "
                    f"H2H forte ({j.h2h.over15_pct*100:.0f}% Over, {j.h2h.total_jogos} jogos) "
                    f"contradiz padrão recente. ({pen} pts) [V7.2 Item 6]"))
            elif xg_alto:
                pen = -10
                self.alertas.append(("aviso",
                    f"⚠️ {time_label}: {seq} jogos sem marcar — TENSÃO: "
                    f"xG combinado alto ({xg_combinado:.1f}) contradiz padrão recente. "
                    f"({pen} pts) [V7.2 Item 6]"))
            else:
                pen = -15
                self.alertas.append(("critico",
                    f"❌ {time_label}: {seq} jogos consecutivos sem marcar — "
                    f"inatividade ofensiva confirmada. Análise manual recomendada. "
                    f"({pen} pts) [V7.2 Item 6]"))
            return pen

        visitante_inativo = seq_fora >= LIMITE
        mandante_inativo  = seq_casa >= LIMITE

        if visitante_inativo and mandante_inativo:
            # Ambos inativos — penalidade combinada com teto −25
            pen_v = _penalidade_com_tensao(f"Visitante ({seq_fora}× fora)", seq_fora)
            pen_m = _penalidade_com_tensao(f"Mandante ({seq_casa}× em casa)", seq_casa)
            score = max(pen_v + pen_m, -25)
            self.alertas.append(("critico",
                f"❌ Confronto estéril — ambos sem marcar recentemente "
                f"(visitante {seq_fora}× fora, mandante {seq_casa}× em casa). "
                f"Score total: {score} pts [V7.2 Item 6]"))
        elif visitante_inativo:
            score = _penalidade_com_tensao(
                f"Visitante ({seq_fora} jogos fora sem marcar)", seq_fora)
        elif mandante_inativo:
            score = _penalidade_com_tensao(
                f"Mandante ({seq_casa} jogos em casa sem marcar)", seq_casa)
        else:
            # Sem inatividade — informar sequência se relevante (≥2)
            if seq_fora >= 2:
                self.alertas.append(("aviso",
                    f"⚠️ Visitante: {seq_fora} jogos fora sem marcar — "
                    f"ainda abaixo do limite ({LIMITE}), monitorar [V7.2 Item 6]"))
            if seq_casa >= 2:
                self.alertas.append(("aviso",
                    f"⚠️ Mandante: {seq_casa} jogos em casa sem marcar — "
                    f"ainda abaixo do limite ({LIMITE}), monitorar [V7.2 Item 6]"))

        return score

    # ──────────────────────────────────────────
    #  MOTOR PRINCIPAL
    # ──────────────────────────────────────────
    def analisar(self) -> dict:
        j = self.jogo
        self._calcular_cobertura()

        # FASE 1: Blacklists
        self.detalhes_fases["fase1"] = ("Blacklists & Range de Odds", 0)
        if not self._fase1_blacklists():
            self.status = "REJEITADO"
            self.score_final = 0
            return self._resultado()

        # FASE 2: Zona de atenção (penalidade no score, não rejeição)
        pen_odd = self._fase2_zona_critica()
        self.pontos += pen_odd
        self.detalhes_fases["fase2"] = ("Odd — Zona de Atenção", pen_odd)

        # FASE 3: Calendário europeu
        pen_cal = self._fase3_calendario()
        self.pontos += pen_cal
        self.detalhes_fases["fase3"] = ("Calendário Europeu", pen_cal)

        # Se penalidade de CL muito severa e times históricos de poupança
        if pen_cal <= -25 and j.tipo_competicao == "Campeonato":
            times_poupam = {"Feyenoord", "Atlético Madrid", "Atlético de Madrid"}
            if j.time_casa in times_poupam:
                self.motivos_rejeicao.append(f"{j.time_casa} tem histórico documentado de poupar antes de CL/EL")
                self.alertas.append(("critico", f"❌ {j.time_casa} — histórico de poupança confirmado"))
                self.status = "REJEITADO"
                self.score_final = 0
                return self._resultado()

        # FASE 4: Rebaixamento
        ok_reb, pen_reb = self._fase4_rebaixamento()
        self.detalhes_fases["fase4"] = ("Contexto de Rebaixamento", pen_reb)
        if not ok_reb:
            self.status = "REJEITADO"
            self.score_final = 0
            return self._resultado()
        self.pontos += pen_reb

        # FASE 5: Over individual (CRÍTICO V6.9)
        ok_over, score_over = self._fase5_over_individual()
        self.detalhes_fases["fase5"] = ("Over Individual", score_over)
        if not ok_over:
            self.status = "REJEITADO"
            self.score_final = 0
            return self._resultado()
        self.pontos += score_over

        # FASE 6: H2H
        score_h2h = self._fase6_h2h()
        self.pontos += score_h2h
        self.detalhes_fases["fase6"] = ("Análise H2H", score_h2h)

        # FASE 7: Superbet
        score_sb = self._fase7_superbet()
        self.pontos += score_sb
        self.detalhes_fases["fase7"] = ("Dados Superbet", score_sb)

        # FASE 8: Contexto
        score_ctx = self._fase8_contexto()
        self.pontos += score_ctx
        self.detalhes_fases["fase8"] = ("Contexto & Situação", score_ctx)

        # FASE 8B: Forma Recente (V7.2)
        score_forma = self._fase8b_forma_recente()
        self.pontos += score_forma
        self.detalhes_fases["fase8b"] = ("Forma Recente", score_forma)

        # FASE 8C: Inatividade Ofensiva Recente (Item 6 V7.2)
        score_inativo = self._fase8c_inatividade_ofensiva()
        self.pontos += score_inativo
        self.detalhes_fases["fase8c"] = ("Inatividade Ofensiva", score_inativo)

        # Base da liga
        liga_info = HIERARQUIA_LIGAS.get(j.liga, {"prob_base": 72, "tier": "?"})
        base_liga = liga_info["prob_base"]
        self.pontos += base_liga * 0.3  # 30% de peso para base da liga
        self.detalhes_fases["base_liga"] = ("Base da Liga", round(base_liga * 0.3, 1))

        # Score final normalizado 0–100
        raw = self.pontos
        self.score_final = max(0, min(100, int(raw)))

        # ── Item 3 V7.2: Score 100 não existe em Copa — teto 99 ──────────────
        # Copa é contexto não repetível — score máximo pressupõe repetibilidade.
        if self.score_final >= 100 and j.tipo_competicao in ("Copa", "copa_inter", "CL_Volta"):
            self.score_final = 99
            self.alertas.append(("info",
                "🔵 Teto de score em Copa: 99/100 (contexto não repetível) [V7.2 Item 3]"))

        # ── V7.1.4: Score 100 exige critérios mínimos ────────────────────────
        # Score máximo sem dados completos é enganoso. Com critérios ausentes,
        # rebaixar para 85 e registrar alerta. Evidência: Midtjylland (liga nova)
        # e Samsunspor (Over casa não confirmado ≥ 80%) → ambos score 100 → 0-0.
        if self.score_final >= 100:
            liga_info_chk = HIERARQUIA_LIGAS.get(j.liga, {"taxa": 0})
            criterios_score_100 = {
                "over_casa_≥_80%": (
                    j.betano.over15_casa_pct is not None
                    and j.betano.over15_casa_pct >= OVER_CASA_MIN_SCORE_100
                ),
                "over_fora_confirmado": j.betano.over15_fora_pct is not None,
                "liga_mapeada_taxa>0": liga_info_chk.get("taxa", 0) > 0,
                "xg_confirmado": j.superbet.xg_casa is not None,
                "h2h_≥_3_jogos": (
                    j.h2h.total_jogos is not None
                    and j.h2h.total_jogos >= 3
                ),
            }
            faltando = [k for k, v in criterios_score_100.items() if not v]
            if faltando:
                self.score_final = 85
                self.alertas.append((
                    "aviso",
                    f"⚠️ Score rebaixado 100→85 (V7.1.4): critérios ausentes: {', '.join(faltando)} "
                    f"— dados insuficientes para score máximo"
                ))

        # Status
        if self.dados_insuficientes and self.score_final < 75:
            self.status = "DADOS INSUFICIENTES"
        elif self.score_final >= PROB_MINIMA_APROVACAO:
            if self.score_final >= 85:
                self.status = "APROVADO"
            else:
                self.status = "ATENÇÃO"  # Aprovado mas com ressalvas
        else:
            if self.motivos_rejeicao:
                self.status = "REJEITADO"
            else:
                self.status = "ATENÇÃO"

        return self._resultado()

    def _resultado(self) -> dict:
        return {
            "status": self.status,
            "score": self.score_final,
            "alertas": self.alertas,
            "motivos_rejeicao": self.motivos_rejeicao,
            "dados_insuficientes": self.dados_insuficientes,
            "cobertura": self.cobertura_dados,
            "detalhes_fases": self.detalhes_fases,
        }


# ══════════════════════════════════════════════════════════════════
