"""
atlas/parsers.py
Todos os parsers de dados brutos: Betano, Superbet, H2H, forma recente,
desfalques Google IA, últimos jogos, lista de importação.
"""

from __future__ import annotations
import re
import json
from typing import Optional
from dataclasses import dataclass, field
from itertools import combinations

from atlas.config import (
    DadosBetano, DadosSuperbet, DadosH2H, FormaRecente,
    JogoSuperbet, UltimosJogosSuperbet, HIERARQUIA_LIGAS,
)

# ══════════════════════════════════════════════════════════════════
#  PARSER DE DADOS BRUTOS
# ══════════════════════════════════════════════════════════════════

def extrair_numero(texto: str, chave: str) -> Optional[float]:
    """Extrai número após uma chave em texto bruto."""
    try:
        pattern = rf"{re.escape(chave)}\s*[\n\r\t ]*([0-9]+(?:[.,][0-9]+)?)\s*%?"
        match = re.search(pattern, texto, re.IGNORECASE | re.MULTILINE)
        if match:
            val = match.group(1).replace(",", ".")
            return float(val)
    except:
        pass
    return None

def extrair_porcentagem(texto: str, chave: str) -> Optional[float]:
    """Extrai porcentagem (ex: '73%' → 0.73)."""
    val = extrair_numero(texto, chave)
    if val is not None:
        if val > 1:
            return val / 100
        return val
    return None

# ══════════════════════════════════════════════════════════════════
#  PARSERS — LÓGICA BASEADA NO FORMATO REAL DAS FONTES
#
#  FORMATO SUPERBET: Os dados chegam em blocos onde o rótulo da
#  estatística aparece numa linha, o valor do time CASA na linha
#  seguinte (ou na mesma separado por espaço), e o valor do time
#  FORA após o rótulo novamente ou na linha subsequente.
#
#  O padrão real observado no exemplo fornecido é:
#    [VALOR_CASA]
#    [ROTULO_ESTATISTICA]
#    [VALOR_FORA]
#
#  FORMATO BETANO: As estatísticas de Over/Under aparecem como:
#    "Mais de 1.5   91%   2.57   83%   2"
#  onde o 1º % é do time casa (Local) e o 2º % é do visitante.
#  O número entre eles (2.57) é a odd da casa de apostas — ignorar.
#
#  FORMATO H2H (Superbet/qualquer fonte): Placares no formato
#    "3 - 1" ou "0 - 3" são extraídos e calculados automaticamente.
# ══════════════════════════════════════════════════════════════════

def _num(s: str) -> Optional[float]:
    """Converte string para float, aceita vírgula ou ponto."""
    try:
        return float(str(s).strip().replace(",", ".").replace("%", ""))
    except:
        return None

def _pct(s: str) -> Optional[float]:
    """Converte string de porcentagem para decimal (73 → 0.73)."""
    v = _num(s)
    if v is None:
        return None
    return v / 100 if v > 1 else v


def parsear_superbet(texto: str) -> DadosSuperbet:
    """
    Parser Superbet.

    O Superbet exibe as estatísticas no formato:
        [VALOR_CASA]
        [RÓTULO]
        [VALOR_FORA]

    Exemplo real:
        2.6
        Gols
        2.0
        62.2%
        Posse de bola
        52.3%
        2.1
        Gols esperados (xG)
        1.5
    """
    d = DadosSuperbet()
    if not texto.strip():
        return d

    linhas = [l.strip() for l in texto.splitlines()]
    linhas = [l for l in linhas if l]  # Remove vazias

    # Mapeamento: rótulo (lowercase parcial) → campo destino
    MAPA = {
        "gols esperados": ("xg_casa", "xg_fora"),
        "xg":             ("xg_casa", "xg_fora"),
        "posse de bola":  ("posse_casa", "posse_fora"),
        "posse":          ("posse_casa", "posse_fora"),
        "finalizações totais": ("finalizacoes_casa", "finalizacoes_fora"),
        "finalizacoes totais": ("finalizacoes_casa", "finalizacoes_fora"),
        "chutes no gol":  ("chutes_gol_casa", "chutes_gol_fora"),
        "chutes a gol":   ("chutes_gol_casa", "chutes_gol_fora"),
        "grandes chances criadas": ("grandes_chances_casa", "grandes_chances_fora"),
        "xgot":           ("xgot_casa", "xgot_fora"),
        "ataques perigosos": ("ataques_perigosos_casa", "ataques_perigosos_fora"),
    }

    # Identificar rótulos conhecidos e seus índices
    def eh_rotulo(linha: str) -> Optional[tuple]:
        ll = linha.lower()
        for chave, campos in MAPA.items():
            if chave in ll:
                return campos
        return None

    def eh_numero(linha: str) -> bool:
        return bool(re.match(r"^-?\d+(?:[.,]\d+)?%?$", linha))

    # Varredura: procura padrão [número | rótulo | número]
    # Aceita tanto [valor_casa → rótulo → valor_fora] quanto [rótulo → valor_casa \n valor_fora]
    i = 0
    while i < len(linhas):
        campos = eh_rotulo(linhas[i])
        if campos:
            # Padrão A: rótulo na linha i, valores nas linhas i+1 e i+2 (ou i-1 e i+1)
            val_antes = _num(linhas[i-1]) if i > 0 and eh_numero(linhas[i-1]) else None
            val_depois1 = _num(linhas[i+1]) if i+1 < len(linhas) and eh_numero(linhas[i+1]) else None
            val_depois2 = _num(linhas[i+2]) if i+2 < len(linhas) and eh_numero(linhas[i+2]) else None

            campo_casa, campo_fora = campos
            atual_casa = getattr(d, campo_casa)

            if val_antes is not None and val_depois1 is not None and atual_casa is None:
                # Padrão: VALOR_CASA \n RÓTULO \n VALOR_FORA
                setattr(d, campo_casa, val_antes)
                setattr(d, campo_fora, val_depois1)
            elif val_depois1 is not None and val_depois2 is not None and atual_casa is None:
                # Padrão: RÓTULO \n VALOR_CASA \n VALOR_FORA
                setattr(d, campo_casa, val_depois1)
                setattr(d, campo_fora, val_depois2)
            elif val_antes is not None and val_depois1 is None and atual_casa is None:
                # Só tem valor antes (casa) — fora não identificado
                setattr(d, campo_casa, val_antes)

        # Caso especial: linha contém rótulo + dois números na mesma linha
        # Ex: "2.1 Gols esperados (xG) 1.5"
        match_inline = re.match(r"^(-?\d+(?:[.,]\d+)?%?)\s+(.+?)\s+(-?\d+(?:[.,]\d+)?%?)$", linhas[i])
        if match_inline:
            campos = eh_rotulo(match_inline.group(2))
            if campos:
                v1 = _num(match_inline.group(1))
                v2 = _num(match_inline.group(3))
                campo_casa, campo_fora = campos
                if v1 is not None and v2 is not None and getattr(d, campo_casa) is None:
                    setattr(d, campo_casa, v1)
                    setattr(d, campo_fora, v2)

        # Caso: "Gols" sozinho, sem qualificador (média de gols marcados)
        if linhas[i].lower().strip() in ["gols", "gols marcados"]:
            val_c = _num(linhas[i-1]) if i > 0 and eh_numero(linhas[i-1]) else None
            val_f = _num(linhas[i+1]) if i+1 < len(linhas) and eh_numero(linhas[i+1]) else None
            if val_c is not None and d.gols_media_casa is None:
                d.gols_media_casa = val_c
            if val_f is not None and d.gols_media_fora is None:
                d.gols_media_fora = val_f

        i += 1

    return d


def parsear_betano(texto: str) -> DadosBetano:
    """
    Parser Betano (V7.2 — mudança de Geral para Local/Visitante).

    ESTRUTURA ESPERADA DO TEXTO COLADO (tudo junto, em ordem):

    ① Bloco Época (topo da página):
        33%Vitórias25%
        1.75Golos1.42
        58%Ambas as equipas para marcar83%
        33%Sem marcar8%
        8%Baliza inviolada8%

    ② Mais/Menos → aba LOCAL (dados do mandante jogando em casa):
        Mais de 1.5   82%   3.4   (o % aqui é do MANDANTE em casa)

    ③ Mais/Menos → aba VISITANTE (dados do visitante jogando fora):
        Mais de 1.5   60%   1.2   (o % aqui é do VISITANTE fora)

    O parser extrai os percentuais de Over 1.5 de cada bloco na ordem
    em que aparecem: 1º encontrado = mandante (Local), 2º = visitante.

    V7.2: a aba "Geral" foi substituída por Local+Visitante para maior precisão.
    Evidência: Brøndby 60% como visitante vs 71% no Geral — diferença significativa.
    """
    d = DadosBetano()
    if not texto.strip():
        return d

    t = texto

    # ── Over/Under ────────────────────────────────────────────────
    # O Betano exibe em dois formatos possíveis:
    #
    # FORMATO A (mesma linha):
    #   "Mais de 1.5   91%   2.57   83%   2"
    #
    # FORMATO B (múltiplas linhas — quando copiado da aba tabular):
    #   "Mais de 1.5"
    #   "91‏%"        ← pode ter caractere invisível ‏ (Unicode U+200F)
    #   "2.57"
    #   "83‏%"
    #   "2"
    #
    # Solução: normalizar o texto removendo caracteres invisíveis
    # e tentar ambos os formatos.

    # Remover caracteres invisíveis Unicode que o Betano insere
    t_clean = re.sub(r'[\u200f\u200e\u200b\u00a0]', '', t)

    # Formato A — tudo na mesma linha (só se Formato C não preencheu)
    if d.over15_casa_pct is None:
        pat_over_A = re.compile(
            r'Mais(?:\s+de)?\s+(\d+[.,]\d+)\s+'
            r'(\d+(?:[.,]\d+)?)\s*%\s*'
            r'(?:\d+(?:[.,]\d+)?\s+)?'
            r'(\d+(?:[.,]\d+)?)\s*%'
            r'(?:\s+(\d+))?',
            re.IGNORECASE
        )
        for m in pat_over_A.finditer(t_clean):
            limite = m.group(1).replace(',', '.')
            pct_c = _pct(m.group(2))
            pct_f = _pct(m.group(3))
            n_str = m.group(4)
            n = int(n_str) if n_str and n_str.isdigit() else None
            if limite == '1.5' and d.over15_casa_pct is None:
                d.over15_casa_pct = pct_c
                d.over15_fora_pct = pct_f
                if n is not None:
                    d.over15_casa_n = n
                    d.over15_fora_n = n
            elif limite == '2.5' and d.over25_casa_pct is None:
                d.over25_casa_pct = pct_c
                d.over25_fora_pct = pct_f

    # Formato B — multilinhas: captura bloco após "Mais de X.X"
    if d.over15_casa_pct is None:
        linhas_clean = [l.strip() for l in t_clean.splitlines() if l.strip()]
        i = 0
        while i < len(linhas_clean):
            m_titulo = re.match(r'Mais(?:\s+de)?\s+(\d+[.,]\d+)', linhas_clean[i], re.IGNORECASE)
            if m_titulo:
                limite = m_titulo.group(1).replace(',', '.')
                # Coletar até 6 linhas seguintes: 2 percentuais + possível denominador
                percentuais = []
                denominador = None
                for j in range(i+1, min(i+7, len(linhas_clean))):
                    m_pct = re.match(r'^(\d+(?:[.,]\d+)?)\s*%?$', linhas_clean[j])
                    if m_pct:
                        raw_str = m_pct.group(1)
                        raw_f = float(raw_str.replace(',', '.'))
                        tem_pct = '%' in linhas_clean[j]
                        # Ignorar odds: float sem % entre 1.0 e 10.0 (ex: 1.5, 1.53, 2.57)
                        eh_odd = (not tem_pct and 1.0 < raw_f < 10.0 and '.' in raw_str)
                        if eh_odd:
                            pass  # pular — é odd separadora de colunas
                        else:
                            v = _pct(raw_str)
                            if v is not None and v <= 1.0:
                                percentuais.append(v)
                            elif len(percentuais) == 2 and raw_str.isdigit():
                                # número inteiro após 2 percentuais = denominador
                                denominador = int(raw_str)
                    if len(percentuais) == 2 and j+1 < len(linhas_clean):
                        # verificar linha seguinte como denominador
                        prox = linhas_clean[j+1].strip()
                        if prox.isdigit():
                            denominador = int(prox)
                        break
                if len(percentuais) >= 2:
                    if limite == '1.5' and d.over15_casa_pct is None:
                        d.over15_casa_pct = percentuais[0]
                        d.over15_fora_pct = percentuais[1]
                        if denominador is not None:
                            d.over15_casa_n = denominador
                            d.over15_fora_n = denominador
                    elif limite == '2.5' and d.over25_casa_pct is None:
                        d.over25_casa_pct = percentuais[0]
                        d.over25_fora_pct = percentuais[1]
            i += 1

    # ── BTTS: "27% Ambas as equipes devem marcar 45%" ─────────────
    btts_m = re.search(
        r'(\d+(?:[.,]\d+)?)\s*%\s*'
        r'Ambas as equip(?:es devem marcar|as para marcar)\s*'
        r'(\d+(?:[.,]\d+)?)\s*%',
        t_clean, re.IGNORECASE
    )
    if btts_m:
        d.btts_casa_pct = _pct(btts_m.group(1))
        d.btts_fora_pct = _pct(btts_m.group(2))

    # ── Clean Sheet: "73% Jogos sem sofrer gols 18%" ──────────────
    cs_m = re.search(
        r'(\d+(?:[.,]\d+)?)\s*%\s*'
        r'(?:Jogos sem sofrer gol[os]s?|Baliza inviolada[^%\d]*)\s*'
        r'(\d+(?:[.,]\d+)?)\s*%',
        t_clean, re.IGNORECASE
    )
    if cs_m:
        d.clean_sheet_casa_pct = _pct(cs_m.group(1))
        d.clean_sheet_fora_pct = _pct(cs_m.group(2))

    # ── Vitórias: "82% Vitórias 27%" ─────────────────────────────
    vit_m = re.search(
        r'(\d+(?:[.,]\d+)?)\s*%\s*Vitórias\s*(\d+(?:[.,]\d+)?)\s*%',
        t_clean, re.IGNORECASE
    )
    if vit_m:
        d.vitorias_casa_pct = _pct(vit_m.group(1))

    # ── Média gols marcados ───────────────────────────────────────
    mgm = re.search(
        r'Média Gols Marcados\s+'
        r'(\d+(?:[.,]\d+)?)\s+'
        r'(?:\d+\s+)?'
        r'(\d+(?:[.,]\d+)?)',
        t_clean, re.IGNORECASE
    )
    if mgm:
        d.media_gols_marcados_casa = _num(mgm.group(1))
        d.media_gols_marcados_fora = _num(mgm.group(2))

    # ── Média gols concedidos ─────────────────────────────────────
    mgc = re.search(
        r'Média Gols Concedidos\s+'
        r'(\d+(?:[.,]\d+)?)\s+'
        r'(?:\d+\s+)?'
        r'(\d+(?:[.,]\d+)?)',
        t_clean, re.IGNORECASE
    )
    if mgc:
        d.media_gols_sofridos_casa = _num(mgc.group(1))
        d.media_gols_sofridos_fora = _num(mgc.group(2))

    # ── Forma recente ─────────────────────────────────────────────
    # O Betano pode exibir a forma de duas formas:
    # Compacta: "VVEVV" ou "V V E V V" (em sequência na mesma linha)
    # Expandida: cada letra em linha separada
    #
    # Problema com início de temporada (< 5 jogos por time):
    # Com 2 jogos cada, os 4 tokens D/V/E/D ficam todos numa sequência
    # e o parser antigo os agrupava como um bloco único "DVVE".
    #
    # Solução: detectar separação entre os dois blocos de forma
    # usando linhas que não contêm apenas V, E ou D como delimitadores.
    # Cada grupo contíguo de tokens V/E/D separado por texto não-VED
    # é tratado como a forma de um time distinto.

    linhas_forma = t_clean.splitlines()
    grupos_forma = []
    grupo_atual = []

    for linha in linhas_forma:
        l = linha.strip()
        # Linha com apenas letras V/E/D (com ou sem espaços) — pertence ao bloco atual
        tokens_linha = re.findall(r'\b([VED])\b', l)
        # Verificar se a linha contém SOMENTE tokens de forma (sem outro texto relevante)
        resto = re.sub(r'\b[VED]\b', '', l).strip()
        resto_limpo = re.sub(r'[\s\|\-\,\.]+', '', resto)

        if tokens_linha and not resto_limpo:
            # Linha pura de forma — acumular no grupo atual
            grupo_atual.extend(tokens_linha)
        elif tokens_linha and len(tokens_linha) >= 3 and not resto_limpo:
            # Linha com múltiplos tokens e sem texto — bloco compacto
            grupo_atual.extend(tokens_linha)
        else:
            # Linha com texto ou linha vazia — potencial separador de times
            if grupo_atual:
                grupos_forma.append(''.join(grupo_atual))
                grupo_atual = []
            # Verificar se há tokens embutidos numa linha com texto
            # (ex: "Últimos 5: V V E D V") — mas só se forem >= 3 tokens
            if len(tokens_linha) >= 3:
                grupos_forma.append(''.join(tokens_linha))

    if grupo_atual:
        grupos_forma.append(''.join(grupo_atual))

    # Filtrar grupos válidos (mínimo 1 token)
    grupos_forma = [g for g in grupos_forma if len(g) >= 1]

    # Fallback: se não conseguiu separar em 2 grupos mas tem tokens suficientes
    # usar o método antigo de split a cada 5
    if len(grupos_forma) < 2:
        todos_tokens = re.findall(r'\b([VED])\b', t_clean)
        grupos_forma = []
        bloco_tmp = []
        for ch in todos_tokens:
            bloco_tmp.append(ch)
            if len(bloco_tmp) == 5:
                grupos_forma.append(''.join(bloco_tmp))
                bloco_tmp = []
        if bloco_tmp and len(bloco_tmp) >= 1:
            grupos_forma.append(''.join(bloco_tmp))

    if len(grupos_forma) >= 1:
        d.forma_casa = grupos_forma[0][:5]
    if len(grupos_forma) >= 2:
        d.forma_fora = grupos_forma[1][:5]

    return d


def parsear_desfalques(texto: str) -> tuple:
    """
    Interpreta texto bruto de desfalques da Superbet.

    Formato real (copiado da aba Lesionados/Suspensos da Superbet):
        Nome do Jogador
        Lesionado          ← ou "Suspenso" / "Incerto"
        NN                 ← número da camisa (IGNORAR — não é quantidade)
        Próximo Jogador
        Incerto
        NN

    Retorna: (n_lesionados_certos, n_incertos, lista_nomes_certos, lista_nomes_incertos)

    IMPORTANTE: "Incerto" conta como 0.5 para o score (agrava mas menos).
    """
    if not texto.strip():
        return 0, 0, [], []

    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    nomes_certos = []
    nomes_incertos = []

    # Status reconhecidos
    STATUS = {"lesionado", "suspenso", "expulso", "lesão", "lesionados",
              "suspensos", "ausente", "fora"}
    INCERTO_SET = {"incerto", "dúvida", "duvidoso", "questionable", "doubt"}

    i = 0
    while i < len(linhas):
        linha = linhas[i].lower()

        # Linha é um status → o nome estava na linha anterior
        if linha in STATUS and i > 0:
            nome_candidato = linhas[i - 1]
            # Verificar que não é um número (jersey)
            if not re.match(r'^\d+$', nome_candidato):
                if nome_candidato not in nomes_certos and nome_candidato not in nomes_incertos:
                    nomes_certos.append(linhas[i - 1])
        elif linha in INCERTO_SET and i > 0:
            nome_candidato = linhas[i - 1]
            if not re.match(r'^\d+$', nome_candidato):
                if nome_candidato not in nomes_certos and nome_candidato not in nomes_incertos:
                    nomes_incertos.append(linhas[i - 1])

        i += 1

    # Fallback A: Nome / Lesionado / NN — varredura por jersey depois do status
    if not nomes_certos and not nomes_incertos:
        for i in range(len(linhas)):
            if re.match(r'^\d{1,2}$', linhas[i]) and i >= 2:
                status = linhas[i-1].lower()
                nome = linhas[i-2]
                if status in STATUS and not re.match(r'^\d+$', nome) and nome not in nomes_certos:
                    nomes_certos.append(nome)
                elif status in INCERTO_SET and not re.match(r'^\d+$', nome) and nome not in nomes_incertos:
                    nomes_incertos.append(nome)

    # Fallback B: NN / Nome — jersey ANTES do nome (ex: 10 / Lautaro Martinez)
    if not nomes_certos and not nomes_incertos:
        for i in range(len(linhas)):
            if re.match(r'^\d{1,2}$', linhas[i]) and i + 1 < len(linhas):
                nome = linhas[i + 1]
                if (not re.match(r'^\d+$', nome)
                        and nome.lower() not in STATUS
                        and nome.lower() not in INCERTO_SET
                        and nome not in nomes_certos):
                    nomes_certos.append(nome)

    return len(nomes_certos), len(nomes_incertos), nomes_certos, nomes_incertos



# ══════════════════════════════════════════════════════════════════
#  D7 — PARSER DESFALQUES SUPERBET
#  Formato: NúmeroCamisa / Nome / Status (Lesionado|Suspenso|Incerto)
#  Aceita dois times no mesmo bloco (separados pelo nome do time)
#  ou somente um time.
# ══════════════════════════════════════════════════════════════════

def _parsear_bloco_desfalques_superbet(linhas: list) -> tuple:
    """
    Processa lista de linhas de UM time.
    Retorna (n_certos, n_incertos, lista_certos, lista_incertos)
    Formato Superbet: NN / Nome / Status (em qualquer ordem de linhas)
    """
    STATUS_CERTO   = {"lesionado", "suspenso", "expulso", "ausente", "fora"}
    STATUS_INCERTO = {"incerto", "dúvida", "duvidoso", "questionable", "doubt"}

    nomes_certos   = []
    nomes_incertos = []
    i = 0
    while i < len(linhas):
        linha_low = linhas[i].lower().strip()
        # Número de camisa — ignora
        if re.match(r'^\d{1,2}$', linhas[i].strip()):
            i += 1
            continue
        # Linha de status → nome está na linha anterior (se não for número)
        if linha_low in STATUS_CERTO and i > 0:
            nome = linhas[i - 1].strip()
            if not re.match(r'^\d+$', nome) and nome not in nomes_certos + nomes_incertos:
                nomes_certos.append(nome)
        elif linha_low in STATUS_INCERTO and i > 0:
            nome = linhas[i - 1].strip()
            if not re.match(r'^\d+$', nome) and nome not in nomes_certos + nomes_incertos:
                nomes_incertos.append(nome)
        i += 1

    # Fallback: NN / Nome / Status (jersey antes do nome)
    if not nomes_certos and not nomes_incertos:
        for i in range(len(linhas) - 2):
            if re.match(r'^\d{1,2}$', linhas[i].strip()):
                nome   = linhas[i + 1].strip()
                status = linhas[i + 2].strip().lower()
                if re.match(r'^\d+$', nome):
                    continue
                if status in STATUS_CERTO and nome not in nomes_certos:
                    nomes_certos.append(nome)
                elif status in STATUS_INCERTO and nome not in nomes_incertos:
                    nomes_incertos.append(nome)

    return len(nomes_certos), len(nomes_incertos), nomes_certos, nomes_incertos


def parsear_desfalques_superbet(texto: str, time_casa: str = "", time_fora: str = "") -> dict:
    """
    D7 — Parser de desfalques copiados da Superbet.

    Aceita:
    - Bloco de dois times juntos (separados pelo nome do time)
    - Bloco de um único time

    Retorna dict com chaves:
      casa: (n_certos, n_incertos, lista_certos, lista_incertos)
      fora: (n_certos, n_incertos, lista_certos, lista_incertos)
      texto_casa: str  — bloco do mandante para exibição
      texto_fora: str  — bloco do visitante para exibição
    """
    vazio = (0, 0, [], [])
    resultado = {"casa": vazio, "fora": vazio, "texto_casa": "", "texto_fora": ""}

    if not texto.strip():
        return resultado

    linhas = [l for l in texto.splitlines() if l.strip()]

    # Detectar separação de times:
    # Procura por linha que seja "Jogadores ausentes" ou nome de time
    # O padrão da Superbet é: NomeTime → "Jogadores ausentes" → jogadores
    SEPARADORES = {"jogadores ausentes", "jogadores ausente", "lesionados", "suspensos"}

    # Índices onde começa cada time
    blocos = []  # lista de (idx_inicio, idx_fim_excl)

    # Tentar separar pelo marcador "Jogadores ausentes"
    indices_sep = [i for i, l in enumerate(linhas) if l.strip().lower() in SEPARADORES]

    if len(indices_sep) >= 2:
        # Dois times: time1 = antes do 2º separador, time2 = do 2º em diante
        mid = indices_sep[1]
        blocos = [(0, mid), (mid, len(linhas))]
    elif len(indices_sep) == 1:
        # Um separador — tudo é um time
        blocos = [(0, len(linhas))]
    else:
        # Sem separador explícito — tentar detectar mudança de time
        # por linha que não seja número, status nem nome de jogador típico
        # Fallback: tratar como bloco único
        blocos = [(0, len(linhas))]

    def _extrair_bloco(inicio, fim):
        return linhas[inicio:fim]

    if len(blocos) == 2:
        bloco1 = _extrair_bloco(*blocos[0])
        bloco2 = _extrair_bloco(*blocos[1])
        resultado["casa"] = _parsear_bloco_desfalques_superbet(bloco1)
        resultado["fora"] = _parsear_bloco_desfalques_superbet(bloco2)
        resultado["texto_casa"] = "\n".join(bloco1)
        resultado["texto_fora"] = "\n".join(bloco2)
    else:
        # Bloco único — associar ao time_casa por padrão
        bloco = _extrair_bloco(*blocos[0])
        resultado["casa"] = _parsear_bloco_desfalques_superbet(bloco)
        resultado["texto_casa"] = "\n".join(bloco)

    return resultado


# ══════════════════════════════════════════════════════════════════
#  D12 — PARSER ÚLTIMOS JOGOS SUPERBET
#  Formato: DD.MM. / TimeCasa-TimeFora / Gols-Gols / Resultado
#  Dois blocos separados (um por time), ou blocos juntos.
# ══════════════════════════════════════════════════════════════════

def _parsear_jogos_raw(texto: str) -> list:
    """
    Extrai jogos brutos do formato real da Superbet.
    Formato:
        DD.MM.
        TimeCasa
        -
        TimeFora
        G - G
        V/E/D
    Retorna lista de (data, time_a, time_b, placar, resultado).
    """
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    jogos_raw = []
    i = 0
    while i < len(linhas):
        if re.match(r'^\d{2}\.\d{2}\.', linhas[i]):
            data = linhas[i]
            j = i + 1
            # Coletar time_a até separador "-" isolado
            time_a_parts = []
            while j < len(linhas) and linhas[j] != '-':
                time_a_parts.append(linhas[j])
                j += 1
            time_a = " ".join(time_a_parts)
            j += 1  # pular o "-"
            # Coletar time_b até linha de placar
            time_b_parts = []
            while j < len(linhas) and not re.match(r'^\d+\s*[-–]\s*\d+$', linhas[j]):
                time_b_parts.append(linhas[j])
                j += 1
            time_b = " ".join(time_b_parts)
            placar    = linhas[j] if j < len(linhas) else ""
            resultado = linhas[j + 1].upper() if j + 1 < len(linhas) else ""
            jogos_raw.append((data, time_a, time_b, placar, resultado))
            i = j + 2
        else:
            i += 1
    return jogos_raw


def _calcular_metricas_ultimos_jogos(jogos: list) -> dict:
    """Calcula over15%, média gols pró/contra de uma lista de JogoSuperbet."""
    if not jogos:
        return {"over15": None, "media_pro": None, "media_contra": None, "n": 0}
    total_com_placar = sum(1 for j in jogos if j.gols_pro is not None)
    if not total_com_placar:
        return {"over15": None, "media_pro": None, "media_contra": None, "n": 0}
    over15       = sum(1 for j in jogos if j.gols_pro is not None and j.gols_contra is not None
                       and (j.gols_pro + j.gols_contra) > 1)
    media_pro    = sum(j.gols_pro for j in jogos if j.gols_pro is not None) / total_com_placar
    media_contra = sum(j.gols_contra for j in jogos if j.gols_contra is not None) / total_com_placar
    return {
        "over15":       over15 / total_com_placar,
        "media_pro":    round(media_pro,    2),
        "media_contra": round(media_contra, 2),
        "n":            total_com_placar
    }


def _construir_jogo_superbet(data, time_a, time_b, placar, resultado, nome_time):
    """Converte um jogo raw em JogoSuperbet, detectando se jogou em casa ou fora."""
    nome_low = nome_time.lower() if nome_time else ""
    em_casa = True
    if nome_low:
        if nome_low in time_a.lower():
            em_casa = True
            adversario = time_b
        elif nome_low in time_b.lower():
            em_casa = False
            adversario = time_a
        else:
            em_casa = True
            adversario = time_b
    else:
        adversario = time_b

    m = re.match(r'(\d+)\s*[-–]\s*(\d+)', placar)
    gols_pro = gols_contra = None
    if m:
        g1, g2 = int(m.group(1)), int(m.group(2))
        gols_pro, gols_contra = (g1, g2) if em_casa else (g2, g1)

    res_map = {"v": "V", "e": "E", "d": "D", "w": "V", "l": "D"}
    res = res_map.get(resultado.lower(), resultado[:1] if resultado else "")

    return JogoSuperbet(
        data=data, adversario=adversario,
        gols_pro=gols_pro, gols_contra=gols_contra,
        em_casa=em_casa, resultado=res
    )


def parsear_ultimos_jogos_superbet(
    texto_casa: str,
    texto_fora: str,
    nome_casa: str = "",
    nome_fora: str = ""
) -> UltimosJogosSuperbet:
    """
    D12 — Parser dos últimos jogos copiados da Superbet.

    Formato real (campo único, dois times colados):
        DD.MM.
        TimeCasa
        -
        TimeFora
        G - G
        V/E/D

    texto_casa: bloco do mandante (split por linha em branco feito antes)
    texto_fora: bloco do visitante

    Se texto_fora estiver vazio, tenta separar automaticamente pelo nome dos times
    detectado no texto_casa.
    """
    uj = UltimosJogosSuperbet()

    def _aplicar(jogos, destino):
        m = _calcular_metricas_ultimos_jogos(jogos)
        if destino == "casa":
            uj.jogos_casa             = jogos
            uj.over15_casa            = m["over15"]
            uj.media_gols_pro_casa    = m["media_pro"]
            uj.media_gols_contra_casa = m["media_contra"]
            uj.n_jogos_casa           = m["n"]
        else:
            uj.jogos_fora             = jogos
            uj.over15_fora            = m["over15"]
            uj.media_gols_pro_fora    = m["media_pro"]
            uj.media_gols_contra_fora = m["media_contra"]
            uj.n_jogos_fora           = m["n"]

    # Caso 1: dois blocos separados (linha em branco entre eles)
    if texto_casa.strip() and texto_fora.strip():
        raw_c = _parsear_jogos_raw(texto_casa)
        raw_f = _parsear_jogos_raw(texto_fora)
        _aplicar([_construir_jogo_superbet(*r, nome_casa) for r in raw_c], "casa")
        _aplicar([_construir_jogo_superbet(*r, nome_fora) for r in raw_f], "fora")
        return uj

    # Caso 2: tudo num bloco só (sem separação por linha em branco)
    texto_total = texto_casa.strip() or texto_fora.strip()
    if not texto_total:
        return uj

    raw_todos = _parsear_jogos_raw(texto_total)
    if not raw_todos:
        return uj

    # Detectar nomes dos times automaticamente se não fornecidos
    _nome_c = nome_casa or raw_todos[0][1]  # time_a do primeiro jogo = mandante
    # time visitante = primeiro time_a que não é o mandante
    _nome_f = nome_fora
    if not _nome_f:
        for _, ta, tb, _, _ in raw_todos:
            if _nome_c.lower() not in ta.lower():
                _nome_f = ta
                break

    jogos_c, jogos_f = [], []
    for r in raw_todos:
        _, time_a, time_b, _, _ = r
        # Atribuir ao grupo pelo nome do time que aparece no confronto
        eh_casa = (_nome_c.lower() in time_a.lower() or _nome_c.lower() in time_b.lower())
        if eh_casa:
            jogos_c.append(_construir_jogo_superbet(*r, _nome_c))
        else:
            jogos_f.append(_construir_jogo_superbet(*r, _nome_f))

    _aplicar(jogos_c, "casa")
    _aplicar(jogos_f, "fora")
    return uj


# ══════════════════════════════════════════════════════════════════
#  PARSER — RESPOSTA DO GOOGLE IA (Modo IA / AI Overview)
# ══════════════════════════════════════════════════════════════════

# Palavras que identificam jogadores ofensivos/criativos na resposta
PALAVRAS_OFENSIVO = {
    "atacante", "centroavante", "ponta", "avante", "striker",
    "forward", "winger", "artilheiro", "goleador", "9",
}
PALAVRAS_CRIATIVO = {
    "meia", "criativo", "camisa 10", "armador", "playmaker",
    "enganche", "trequartista", "meio-ofensivo", "10",
}
PALAVRAS_SUBSTITUTO = {
    "substitui", "substituirá", "retornou", "voltou", "disponível",
    "deve jogar", "está de volta", "retorna", "convocado", "titular esperado",
}

@dataclass
class InfoDesfalqueIA:
    """Resultado parseado da resposta do Google IA para um time."""
    lesionados: list = field(default_factory=list)      # nomes confirmados fora
    incertos: list = field(default_factory=list)        # nomes com dúvida
    substitutos: list = field(default_factory=list)     # nomes que substituem
    tem_atacante_out: bool = False
    tem_criativo_out: bool = False
    tem_substituto_atacante: bool = False
    qualidade_sub_atk: int = 0   # 0=sem sub, 1=queda, 2=competente, 3=estrela (legado)
    gols_ausente: int = 0        # gols somados dos ausentes (temporada atual)
    assists_ausente: int = 0     # assistências somadas dos ausentes
    raw_texto: str = ""          # texto original colado
    # D7 — minutagem
    min_ausente_atk: Optional[float] = None   # % minutos ausente titular (0.0–1.0)
    min_melhor_sub: Optional[float] = None    # % minutos do melhor sub disponível
    linha_comprometida: bool = False          # dois+ ausentes na mesma posição ofensiva


def _limpar_texto_desfalques(texto: str) -> str:
    """
    Remove corpo do prompt antes de parsear — suporta múltiplos formatos.
    """
    import re as _re
    # Prio 1: TIME CASA:
    m = _re.search(r'(?i)time\s+casa\s*:', texto)
    if m:
        return texto[m.start():]
    # Prio 1.5: formato [NOME DO TIME]: com colchetes — preserva cabeçalhos para divisão de blocos
    m15 = _re.search(r'(?m)^\[([A-ZÁÀÂÃÉÊÍÓÔÕÚÜ][\w\s\.\-]{2,40})\]\s*:', texto)
    if m15:
        # Normaliza removendo colchetes mas mantendo "NOME:" para extrair_bloco funcionar
        return _re.sub(r'\[([A-ZÁÀÂÃÉÊÍÓÔÕÚÜ][\w\s\.\-]{2,40})\]\s*:', r'\1:', texto)
    # Prio 2: cabeçalho por nome de time em maiúsculas (LEEDS UNITED:)
    m2 = _re.search(r'(?m)^[A-ZÁÀÂÃÉÊÍÓÔÕÚÜ][\w\s\.\-]{2,40}:\s*$', texto)
    if m2:
        return texto[m2.start():]
    # Prio 3: primeira linha com pipe
    for i, linha in enumerate(texto.splitlines()):
        l = linha.strip()
        if "|" in l and len(l) > 8 and not l.lower().startswith(("para ", "resp", "ignore", "1.", "2.", "3.")):
            return "\n".join(texto.splitlines()[i:])
    return texto


def parsear_resposta_google_ia(texto: str, time_casa: str, time_fora: str) -> tuple:
    """
    Interpreta resposta do Google IA (Modo IA) sobre desfalques de um jogo.
    Retorna: (InfoDesfalqueIA_casa, InfoDesfalqueIA_fora)
    """
    if not texto.strip():
        return InfoDesfalqueIA(), InfoDesfalqueIA()
    # Limpar prompt embutido antes de parsear
    texto = _limpar_texto_desfalques(texto)
    if not texto.strip():
        return InfoDesfalqueIA(), InfoDesfalqueIA()

    STATUS_FORA = {
        "lesionado", "lesao", "lesão", "machucado", "fora", "ausente",
        "nao joga", "não joga", "desfalque", "suspenso", "injured", "out",
        "joelho", "tornozelo", "muscular", "coxa", "panturrilha",
        "contusao", "contusão", "cirurgia", "operacao", "operação",
        "recuperacao", "recuperação", "knee", "hamstring", "ankle", "thigh",
    }
    STATUS_INCERTO = {
        "incerto", "duvida", "dúvida", "questionavel", "questionável",
        "pode ser poupado", "questionable", "doubt",
    }
    PALAVRAS_SUB = {
        "deve assumir", "deve ser titular", "sera titular", "será titular",
        "vai jogar", "deve jogar", "substituira", "substituirá",
        "retornou", "voltou", "esta de volta", "está de volta", "retorna",
    }
    PALAVRAS_DISP = {"disponivel", "disponível", "convocado"}

    NOME_RE = (
        r"(?<![a-záéíóúàâêôãõüçñ])"
        r"([A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÑ][a-záéíóúàâêôãõüçñ]+"
        r"(?:\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÜÇÑ][a-záéíóúàâêôãõüçñ-]+){1,3})"
    )

    def normalizar(nome):
        partes = nome.strip().split()
        return " ".join(partes[:2]) if len(partes) >= 2 else nome.strip()

    def extrair_bloco(nome_time, texto_completo, outro_time=""):
        token = nome_time.lower().split()[0]
        outro = outro_time.lower().split()[0] if outro_time else ""
        tl = texto_completo.lower()
        idx = tl.find(token)
        if idx == -1:
            return texto_completo
        if outro:
            idx2 = tl.find(outro, idx + len(token) + 10)
            if idx2 > idx:
                return texto_completo[idx:idx2]
        return texto_completo[idx:idx + 800]

    def detectar_jogadores_formato_pipe(bloco):
        """
        Parser robusto — suporta variações reais do Google IA:
        - Com ou sem "-" no início
        - Posições em PT livre: centroavante, ponta, meia armador
        - Qualidade do sub inferida pelo texto
        - Status com parênteses: "Lesionado (coxa)"
        """
        info = InfoDesfalqueIA(raw_texto=bloco)
        TOKENS_ATK = {"atacante", "centroavante", "ponta", "striker", "avante", "artilheiro", "extremo", "ala"}
        TOKENS_CRI = {"meia", "armador", "playmaker", "criativo", "meio-ofensivo", "meia-atacante"}
        ST_FORA  = {"lesionado", "suspenso", "expulso", "fora", "machucado", "contundido", "injured",
                    "poupado", "ausente", "cirurgia", "recuperação", "recuperacao"}
        ST_INC   = {"incerto", "dúvida", "duvida", "duvidoso", "questionável", "questionavel"}

        def inferir_qualidade(s) -> int:
            """Mapeia texto do sub para índice 0-3 (legado — usado só para criativo)."""
            s = s.lower()
            if any(t in s for t in ["qualidade: titular", "nível mantido", "nivel mantido",
                                    "mesmo nível", "mesmo nivel", "sub de nível", "sub de nivel"]):
                return 3
            if any(t in s for t in ["qualidade: reserva", "competente", "similar", "sub competente"]):
                return 2
            if any(t in s for t in ["jovem", "diferente", "queda", "queda de nível",
                                    "queda de nivel", "sem sub direto"]):
                return 1
            return 1

        def nivel_para_min_sub(s) -> Optional[float]:
            """
            Converte label qualitativo do novo prompt em float para min_melhor_sub.
            SUB DE NÍVEL   → 0.75  (>=70% no motor → -3 pts)
            SUB COMPETENTE → 0.55  (50-69% no motor → -10 pts)
            SEM SUB DIRETO → 0.20  (<50% no motor  → -18 pts)
            Retorna None se label não reconhecido (fallback: extrair_minutagem).
            """
            sl = s.lower()
            if "sub de nível" in sl or "sub de nivel" in sl:
                return 0.75
            if "sub competente" in sl:
                return 0.55
            if "sem sub direto" in sl:
                return 0.20
            return None

        def extrair_minutagem(s: str) -> Optional[float]:
            """Extrai % de minutagem de texto como '87%' ou '87% minutagem' → 0.87."""
            import re as _re3
            m = _re3.search(r'(\d{1,3})\s*%', s)
            if m:
                v = int(m.group(1))
                if 0 <= v <= 100:
                    return v / 100
            # Formato numérico direto: "minutagem: 87" ou "87 min"
            m2 = _re3.search(r'minutagem[:\s]+(\d{1,3})', s, _re3.I)
            if m2:
                v2 = int(m2.group(1))
                if 0 <= v2 <= 100:
                    return v2 / 100
            return None

        for linha in bloco.splitlines():
            linha = linha.strip()
            ll = linha.lower()
            # Nível ofensivo — suporta nome real do time
            if "nível ofensivo" in ll or "nivel ofensivo" in ll:
                if "drástica" in ll or "drastica" in ll:
                    info.tem_atacante_out = True
                continue
            if "|" not in linha:
                continue
            if ll.startswith(("time ", "nível", "nivel", "para ", "meias criativos", "sem ausên")):
                continue
            partes = [p.strip() for p in linha.lstrip("-* ").split("|")]
            if len(partes) < 2:
                continue
            # Nome: remover "(coxa)" e similares
            nome    = re.split(r'\s*\(', partes[0].strip())[0].strip()
            posicao = partes[1].strip().lower() if len(partes) > 1 else ""
            status  = partes[2].strip().lower() if len(partes) > 2 else ""
            # Template novo (6 partes): Nome | posição | status | gols | Sub: ... | Nível: ...
            # Template antigo (5 partes): Nome | posição | status | gols | Sub: ...
            # Template antigo sem gols (4 partes): Nome | posição | status | Sub: ...
            _p3 = partes[3].strip() if len(partes) > 3 else ""
            _p4 = partes[4].strip() if len(partes) > 4 else ""
            _p5 = partes[5].strip() if len(partes) > 5 else ""
            if _p3.lower().startswith("sub:") or "sub:" in _p3.lower():
                # Antigo sem gols: Nome | posição | status | Sub: ...
                sub_raw  = _p3
                gols_raw = ""
                min_aus_raw = ""
            elif _p4.lower().startswith("sub:") or "sub:" in _p4.lower():
                # Novo e antigo com gols: Nome | posição | status | gols | Sub: ... [| Nível: ...]
                gols_raw    = _p3
                sub_raw     = _p4 + (" | " + _p5 if _p5 else "")  # inclui Nível: para nivel_para_min_sub
                min_aus_raw = ""
            else:
                # Novo com minutagem: Nome | posição | status | gols | minutagem% | Sub: ...
                gols_raw    = _p3
                min_aus_raw = _p4   # "87% minutagem"
                sub_raw     = _p5   # "Sub: Hugo Ekitike (minutagem sub: 34%)"
            # Extrair gols e assistências para o relatório
            import re as _re2
            _mg = _re2.search(r'(\d+)\s*gol', gols_raw, _re2.I)
            _ma = _re2.search(r'(\d+)\s*assist', gols_raw, _re2.I)
            if _mg: info.gols_ausente = info.gols_ausente + int(_mg.group(1))
            if _ma: info.assists_ausente = info.assists_ausente + int(_ma.group(1))
            if not nome or len(nome) < 3 or nome[0].islower():
                continue
            is_fora  = any(s in status for s in ST_FORA)
            is_inc   = any(s in status for s in ST_INC)
            is_atk   = any(t in posicao for t in TOKENS_ATK)
            is_cri   = any(t in posicao for t in TOKENS_CRI)
            if is_fora:
                if nome not in info.lesionados: info.lesionados.append(nome)
                if is_atk: info.tem_atacante_out = True
                if is_cri: info.tem_criativo_out = True
            elif is_inc:
                if nome not in info.incertos: info.incertos.append(nome)
                if is_atk: info.tem_atacante_out = True
                if is_cri: info.tem_criativo_out = True
            if sub_raw and "nenhum" not in sub_raw.lower():
                ms = re.search(r'Sub:\s*([^(|\n]+)', sub_raw, re.IGNORECASE)
                if ms:
                    ns = ms.group(1).strip().rstrip(".")
                    qual = inferir_qualidade(sub_raw)
                    # Prioridade: label qualitativo novo ("SUB DE NÍVEL" etc.) > minutagem em %
                    min_sub_val = nivel_para_min_sub(sub_raw) or extrair_minutagem(sub_raw)
                    if ns and len(ns) > 2 and ns not in info.substitutos:
                        info.substitutos.append(ns)
                        if is_atk:
                            info.tem_substituto_atacante = True
                            info.qualidade_sub_atk = max(info.qualidade_sub_atk, qual)
                            # D7 — min_melhor_sub via label qualitativo ou % explícita
                            if min_sub_val is not None:
                                if info.min_melhor_sub is None or min_sub_val > info.min_melhor_sub:
                                    info.min_melhor_sub = min_sub_val

            # D7 — minutagem do ausente vem de min_aus_raw
            _min_ausente_val = extrair_minutagem(min_aus_raw) if min_aus_raw else None
            if _min_ausente_val is not None and is_atk and (is_fora or is_inc):
                if info.min_ausente_atk is None or _min_ausente_val > info.min_ausente_atk:
                    info.min_ausente_atk = _min_ausente_val

        # D7-B — linha comprometida: dois+ ausentes atacantes
        _atk_count = sum(
            1 for l in bloco.splitlines()
            if "|" in l and any(t in l.lower() for t in TOKENS_ATK)
            and any(s in l.lower() for s in ST_FORA | ST_INC)
        )
        if _atk_count >= 2:
            info.linha_comprometida = True

        return info

    def detectar_jogadores(bloco):
        # Ativar parser pipe se há linhas com "|" (com ou sem "-")
        _excl = ("time ", "nível", "nivel", "para ", "meias criativos", "sem ausên")
        linhas_pipe = [l for l in bloco.splitlines()
                       if "|" in l and len(l.strip()) > 8
                       and not l.strip().lower().startswith(_excl)]
        if linhas_pipe:
            return detectar_jogadores_formato_pipe(bloco)

        # Fallback: parser de linguagem natural
        info = InfoDesfalqueIA(raw_texto=bloco)
        bl = bloco.lower()
        norm_les = set()
        norm_inc = set()
        norm_sub = set()

        def add_les(nome, ctx_start, ctx_end):
            n = normalizar(nome)
            if n in norm_les:
                return
            norm_les.add(n)
            info.lesionados.append(nome)
            ctx = bl[max(0, ctx_start - 80):ctx_end + 80]
            if any(p in ctx for p in PALAVRAS_OFENSIVO):
                info.tem_atacante_out = True
            if any(p in ctx for p in PALAVRAS_CRIATIVO):
                info.tem_criativo_out = True

        # Padrão 1: "Nome (lesão/joelho/...)"
        for m in re.finditer(NOME_RE + r"\s*\(([^)]{2,50})\)", bloco):
            nome, sp = m.group(1).strip(), m.group(2).lower()
            if any(s in sp for s in STATUS_FORA):
                add_les(nome, m.start(), m.end())
            elif any(s in sp for s in STATUS_INCERTO):
                n = normalizar(nome)
                if n not in norm_inc and n not in norm_les:
                    norm_inc.add(n)
                    info.incertos.append(nome)

        # Padrão 2: "Nome está/estão fora/lesionado/não jogará"
        p2 = (NOME_RE +
              r"\s+(?:está|estão|ficará|não\s+(?:joga|jogará|estará|está)|"
              r"tambem não está|também não está|também não jogará|tambem não jogará)"
              r"\s+([^.]{2,80})")
        for m in re.finditer(p2, bloco):
            nome, cs = m.group(1).strip(), m.group(2).lower()
            trecho_m = bloco[m.start():m.end()].lower()
            neg_disp = ("não está" in trecho_m or "também não" in trecho_m) and any(p in cs for p in PALAVRAS_DISP)
            if (any(s in cs for s in STATUS_FORA)
                    or any(s in cs.split() for s in {"fora", "ausente", "lesionado"})
                    or neg_disp):
                add_les(nome, m.start(), m.end())
            elif any(s in cs for s in STATUS_INCERTO):
                n = normalizar(nome)
                if n not in norm_inc and n not in norm_les:
                    norm_inc.add(n)
                    info.incertos.append(nome)

        # Padrão 3: substitutos (verbos de ação positiva)
        psub = sorted(PALAVRAS_SUB, key=len, reverse=True)
        p3 = (NOME_RE + r"(?:\s+\w+){0,3}\s+(?:" +
              "|".join(re.escape(p) for p in psub) + r")")
        for m in re.finditer(p3, bloco, re.IGNORECASE):
            nome = m.group(1).strip()
            antes = bloco[max(0, m.start() - 30):m.start()].lower()
            if "não" in antes.split():
                continue
            n = normalizar(nome)
            if n not in norm_les and n not in norm_sub:
                norm_sub.add(n)
                info.substitutos.append(nome)
                ctx = bl[max(0, m.start() - 40):m.end() + 80]
                if any(p in ctx for p in PALAVRAS_OFENSIVO | {"ataque", "ofensivo"}):
                    info.tem_substituto_atacante = True

        # Padrão 4: "Nome está disponível" (sem negação)
        p4 = (NOME_RE + r"[^.]{0,60}(?:" +
              "|".join(re.escape(p) for p in PALAVRAS_DISP) + r")")
        for m in re.finditer(p4, bloco, re.IGNORECASE):
            nome = m.group(1).strip()
            trecho = bloco[m.start():m.end()].lower()
            if "não" in trecho or "também não" in trecho or "tambem não" in trecho:
                continue
            n = normalizar(nome)
            if n not in norm_les and n not in norm_sub:
                norm_sub.add(n)
                info.substitutos.append(nome)
                ctx = bl[max(0, m.start() - 40):m.end() + 80]
                if any(p in ctx for p in PALAVRAS_OFENSIVO | {"ataque", "ofensivo"}):
                    info.tem_substituto_atacante = True

        return info

    # ── Separação de blocos ───────────────────────────────────────
    # Prioridade 1: formato estruturado com "TIME CASA:" / "TIME FORA:"
    import re as _re_sep

    def _encontrar_bloco_time(nome_time, txt):
        """Encontra início do bloco de um time no texto — suporta TIME CASA: e NOME DO TIME:"""
        # Padrão 1: "TIME CASA:" ou "TIME FORA:"
        m = _re_sep.search(r'(?i)time\s+casa\s*:', txt)
        if nome_time == time_casa and m:
            return m.start()
        m = _re_sep.search(r'(?i)time\s+fora\s*:', txt)
        if nome_time == time_fora and m:
            return m.start()
        # Padrão 2: "NOME DO TIME:" (Google IA usa nome real)
        tokens = [t for t in nome_time.upper().split() if len(t) > 2]
        for token in tokens:
            m2 = _re_sep.search(
                rf'(?m)^.*{_re_sep.escape(token)}.*:\s*$', txt, _re_sep.IGNORECASE
            )
            if m2:
                return m2.start()
        return -1

    idx_casa = _encontrar_bloco_time(time_casa, texto)
    idx_fora = _encontrar_bloco_time(time_fora, texto)

    if idx_casa >= 0 and idx_fora >= 0 and idx_casa != idx_fora:
        if idx_casa < idx_fora:
            bloco_casa = texto[idx_casa:idx_fora]
            bloco_fora = texto[idx_fora:]
        else:
            bloco_fora = texto[idx_fora:idx_casa]
            bloco_casa = texto[idx_casa:]
    else:
        # Fallback: heurística por nome do time
        bloco_casa = extrair_bloco(time_casa, texto, outro_time=time_fora)
        bloco_fora = extrair_bloco(time_fora, texto)
        if bloco_casa == bloco_fora:
            meio = len(texto) // 2
            bloco_casa = texto[:meio]
            bloco_fora = texto[meio:]

    return detectar_jogadores(bloco_casa), detectar_jogadores(bloco_fora)



# ─────────────────────────────────────────────────────────────────────────────
#  TEMPLATE DO PROMPT PARA O GOOGLE MODO IA
#
#  Instruções deliberadamente restritas ao que afeta o Over 1.5:
#  ✅ Atacantes e centroavantes titulares ausentes
#  ✅ Meias criativos / armadores ausentes
#  ✅ Quem os substitui e se o substituto mantém qualidade ofensiva
#  ❌ Goleiros (não afetam gols marcados)
#  ❌ Zagueiros e laterais (impacto indireto, ignorado)
#  ❌ Jogadores do banco / sub-23 / reservas secundários
# ─────────────────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """Você é um analista de futebol. Preciso de dados de desfalques ofensivos para {time_casa} x {time_fora} ({liga}{data_str}).

REGRAS CRÍTICAS — leia antes de responder:
1. ELENCO ATUAL OBRIGATÓRIO: confirme que o jogador pertence ao elenco do clube NA DATA DO JOGO. Verifique transferências recentes em Transfermarkt ou fonte oficial. Jogadores transferidos NÃO são válidos.
2. SOMENTE jogadores com ações ofensivas diretas: atacantes, centroavantes, pontas, meias criativos/armadores, meias-atacantes. Ignore goleiros, zagueiros, laterais, volantes defensivos.
3. ESTATÍSTICAS DA TEMPORADA ATUAL apenas. Não use dados de temporadas anteriores.
4. Se não houver desfalques ofensivos confirmados, escreva exatamente: (sem desfalques ofensivos)
5. NÃO invente dados. Se a informação não estiver disponível em fonte confiável, omita.
6. SUBSTITUTO: liste o melhor substituto disponível e classifique-o com exatamente uma das três opções:
   - SUB DE NÍVEL → cobre a posição sem queda técnica relevante
   - SUB COMPETENTE → cobre a posição com queda técnica moderada
   - SEM SUB DIRETO → nenhum jogador de perfil similar disponível
   Se não conseguir confirmar com certeza: Sub: indefinido | Nível: SEM SUB DIRETO

Preencha EXATAMENTE o template abaixo. Mantenha o formato — traço, pipe e rótulos.

{time_casa}:
- [Nome] | [posição] | [Lesionado / Suspenso / Poupado] | [X gols, Y assist] | Sub: [Nome ou indefinido] | Nível: [SUB DE NÍVEL / SUB COMPETENTE / SEM SUB DIRETO]

{time_fora}:
- [Nome] | [posição] | [Lesionado / Suspenso / Poupado] | [X gols, Y assist] | Sub: [Nome ou indefinido] | Nível: [SUB DE NÍVEL / SUB COMPETENTE / SEM SUB DIRETO]

Nível ofensivo {time_casa}: [mantido / queda leve / queda drástica]
Nível ofensivo {time_fora}: [mantido / queda leve / queda drástica]"""


def gerar_prompt_google(time_casa: str, time_fora: str, liga: str, data: str = "") -> str:
    """
    Gera prompt estruturado para o Google Modo IA.
    Instrui o modelo a responder APENAS sobre jogadores ofensivos/criativos,
    ignorando goleiros, zagueiros e reservas que não impactam o Over 1.5.
    """
    data_str = f", {data}" if data else ""
    return PROMPT_TEMPLATE.format(
        time_casa=time_casa,
        time_fora=time_fora,
        liga=liga,
        data_str=data_str,
    ).strip()


def gerar_url_google(time_casa: str, time_fora: str, liga: str, data: str = "") -> str:
    """Gera URL de busca Google com o prompt já codificado."""
    from urllib.parse import quote_plus
    prompt = gerar_prompt_google(time_casa, time_fora, liga, data)
    return f"https://www.google.com/search?q={quote_plus(prompt)}"


def parsear_forma_recente(texto: str) -> tuple:
    """
    Parser Forma Recente Betano — Opção C (V7.2.1).

    CAMPO ÚNICO com os dois times juntos, exatamente como copiado da Betano.
    Cole os dois blocos em sequência: Marcados/Total/6 + Concedidos/Total/6.

    Retorna: (FormaRecente_casa, FormaRecente_fora)

    Formato real do Betano (dois times lado a lado, intercalados):
        Rótulo
        valor_mandante
        X / N              ← fração mandante
        valor_visitante
        X / N              ← fração visitante

    Testado com dados reais: Gil Vicente × Benfica — 12/12 campos corretos.
    """
    if not texto.strip():
        return FormaRecente(), FormaRecente()

    casa = FormaRecente()
    fora = FormaRecente()

    t = re.sub(r'[\u200f\u200e\u200b\u00a0]', ' ', texto)
    linhas = [l.strip() for l in t.splitlines() if l.strip()]

    # Detectar amostra pelo denominador mais frequente nas frações X/N
    denominadores = re.findall(r'\d+\s*/\s*(\d+)', t)
    if denominadores:
        from collections import Counter
        mais_comum = Counter(int(d) for d in denominadores).most_common(1)[0][0]
        casa.total_jogos_amostra = mais_comum
        fora.total_jogos_amostra = mais_comum

    # Mapa de rótulos → (campo_casa, campo_fora, tipo)
    # tipo 'fracao' = usar numerador de X/N; 'media' = usar valor decimal
    ROTULOS = [
        ('matches scored at ft',              'jogos_com_gol',          'fracao'),
        ('partidas com golos no final',        'jogos_com_gol',          'fracao'),
        ('matches scored at ht',               'jogos_com_gol_1t',       'fracao'),
        ('partidas com golos ao intervalo',    'jogos_com_gol_1t',       'fracao'),
        ('média gols marcados',                'media_gols_marcados',    'media'),
        ('media gols marcados',                'media_gols_marcados',    'media'),
        ('sem marcar',                         'jogos_sem_marcar',       'fracao'),
        ('média gols concedidos',              'media_gols_concedidos',  'media'),
        ('media gols concedidos',              'media_gols_concedidos',  'media'),
        ('média total gols concedidos 1',      'media_gols_concedidos_1t','media'),
        ('media total gols concedidos 1',      'media_gols_concedidos_1t','media'),
        ('golos concedidos 1ª parte',          'media_gols_concedidos_1t','media'),
    ]

    def eh_numero(s: str) -> bool:
        return bool(re.match(r'^-?\d+(?:[.,]\d+)?%?$', s))

    def eh_fracao(s: str) -> bool:
        return bool(re.match(r'^\d+\s*/\s*\d+$', s))

    def parse_num(s: str) -> Optional[float]:
        try:
            return float(re.sub(r'%', '', s).replace(',', '.').strip())
        except:
            return None

    def coletar_par(start: int) -> list:
        """
        A partir de start+1, coleta dois pares (valor, frac_num, frac_den).
        Cada time: número decimal + opcionalmente X/N na linha seguinte.
        Para frações diretas como "17% / 1 / 6": lê o número e a fração.
        """
        vals = []
        j = start + 1
        while j < len(linhas) and len(vals) < 2:
            linha = linhas[j]
            ll = linha.lower()
            # Parar se chegou em novo rótulo
            if any(r in ll for r, _, _ in ROTULOS):
                break
            if eh_fracao(linha):
                j += 1
                continue  # fração isolada sem número antes — pular
            if eh_numero(linha):
                num = parse_num(linha)
                frac_num, frac_den = None, None
                # próxima linha é fração?
                if j + 1 < len(linhas) and eh_fracao(linhas[j+1]):
                    m = re.match(r'(\d+)\s*/\s*(\d+)', linhas[j+1])
                    if m:
                        frac_num, frac_den = int(m.group(1)), int(m.group(2))
                    j += 2
                else:
                    j += 1
                vals.append((num, frac_num, frac_den))
                continue
            j += 1
        return vals

    for i, linha in enumerate(linhas):
        ll = linha.lower()
        for rotulo, campo, tipo in ROTULOS:
            if rotulo in ll and getattr(casa, campo) is None:
                par = coletar_par(i)
                if len(par) >= 1:
                    v_c, fn_c, _ = par[0]
                    # tipo 'fracao': precisa de fração explícita (X/N). Percentual isolado
                    # (ex: 67%) NÃO é substituto — causaria "67/6 jogos" no relatório.
                    if tipo == 'fracao':
                        val_c = fn_c  # None se não veio fração → campo fica sem dado
                    else:
                        val_c = v_c
                    setattr(casa, campo, val_c)
                if len(par) >= 2:
                    v_f, fn_f, _ = par[1]
                    if tipo == 'fracao':
                        val_f = fn_f  # mesmo critério
                    else:
                        val_f = v_f
                    setattr(fora, campo, val_f)
                break

    return casa, fora


def parsear_h2h(texto: str) -> DadosH2H:
    """
    Parser H2H.

    Extrai placares de qualquer formato que contenha "X - Y" ou "X–Y".
    Calcula automaticamente:
        - Média de gols por jogo
        - % Over 1.5 (>= 2 gols totais)
        - % Over 2.5 (>= 3 gols totais)
        - % BTTS (ambos marcaram)
        - Últimos 5 resultados

    Aceita colagens diretas da Superbet, Betano ou qualquer fonte.
    Placares com ambos os lados zerados (0-0) são contabilizados.
    """
    d = DadosH2H()
    if not texto.strip():
        return d

    t = texto

    # Extrair todos os placares no formato "N - N" ou "N–N" ou "N:N"
    resultados_raw = re.findall(r'\b(\d{1,2})\s*[-\u2013:]\s*(\d{1,2})\b', t)

    # V7.2 Bloco 2 — Filtro pênaltis: detectar, não excluir.
    # Placar de pênaltis tem placar real por trás — excluir perde o jogo do H2H.
    # Heurística: soma >= 8 com ambos >= 3 = suspeito. Sinaliza para revisão manual.
    # Caso confirmado: Toulouse×Marseille 5-6 (jogo real 2-2).
    resultados = []
    penaltis_suspeitos = []
    for a_str, b_str in resultados_raw:
        a, b = int(a_str), int(b_str)
        if a > 12 or b > 12 or (a + b) > 15:
            continue  # placar inválido
        if (a + b) >= 8 and a >= 3 and b >= 3:
            penaltis_suspeitos.append(f"{a}-{b}")  # sinalizar — não excluir
        resultados.append((a, b))

    if penaltis_suspeitos:
        d.penaltis_suspeitos = penaltis_suspeitos

    if resultados:
        gols_totais = [a + b for a, b in resultados]
        n = len(gols_totais)

        d.total_jogos = n
        d.media_gols = round(sum(gols_totais) / n, 2)
        d.over15_pct = round(sum(1 for g in gols_totais if g >= 2) / n, 3)
        d.over25_pct = round(sum(1 for g in gols_totais if g >= 3) / n, 3)
        d.btts_pct   = round(sum(1 for a, b in resultados if a > 0 and b > 0) / n, 3)
        d.resultados_recentes = [f"{a}-{b}" for a, b in resultados[:5]]

        # Contagem vitórias
        d.vitorias_casa = sum(1 for a, b in resultados if a > b)
        d.empates       = sum(1 for a, b in resultados if a == b)
        d.vitorias_fora = sum(1 for a, b in resultados if b > a)

    return d


# ══════════════════════════════════════════════════════════════════
#  GERADOR DE BILHETES
# ══════════════════════════════════════════════════════════════════


