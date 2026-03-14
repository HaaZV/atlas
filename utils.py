"""
atlas/utils.py
Funções utilitárias: detecção de liga, importação de lista,
reconstrução de Jogo, geração de bilhetes.
"""

from __future__ import annotations
import re
import dataclasses
from typing import Optional
from itertools import combinations

from atlas.config import (
    Jogo, DadosBetano, DadosSuperbet, DadosH2H, DadosContexto,
    FormaRecente, UltimosJogosSuperbet, JogoSuperbet,
    HIERARQUIA_LIGAS, RANGE_BILHETE_MIN, RANGE_BILHETE_MAX,
)

def gerar_bilhetes(jogos_aprovados: list) -> list:
    """
    Gera combinações de bilhetes dentro do range 1.50–1.60.
    Retorna lista de (nome, jogos, odd_combinada, descricao).
    """
    bilhetes = []

    for n in range(2, min(4, len(jogos_aprovados) + 1)):
        for combo in combinations(jogos_aprovados, n):
            odd_combinada = 1.0
            for j in combo:
                odd_combinada *= j["odd"]
            odd_combinada = round(odd_combinada, 3)

            if RANGE_BILHETE_MIN <= odd_combinada <= RANGE_BILHETE_MAX:
                score_medio = sum(j["score"] for j in combo) / len(combo)
                bilhetes.append({
                    "jogos": combo,
                    "odd": odd_combinada,
                    "score_medio": round(score_medio, 1),
                    "n_jogos": n
                })

    # Ordenar por score médio
    bilhetes.sort(key=lambda x: (-x["score_medio"], -x["odd"]))
    return bilhetes[:6]  # Top 6 combinações


# ══════════════════════════════════════════════════════════════════
#  INTERFACE STREAMLIT
# ══════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════
#  MAIN — LAYOUT PRINCIPAL
# ══════════════════════════════════════════════════════════════════


def _build_time_liga_map():
    """
    Mapa de times conhecidos para detecção automática de liga.
    Adicione times conforme necessário.
    Formato: token_minusculo -> nome_liga
    """
    m = {}

    bundesliga = [
        "bayern","dortmund","leverkusen","leipzig","frankfurt","wolfsburg",
        "freiburg","mainz","hoffenheim","augsburg","bochum","bremen",
        "gladbach","monchengladbach","heidenheim","stuttgart","union berlin",
        "st pauli","pauli","holstein kiel","kiel",
    ]
    for t in bundesliga: m[t] = "Bundesliga"

    segunda_bundesliga = [
        "hamburgo","hsv","kaiserslautern","nurnberg","hannover","karlsruhe",
        "schalke","paderborn","elversberg","greuther furth","magdeburg",
        "hertha","dusseldorf","fortuna","spvgg","greuther",
    ]
    for t in segunda_bundesliga: m[t] = "2. Bundesliga"

    premier = [
        "arsenal","chelsea","liverpool","manchester city","man city",
        "manchester united","man united","tottenham","spurs","newcastle",
        "aston villa","west ham","brighton","everton","brentford",
        "fulham","crystal palace","wolves","wolverhampton","leicester",
        "nottingham","ipswich","southampton","bournemouth",
    ]
    for t in premier: m[t] = "Premier League"

    championship = [
        "leeds","middlesbrough","sheffield united","sheffield","burnley",
        "sunderland","norwich","luton","cardiff","millwall","bristol city",
        "coventry","plymouth","hull","portsmouth","oxford","derby","watford",
        "blackburn","swansea","qpr","stoke","preston",
    ]
    for t in championship: m[t] = "Championship"

    seriea = [
        "inter","milan","juventus","napoli","roma","lazio","atalanta",
        "fiorentina","torino","bologna","genoa","como","verona",
        "parma","cagliari","udinese","empoli","lecce","monza","venezia",
    ]
    for t in seriea: m[t] = "Serie A"

    laliga = [
        "real madrid","barcelona","atletico","athletic","real sociedad",
        "villarreal","betis","sevilla","valencia","osasuna","girona",
        "mallorca","celta","alaves","valladolid","las palmas","getafe",
        "espanyol","leganes","rayo",
    ]
    for t in laliga: m[t] = "La Liga"

    ligue1 = [
        "psg","paris saint","marseille","lyon","monaco","lille","rennes",
        "nice","lens","toulouse","reims","nantes","brest","le havre",
        "angers","montpellier","saint-etienne","auxerre","strasbourg",
    ]
    for t in ligue1: m[t] = "Ligue 1"

    eredivisie = [
        "ajax","psv","feyenoord","az alkmaar","utrecht","twente",
        "groningen","sparta rotterdam","heerenveen",
        "nec nijmegen","nec","fortuna sittard","heracles",
        "go ahead","go ahead eagles","excelsior",
    ]
    for t in eredivisie: m[t] = "Eredivisie"

    eerste_divisie = [
        "vitesse","almere","waalwijk","cambuur","volendam",
        "pec zwolle","zwolle","roda","helmond","den bosch",
        "oss","top oss","mvv","maastricht","vvv","venlo",
        "emmen","den haag","fc eindhoven","dordrecht","fortuna",
        "telstar","jong ajax","jong psv","jong az","jong utrecht",
    ]
    for t in eerste_divisie: m[t] = "Eerste Divisie"

    ligaportugal = [
        "sporting","benfica","porto","braga","vitoria","guimaraes",
        "famalicao","boavista","estoril","moreirense","casa pia",
        "farense","rio ave","arouca","vizela","santa clara",
        "nacional","estrela","gil vicente",
    ]
    for t in ligaportugal: m[t] = "Liga Portugal"

    superlig = [
        "galatasaray","fenerbahce","besiktas","trabzonspor","sivasspor",
        "alanyaspor","antalyaspor","kayserispor","kasimpasa","konyaspor",
        "hatayspor","rizespor","gaziantep","eyupspor","samsunspor",
    ]
    for t in superlig: m[t] = "Süper Lig"

    return m

TIME_LIGA_MAP = _build_time_liga_map()

# Número padrão de times por liga
N_TIMES_LIGA = {
    "Bundesliga": 18, "2. Bundesliga": 18,
    "Premier League": 20, "Championship": 24,
    "Serie A": 20, "La Liga": 20, "Ligue 1": 18,
    "Eredivisie": 18, "Eerste Divisie": 20,
    "Liga Portugal": 18, "Saudi Pro League": 18,
    "Süper Lig": 19, "Brasileirão": 20,
    "Paulistão": 16, "Copa del Rey": 0,
}

def detectar_liga_por_times(time_casa: str, time_fora: str) -> str:
    """
    Detecta a liga automaticamente pelo nome dos times.
    Retorna nome da liga ou string vazia se não reconhecido.
    """
    for nome in (time_casa.lower(), time_fora.lower()):
        # Verificar cada token do nome
        for token in [nome] + nome.split():
            if token in TIME_LIGA_MAP:
                return TIME_LIGA_MAP[token]
        # Verificar substrings de 5+ chars
        for chave, liga in TIME_LIGA_MAP.items():
            if len(chave) >= 5 and chave in nome:
                return liga
    return ""


def parsear_lista_jogos(texto: str) -> list:
    """
    Parser V7.2.2 — Opção A — formato padronizado.

    FORMATO OBRIGATÓRIO:
        Time Casa × Time Fora | Liga | Odd
        Time Casa x Time Fora | Liga | Odd

    Liga e Odd podem vir em qualquer ordem após o | inicial.
    Linhas sem separador de times são ignoradas silenciosamente.

    Exemplos:
        Como 1907 × Inter de Milão | Copa da Itália | 1.42
        Port Vale × Bristol City | FA Cup | 1.31
        Bournemouth × Brentford | Premier League | 1.21
        19:00 Arsenal × Chelsea | Premier League | 1.35
    """
    import re
    jogos = []
    separadores = re.compile(r'\s+(?:x|vs\.?|×)\s+', re.IGNORECASE)

    ligas_conhecidas = list(dict.fromkeys(
        list(HIERARQUIA_LIGAS.keys()) +
        list(TIME_LIGA_MAP.values()) + [
            "Bundesliga", "Premier League", "Serie A", "La Liga", "Ligue 1",
            "Eredivisie", "Liga Portugal", "Süper Lig", "Championship", "EFL Championship",
            "2. Bundesliga", "Brasileirão", "Paulistão",
            "Champions League", "Europa League", "Conference League",
            "FA Cup", "Copa da Itália", "Coppa Italia",
            "Copa da França", "Coupe de France",
            "Copa KNVB", "KNVB Cup", "Copa da Holanda",
            "DFB Pokal", "Copa da Alemanha",
            "Copa do Brasil", "Taça de Portugal",
            "Copa da Inglaterra", "Copa da Espanha", "Copa del Rey",
        ]
    ))
    ligas_lower = {l.lower(): l for l in ligas_conhecidas}

    for linha in texto.strip().splitlines():
        linha = linha.strip()
        if not linha or linha.startswith('#'):
            continue
        # Remover horário no início
        linha = re.sub(r'^\d{1,2}[h:]\d{2}\s*', '', linha).strip()
        # Separar por |
        partes = [p.strip() for p in linha.split('|')]
        # Times na primeira parte
        match_times = separadores.split(partes[0], maxsplit=1)
        if len(match_times) != 2:
            continue
        time_casa = match_times[0].strip()
        time_fora = match_times[1].strip()
        # Liga e odd nas partes seguintes
        liga = ""
        odd = 0.0
        for parte in partes[1:]:
            parte = parte.strip()
            if not parte:
                continue
            try:
                v = float(parte.replace(',', '.'))
                if 1.01 <= v <= 5.0:
                    odd = v
                    continue
            except ValueError:
                pass
            parte_l = parte.lower()
            if parte_l in ligas_lower:
                liga = ligas_lower[parte_l]
                continue
            for nome_l, nome_orig in ligas_lower.items():
                if nome_l in parte_l or parte_l in nome_l:
                    liga = nome_orig
                    break
        if not liga:
            liga = detectar_liga_por_times(time_casa, time_fora)
        jogos.append({
            "time_casa":      time_casa,
            "time_fora":      time_fora,
            "liga":           liga or "Outra",
            "odd":            round(odd, 2) if odd >= 1.01 else 0.0,
            "n_times":        max(10, N_TIMES_LIGA.get(liga, 18) or 18),
            "liga_detectada": bool(liga and liga != "Outra"),
        })
    return jogos




def _reconstruir_jogo(d: dict):
    """Reconstrói um objeto Jogo completo a partir do dict serializado por dataclasses.asdict()."""
    def _superbet(sd):
        if not sd: return DadosSuperbet()
        return DadosSuperbet(
            xg_casa=sd.get("xg_casa"),
            xg_fora=sd.get("xg_fora"),
            gols_media_casa=sd.get("gols_media_casa"),
            gols_media_fora=sd.get("gols_media_fora"),
            posse_casa=sd.get("posse_casa"),
            posse_fora=sd.get("posse_fora"),
            finalizacoes_casa=sd.get("finalizacoes_casa"),
            finalizacoes_fora=sd.get("finalizacoes_fora"),
            chutes_gol_casa=sd.get("chutes_gol_casa"),
            chutes_gol_fora=sd.get("chutes_gol_fora"),
            grandes_chances_casa=sd.get("grandes_chances_casa"),
            grandes_chances_fora=sd.get("grandes_chances_fora"),
            xgot_casa=sd.get("xgot_casa"),
            xgot_fora=sd.get("xgot_fora"),
            ataques_perigosos_casa=sd.get("ataques_perigosos_casa"),
            ataques_perigosos_fora=sd.get("ataques_perigosos_fora"),
        )

    def _betano(bd):
        if not bd: return DadosBetano()
        return DadosBetano(
            over15_casa_pct=bd.get("over15_casa_pct"),
            over15_fora_pct=bd.get("over15_fora_pct"),
            over15_casa_n=bd.get("over15_casa_n"),
            over15_fora_n=bd.get("over15_fora_n"),
            over25_casa_pct=bd.get("over25_casa_pct"),
            over25_fora_pct=bd.get("over25_fora_pct"),
            btts_casa_pct=bd.get("btts_casa_pct"),
            btts_fora_pct=bd.get("btts_fora_pct"),
            clean_sheet_casa_pct=bd.get("clean_sheet_casa_pct"),
            clean_sheet_fora_pct=bd.get("clean_sheet_fora_pct"),
            media_gols_marcados_casa=bd.get("media_gols_marcados_casa"),
            media_gols_marcados_fora=bd.get("media_gols_marcados_fora"),
            media_gols_sofridos_casa=bd.get("media_gols_sofridos_casa"),
            media_gols_sofridos_fora=bd.get("media_gols_sofridos_fora"),
            forma_casa=bd.get("forma_casa"),
            forma_fora=bd.get("forma_fora"),
            vitorias_casa_pct=bd.get("vitorias_casa_pct"),
            # Item 9 V7.2 — FootyStats por competição
            over15_mandante_comp=bd.get("over15_mandante_comp"),
            over15_visitante_comp=bd.get("over15_visitante_comp"),
        )

    def _h2h(hd):
        if not hd: return DadosH2H()
        return DadosH2H(
            total_jogos=hd.get("total_jogos"),
            vitorias_casa=hd.get("vitorias_casa"),
            empates=hd.get("empates"),
            vitorias_fora=hd.get("vitorias_fora"),
            media_gols=hd.get("media_gols"),
            btts_pct=hd.get("btts_pct"),
            over15_pct=hd.get("over15_pct"),
            over25_pct=hd.get("over25_pct"),
            resultados_recentes=hd.get("resultados_recentes", []),
            penaltis_suspeitos=hd.get("penaltis_suspeitos", []),
        )

    def _forma(fd):
        if not fd: return FormaRecente()
        return FormaRecente(
            jogos_com_gol=fd.get("jogos_com_gol"),
            jogos_com_gol_1t=fd.get("jogos_com_gol_1t"),
            total_jogos_amostra=fd.get("total_jogos_amostra"),
            media_gols_marcados=fd.get("media_gols_marcados"),
            jogos_sem_marcar=fd.get("jogos_sem_marcar"),
            media_gols_concedidos=fd.get("media_gols_concedidos"),
            media_gols_concedidos_1t=fd.get("media_gols_concedidos_1t"),
        )

    def _ctx(cd):
        if not cd: return DadosContexto()
        return DadosContexto(
            tipo_competicao=cd.get("tipo_competicao", "Campeonato"),
            agregado_cl=cd.get("agregado_cl"),
            tem_cl_proximos_3_dias=cd.get("tem_cl_proximos_3_dias", False),
            tem_el_proximos_4_dias=cd.get("tem_el_proximos_4_dias", False),
            total_times_liga=cd.get("total_times_liga"),
            casa_posicao=cd.get("casa_posicao"),
            fora_posicao=cd.get("fora_posicao"),
            casa_zona_rebaixamento=cd.get("casa_zona_rebaixamento", False),
            fora_zona_rebaixamento=cd.get("fora_zona_rebaixamento", False),
            desfalques_casa=cd.get("desfalques_casa", 0),
            desfalques_fora=cd.get("desfalques_fora", 0),
            atacante_titular_casa_out=cd.get("atacante_titular_casa_out", False),
            atacante_titular_fora_out=cd.get("atacante_titular_fora_out", False),
            # D7 — campos adicionados V7.2 (faltavam em _reconstruir_jogo)
            atacante_titular_casa_duvida=cd.get("atacante_titular_casa_duvida", False),
            atacante_titular_fora_duvida=cd.get("atacante_titular_fora_duvida", False),
            min_ausente_atk_casa=cd.get("min_ausente_atk_casa"),
            min_sub_atk_casa=cd.get("min_sub_atk_casa"),
            min_ausente_atk_fora=cd.get("min_ausente_atk_fora"),
            min_sub_atk_fora=cd.get("min_sub_atk_fora"),
            linha_comprometida_casa=cd.get("linha_comprometida_casa", False),
            linha_comprometida_fora=cd.get("linha_comprometida_fora", False),
            criativo_central_casa_out=cd.get("criativo_central_casa_out", False),
            criativo_central_fora_out=cd.get("criativo_central_fora_out", False),
            criativo_sub_casa=cd.get("criativo_sub_casa", False),
            criativo_sub_fora=cd.get("criativo_sub_fora", False),
            qualidade_sub_atk_casa=cd.get("qualidade_sub_atk_casa", 0),
            qualidade_sub_atk_fora=cd.get("qualidade_sub_atk_fora", 0),
            e_derby=cd.get("e_derby", False),
            derby_ofensivo=cd.get("derby_ofensivo", False),
            freiburg_visitante_copa=cd.get("freiburg_visitante_copa", False),
            # Item 1+8 V7.2 — fase eliminatória (faltavam em _reconstruir_jogo)
            fase_eliminatoria=cd.get("fase_eliminatoria"),
            jogo_volta=cd.get("jogo_volta", False),
            agregado_gols_ida=cd.get("agregado_gols_ida"),
        )

    def _ultimos(ud):
        if not ud: return UltimosJogosSuperbet()
        uj = UltimosJogosSuperbet()
        uj.over15_casa          = ud.get("over15_casa")
        uj.over15_fora          = ud.get("over15_fora")
        uj.media_gols_pro_casa  = ud.get("media_gols_pro_casa")
        uj.media_gols_pro_fora  = ud.get("media_gols_pro_fora")
        uj.media_gols_contra_casa = ud.get("media_gols_contra_casa")
        uj.media_gols_contra_fora = ud.get("media_gols_contra_fora")
        uj.n_jogos_casa         = ud.get("n_jogos_casa", 0)
        uj.n_jogos_fora         = ud.get("n_jogos_fora", 0)
        # Reconstruir lista de JogoSuperbet
        for j in ud.get("jogos_casa", []):
            uj.jogos_casa.append(JogoSuperbet(
                data=j.get("data",""), adversario=j.get("adversario",""),
                gols_pro=j.get("gols_pro"), gols_contra=j.get("gols_contra"),
                em_casa=j.get("em_casa", True), resultado=j.get("resultado","")
            ))
        for j in ud.get("jogos_fora", []):
            uj.jogos_fora.append(JogoSuperbet(
                data=j.get("data",""), adversario=j.get("adversario",""),
                gols_pro=j.get("gols_pro"), gols_contra=j.get("gols_contra"),
                em_casa=j.get("em_casa", True), resultado=j.get("resultado","")
            ))
        return uj

    return Jogo(
        time_casa=d.get("time_casa", "?"),
        time_fora=d.get("time_fora", "?"),
        liga=d.get("liga", "Outra"),
        odd=d.get("odd", 1.25),
        tipo_competicao=d.get("tipo_competicao", "Campeonato"),
        superbet=_superbet(d.get("superbet", {})),
        betano=_betano(d.get("betano", {})),
        h2h=_h2h(d.get("h2h", {})),
        contexto=_ctx(d.get("contexto", {})),
        forma_casa=_forma(d.get("forma_casa", {})),
        forma_fora=_forma(d.get("forma_fora", {})),
        desfalques_texto_casa=d.get("desfalques_texto_casa", ""),
        desfalques_texto_fora=d.get("desfalques_texto_fora", ""),
        ultimos_jogos=_ultimos(d.get("ultimos_jogos", {})),
        desfalques_superbet_raw=d.get("desfalques_superbet_raw", ""),
    )


