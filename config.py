"""
atlas/config.py
Constantes, dataclasses e hierarquia de ligas do ATLAS V7.2.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# ══════════════════════════════════════════════════════════════════
#  BLACKLISTS
# ══════════════════════════════════════════════════════════════════

BLACKLIST_TIMES_VISITANTE = {
    "Getafe":    "Retranca absoluta fora (0% Over histórico)",
    "Burnley":   "Retranca absoluta fora",
    "Freiburg":  "Retranca fora em campeonato (ataca apenas em Copa)",
    "Brentford": "Retranca vs top-6",
}

BLACKLIST_LIGAS = {
    "Serie B (Itália)": "Historicamente Under",
}

EXCECAO_ZONA_CRITICA = {
    "Eredivisie", "Eerste Divisie", "Copa KNVB", "Copa del Rey",
}

TIMES_ULTRA_OFENSIVOS_HOLANDA = {
    "PSV", "PSV II", "Jong PSV", "Ajax", "Ajax II", "Jong Ajax",
    "Feyenoord", "AZ", "AZ II", "Jong AZ",
}

# ══════════════════════════════════════════════════════════════════
#  TIPO DE COMPETIÇÃO
# ══════════════════════════════════════════════════════════════════

TIPO_COMPETICAO_LIGA: dict[str, str] = {
    # Ligas
    "Süper Lig":        "liga",
    "Eredivisie":       "liga",
    "Eerste Divisie":   "liga",
    "Brasileirão":      "liga",
    "La Liga":          "liga",
    "Bundesliga":       "liga",
    "Championship":     "liga",
    "EFL Championship": "liga",
    "Cymru Premier":    "liga",
    "Paulistão":        "liga",
    "2. Bundesliga":    "liga",
    "Liga Portugal":    "liga",
    "Premier League":   "liga",
    "Serie A":          "liga",
    "Ligue 1":          "liga",
    "Saudi Pro League": "liga",
    "Serie B (Itália)": "liga",
    # Copas nacionais
    "Copa del Rey":       "copa",
    "FA Cup":             "copa",
    "Copa da Inglaterra": "copa",
    "Copa da Itália":     "copa",
    "Coppa Italia":       "copa",
    "Copa da França":     "copa",
    "Coupe de France":    "copa",
    "Copa KNVB":          "copa",
    "KNVB Cup":           "copa",
    "Copa da Holanda":    "copa",
    "DFB Pokal":          "copa",
    "Copa do Brasil":     "copa",
    "Copa da Alemanha":   "copa",
    "Copa da Espanha":    "copa",
    "Taça de Portugal":   "copa",
    # Copas internacionais
    "Champions League":  "copa_inter",
    "Europa League":     "copa_inter",
    "Conference League": "copa_inter",
}

# ══════════════════════════════════════════════════════════════════
#  HIERARQUIA DE LIGAS
# ══════════════════════════════════════════════════════════════════

HIERARQUIA_LIGAS: dict[str, dict] = {
    # Copas — n_times não aplicável
    "Copa del Rey":       {"taxa": 1.00, "tier": "S+", "prob_base": 92, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "FA Cup":             {"taxa": 0.85, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da Inglaterra": {"taxa": 0.85, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da Itália":     {"taxa": 0.82, "tier": "A",  "prob_base": 84, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Coppa Italia":       {"taxa": 0.82, "tier": "A",  "prob_base": 84, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da França":     {"taxa": 0.78, "tier": "B",  "prob_base": 80, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Coupe de France":    {"taxa": 0.78, "tier": "B",  "prob_base": 80, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa KNVB":          {"taxa": 0.86, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "KNVB Cup":           {"taxa": 0.86, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da Holanda":    {"taxa": 0.86, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "DFB Pokal":          {"taxa": 0.84, "tier": "A",  "prob_base": 84, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa do Brasil":     {"taxa": 0.80, "tier": "B",  "prob_base": 80, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da Alemanha":   {"taxa": 0.84, "tier": "A",  "prob_base": 84, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Copa da Espanha":    {"taxa": 1.00, "tier": "S+", "prob_base": 92, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Taça de Portugal":   {"taxa": 0.79, "tier": "B",  "prob_base": 80, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    # ── COPAS INTERNACIONAIS ────────────────────────────────────────────────
    "Champions League":   {"taxa": 1.00, "tier": "S+", "prob_base": 92, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Europa League":      {"taxa": 0.90, "tier": "S+", "prob_base": 90, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    "Conference League":  {"taxa": 0.85, "tier": "A",  "prob_base": 86, "n_times": None, "reb_direto": 0, "reb_playoff": 0},
    # Ligas
    "Süper Lig":          {"taxa": 0.90,  "tier": "S+", "prob_base": 90, "n_times": 18, "reb_direto": 17, "reb_playoff": 0},
    "Eredivisie":         {"taxa": 0.864, "tier": "A",  "prob_base": 88, "n_times": 18, "reb_direto": 18, "reb_playoff": 16},
    "Eerste Divisie":     {"taxa": 0.864, "tier": "A",  "prob_base": 86, "n_times": 20, "reb_direto": 19, "reb_playoff": 0},
    "Brasileirão":        {"taxa": 0.842, "tier": "A",  "prob_base": 86, "n_times": 20, "reb_direto": 17, "reb_playoff": 0},
    "La Liga":            {"taxa": 0.824, "tier": "A",  "prob_base": 86, "n_times": 20, "reb_direto": 18, "reb_playoff": 0},
    "Bundesliga":         {"taxa": 0.813, "tier": "A",  "prob_base": 84, "n_times": 18, "reb_direto": 17, "reb_playoff": 16},
    "Championship":       {"taxa": 0.917, "tier": "A",  "prob_base": 88, "n_times": 24, "reb_direto": 23, "reb_playoff": 0},
    "EFL Championship":   {"taxa": 0.917, "tier": "A",  "prob_base": 88, "n_times": 24, "reb_direto": 23, "reb_playoff": 0},
    "Cymru Premier":      {"taxa": 0.80,  "tier": "B",  "prob_base": 82, "n_times": 12, "reb_direto": 11, "reb_playoff": 0},
    "Paulistão":          {"taxa": 0.80,  "tier": "B",  "prob_base": 80, "n_times": 16, "reb_direto": 13, "reb_playoff": 0},
    "2. Bundesliga":      {"taxa": 0.75,  "tier": "B",  "prob_base": 78, "n_times": 18, "reb_direto": 17, "reb_playoff": 16},
    "Liga Portugal":      {"taxa": 0.79,  "tier": "B",  "prob_base": 80, "n_times": 18, "reb_direto": 17, "reb_playoff": 16},
    "Premier League":     {"taxa": 0.731, "tier": "B",  "prob_base": 78, "n_times": 20, "reb_direto": 18, "reb_playoff": 0},
    "Serie A":            {"taxa": 0.76,  "tier": "B",  "prob_base": 78, "n_times": 20, "reb_direto": 18, "reb_playoff": 0},
    "Ligue 1":            {"taxa": 0.63,  "tier": "C",  "prob_base": 70, "n_times": 18, "reb_direto": 17, "reb_playoff": 16},
    "Saudi Pro League":   {"taxa": 0.615, "tier": "BL", "prob_base": 0,  "n_times": 18, "reb_direto": 17, "reb_playoff": 0},
    "Serie B (Itália)":   {"taxa": 0.30,  "tier": "BL", "prob_base": 0,  "n_times": 20, "reb_direto": 18, "reb_playoff": 0},
}

# ══════════════════════════════════════════════════════════════════
#  TIMES T1 POR LIGA
# ══════════════════════════════════════════════════════════════════

TIMES_T1_POR_LIGA: dict[str, set] = {
    "Serie A":        {"Juventus", "AC Milan", "Inter", "Inter de Milão", "Napoli", "Atalanta", "Roma", "Lazio"},
    "Süper Lig":      {"Fenerbahce", "Fenerbahçe", "Galatasaray", "Beşiktaş", "Besiktas", "Trabzonspor"},
    "La Liga":        {"Real Madrid", "Barcelona", "Atletico Madrid", "Atlético Madrid", "Athletic Club", "Athletic Bilbao"},
    "Bundesliga":     {"Bayern Munich", "Bayern de Munique", "Borussia Dortmund", "Bayer Leverkusen", "RB Leipzig"},
    "Premier League": {"Manchester City", "Arsenal", "Liverpool", "Chelsea", "Manchester United", "Tottenham"},
    "Brasileirão":    {"Flamengo", "Palmeiras", "Atletico Mineiro", "Atlético-MG", "Grêmio", "Internacional", "Botafogo", "Fluminense"},
    "Eredivisie":     {"Ajax", "PSV", "Feyenoord", "AZ", "Twente"},
    "Liga Portugal":  {"Benfica", "SL Benfica", "Porto", "FC Porto", "Sporting Lisboa", "Sporting CP"},
}

def _is_visitante_t1(time_fora: str, liga: str) -> bool:
    times = TIMES_T1_POR_LIGA.get(liga, set())
    tf = time_fora.lower().strip()
    return any(t.lower() in tf or tf in t.lower() for t in times)

# Ligas que exigem Over individual confirmado (V7.1.3)
LIGAS_OVER_INDIVIDUAL_OBRIGATORIO = {
    "Süper Lig", "Eredivisie", "Copa del Rey", "Primeira Divisie", "Eerste Divisie",
}

# Score 100 exige Over casa ≥ 80% (V7.1.4)
OVER_CASA_MIN_SCORE_100 = 0.80

# Parâmetros globais de odd e aprovação
RANGE_ODD_MIN        = 1.08
RANGE_ODD_MAX        = 1.60
OVER_INDIVIDUAL_MIN  = 0.70
PROB_MINIMA_APROVACAO = 70
RANGE_BILHETE_MIN    = 1.50
RANGE_BILHETE_MAX    = 1.60

# ══════════════════════════════════════════════════════════════════
#  DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class DadosSuperbet:
    xg_casa: Optional[float] = None
    xg_fora: Optional[float] = None
    gols_media_casa: Optional[float] = None
    gols_media_fora: Optional[float] = None
    posse_casa: Optional[float] = None
    posse_fora: Optional[float] = None
    finalizacoes_casa: Optional[float] = None
    finalizacoes_fora: Optional[float] = None
    chutes_gol_casa: Optional[float] = None
    chutes_gol_fora: Optional[float] = None
    grandes_chances_casa: Optional[float] = None
    grandes_chances_fora: Optional[float] = None
    xgot_casa: Optional[float] = None
    xgot_fora: Optional[float] = None
    ataques_perigosos_casa: Optional[float] = None
    ataques_perigosos_fora: Optional[float] = None

@dataclass
class DadosBetano:
    over15_casa_pct: Optional[float] = None
    over15_fora_pct: Optional[float] = None
    over15_casa_n: Optional[int] = None
    over15_fora_n: Optional[int] = None
    over25_casa_pct: Optional[float] = None
    over25_fora_pct: Optional[float] = None
    btts_casa_pct: Optional[float] = None
    btts_fora_pct: Optional[float] = None
    clean_sheet_casa_pct: Optional[float] = None
    clean_sheet_fora_pct: Optional[float] = None
    media_gols_marcados_casa: Optional[float] = None
    media_gols_marcados_fora: Optional[float] = None
    media_gols_sofridos_casa: Optional[float] = None
    media_gols_sofridos_fora: Optional[float] = None
    forma_casa: Optional[str] = None
    forma_fora: Optional[str] = None
    vitorias_casa_pct: Optional[float] = None
    # Item 9 V7.2 — Over% por competição (FootyStats)
    # Dado GERAL do time nesta competição (sem separar casa/fora — FootyStats não entrega).
    # Quando preenchido, substitui dado global da Betano no motor.
    # Risco: dado geral pode inflar/deflacionar vs real casa/fora.
    # Ganho: elimina contaminação La Liga/Campeonato no dado UCL.
    # Caso Arsenal UCL 100% vs Premier League 60% — dado global inútil.
    over15_mandante_comp: Optional[float] = None   # Over 1.5% geral mandante nesta competição
    over25_mandante_comp: Optional[float] = None   # Over 2.5% geral mandante nesta competição
    btts_mandante_comp: Optional[float] = None     # BTTS% geral mandante nesta competição
    avg_gols_mandante_comp: Optional[float] = None # Média gols/jogo mandante nesta competição
    over15_visitante_comp: Optional[float] = None  # Over 1.5% geral visitante nesta competição
    over25_visitante_comp: Optional[float] = None  # Over 2.5% geral visitante nesta competição
    btts_visitante_comp: Optional[float] = None    # BTTS% geral visitante nesta competição
    avg_gols_visitante_comp: Optional[float] = None # Média gols/jogo visitante nesta competição

@dataclass
class DadosH2H:
    total_jogos: Optional[int] = None
    vitorias_casa: Optional[int] = None
    empates: Optional[int] = None
    vitorias_fora: Optional[int] = None
    media_gols: Optional[float] = None
    btts_pct: Optional[float] = None
    over15_pct: Optional[float] = None
    over25_pct: Optional[float] = None
    resultados_recentes: list = field(default_factory=list)
    penaltis_suspeitos: list = field(default_factory=list)  # placares suspeitos de pênaltis [V7.2]

@dataclass
class FormaRecente:
    jogos_com_gol: Optional[int] = None
    jogos_com_gol_1t: Optional[int] = None
    total_jogos_amostra: Optional[int] = None
    media_gols_marcados: Optional[float] = None
    jogos_sem_marcar: Optional[int] = None
    media_gols_concedidos: Optional[float] = None
    media_gols_concedidos_1t: Optional[float] = None

@dataclass
class JogoSuperbet:
    data: str = ""
    adversario: str = ""
    gols_pro: Optional[int] = None
    gols_contra: Optional[int] = None
    em_casa: bool = True
    resultado: str = ""

@dataclass
class UltimosJogosSuperbet:
    jogos_casa: list = field(default_factory=list)
    jogos_fora: list = field(default_factory=list)
    over15_casa: Optional[float] = None
    over15_fora: Optional[float] = None
    media_gols_pro_casa: Optional[float] = None
    media_gols_pro_fora: Optional[float] = None
    media_gols_contra_casa: Optional[float] = None
    media_gols_contra_fora: Optional[float] = None
    n_jogos_casa: int = 0
    n_jogos_fora: int = 0

@dataclass
class DadosContexto:
    tipo_competicao: str = "Campeonato"
    agregado_cl: Optional[str] = None
    tem_cl_proximos_3_dias: bool = False
    tem_el_proximos_4_dias: bool = False
    total_times_liga: Optional[int] = None
    casa_posicao: Optional[int] = None
    fora_posicao: Optional[int] = None
    casa_zona_rebaixamento: bool = False
    fora_zona_rebaixamento: bool = False
    desfalques_casa: int = 0
    desfalques_fora: int = 0
    atacante_titular_casa_out: bool = False
    atacante_titular_fora_out: bool = False
    atacante_titular_casa_duvida: bool = False  # 🟡 status dúvida — penalidade reduzida D7
    atacante_titular_fora_duvida: bool = False  # 🟡 status dúvida — penalidade reduzida D7
    criativo_central_casa_out: bool = False
    criativo_central_fora_out: bool = False
    criativo_sub_casa: bool = False
    criativo_sub_fora: bool = False
    qualidade_sub_atk_casa: int = 0      # legado — mantido para compatibilidade
    qualidade_sub_atk_fora: int = 0      # legado — mantido para compatibilidade
    # D7 — minutagem real (0.0–1.0, None = não informado)
    min_ausente_atk_casa: Optional[float] = None   # % minutos do atacante ausente (casa)
    min_sub_atk_casa: Optional[float] = None       # % minutos do melhor sub disponível (casa)
    min_ausente_atk_fora: Optional[float] = None   # % minutos do atacante ausente (fora)
    min_sub_atk_fora: Optional[float] = None       # % minutos do melhor sub disponível (fora)
    linha_comprometida_casa: bool = False           # D7-B: dois+ ausentes mesma posição
    linha_comprometida_fora: bool = False
    e_derby: bool = False
    derby_ofensivo: bool = False
    freiburg_visitante_copa: bool = False
    # Item 1+8 V7.2 — Fase eliminatória
    # Valores: "grupos" | "oitavas" | "quartas" | "semis" | "final" | None
    fase_eliminatoria: str = None      # None = não copa_inter ou grupos
    jogo_volta: bool = False           # True = jogo de volta em eliminatório
    agregado_gols_ida: Optional[str] = None  # placar da ida ex: "1-2" (casa-fora)

@dataclass
class Jogo:
    time_casa: str
    time_fora: str
    liga: str
    odd: float
    tipo_competicao: str = "Campeonato"
    superbet: DadosSuperbet = field(default_factory=DadosSuperbet)
    betano: DadosBetano = field(default_factory=DadosBetano)
    h2h: DadosH2H = field(default_factory=DadosH2H)
    contexto: DadosContexto = field(default_factory=DadosContexto)
    forma_casa: FormaRecente = field(default_factory=FormaRecente)
    forma_fora: FormaRecente = field(default_factory=FormaRecente)
    desfalques_texto_casa: str = ""
    desfalques_texto_fora: str = ""
    ultimos_jogos: UltimosJogosSuperbet = field(default_factory=UltimosJogosSuperbet)
    desfalques_superbet_raw: str = ""

# Widget keys para autosave D15 — (template, tipo, default)
# ATENÇÃO: defaults devem ser idênticos ao original para restauração correta
WIDGET_KEYS: list[tuple[str, str, object]] = [
    ("casa_{i}",           "text",  ""),
    ("fora_{i}",           "text",  ""),
    ("liga_{i}",           "text",  "Liga Portugal"),
    ("odd_{i}",            "float", 1.25),
    ("tipo_{i}",           "text",  "Campeonato"),
    ("betano_{i}",         "text",  ""),
    ("superbet_{i}",       "text",  ""),
    ("h2h_{i}",            "text",  ""),
    ("forma_recente_{i}",  "text",  ""),
    ("googleia_{i}",       "text",  ""),
    ("ag_{i}",             "text",  ""),
    ("cl_{i}",             "bool",  False),
    ("el_{i}",             "bool",  False),
    ("nt_{i}",             "int",   18),
    ("pc_{i}",             "int",   1),
    ("pf_{i}",             "int",   1),
    ("creb_{i}",           "bool",  False),
    ("freb_{i}",           "bool",  False),
    ("derby_{i}",          "bool",  False),
    ("derbyof_{i}",        "bool",  False),
    ("dc_ia_{i}",          "int",   0),
    ("df_ia_{i}",          "int",   0),
    ("atk_c_ia_{i}",       "bool",  False),
    ("atk_f_ia_{i}",       "bool",  False),
    ("cri_c_ia_{i}",       "bool",  False),
    ("cri_f_ia_{i}",       "bool",  False),
    ("cri_sub_c_{i}",      "bool",  False),
    ("cri_sub_f_{i}",      "bool",  False),
    ("sub_atk_c_{i}",      "text",  "0 — Sem substituto / reserva irrelevante"),
    ("sub_atk_f_{i}",      "text",  "0 — Sem substituto / reserva irrelevante"),
    ("desf_superbet_{i}",  "text",  ""),
    ("ultimos_raw_{i}",    "text",  ""),
    # D7 — minutagem
    ("min_aus_atk_c_{i}",  "text",  ""),   # minutagem ausente atacante casa (ex: "87")
    ("min_sub_atk_c_{i}",  "text",  ""),   # minutagem melhor sub casa
    ("min_aus_atk_f_{i}",  "text",  ""),   # minutagem ausente atacante fora
    ("min_sub_atk_f_{i}",  "text",  ""),   # minutagem melhor sub fora
    ("lc_casa_{i}",        "bool",  False), # linha comprometida casa
    ("lc_fora_{i}",        "bool",  False), # linha comprometida fora
    # Item 1+8 V7.2 — fase eliminatória
    ("fase_elim_{i}",      "text",  "grupos"),  # fase da copa_inter
    ("jogo_volta_{i}",     "bool",  False),     # é jogo de volta
    ("ag_ida_{i}",         "text",  ""),        # placar da ida ex: "1-2"
    # Item 9 V7.2 — dados por competição (FootyStats) — geral por time
    ("footy_m_{i}",        "text",  ""),   # FootyStats linha mandante: btts,xGF,o15,o25,avg
    ("footy_v_{i}",        "text",  ""),   # FootyStats linha visitante: btts,xGF,o15,o25,avg
]
