"""
atlas/db.py
Camada de persistência SQLite — fiel ao schema original do monolítico.

Schema:
  sessoes       (id, data_analise, criado_em, n_jogos, ativa)
  widgets_salvos(id, sessao_id, idx_jogo, widgets_json, salvo_em)  — JSON blob por jogo
  globals_salvos(sessao_id PK, data_global, n_jogos, lista_importacao)
  lotes_salvos  (id, sessao_id, label, jogos_json, salvo_em)
"""

from __future__ import annotations
import sqlite3
import json
import os
import streamlit as st
from datetime import datetime

from atlas.config import WIDGET_KEYS

_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "atlas_autosave.db"
)


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # proteção contra corrupção em crash
    return conn


def _db_migrate(conn) -> None:
    """Migration automatica — garante compatibilidade com banco existente."""
    # Migration: analises_salvas (bancos antigos)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analises_salvas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id      INTEGER NOT NULL,
                idx_jogo       INTEGER NOT NULL,
                jogo_json      TEXT NOT NULL,
                resultado_json TEXT NOT NULL,
                salvo_em       TEXT NOT NULL,
                FOREIGN KEY (sessao_id) REFERENCES sessoes(id),
                UNIQUE(sessao_id, idx_jogo)
            )
        """)
    except Exception:
        pass
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(widgets_salvos)").fetchall()}
        if cols and "idx_jogo" not in cols:
            conn.execute("DROP TABLE IF EXISTS widgets_salvos")
            conn.execute("""
                CREATE TABLE widgets_salvos (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    sessao_id    INTEGER NOT NULL,
                    idx_jogo     INTEGER NOT NULL,
                    widgets_json TEXT NOT NULL,
                    salvo_em     TEXT NOT NULL,
                    FOREIGN KEY (sessao_id) REFERENCES sessoes(id),
                    UNIQUE(sessao_id, idx_jogo)
                )
            """)
    except Exception:
        pass
    try:
        cols_s = {r[1] for r in conn.execute("PRAGMA table_info(sessoes)").fetchall()}
        if "n_jogos" not in cols_s:
            conn.execute("ALTER TABLE sessoes ADD COLUMN n_jogos INTEGER DEFAULT 0")
    except Exception:
        pass


def db_init() -> None:
    with _db_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                data_analise TEXT NOT NULL,
                criado_em    TEXT NOT NULL,
                n_jogos      INTEGER DEFAULT 0,
                ativa        INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS widgets_salvos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id    INTEGER NOT NULL,
                idx_jogo     INTEGER NOT NULL,
                widgets_json TEXT NOT NULL,
                salvo_em     TEXT NOT NULL,
                FOREIGN KEY (sessao_id) REFERENCES sessoes(id),
                UNIQUE(sessao_id, idx_jogo)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lotes_salvos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id    INTEGER NOT NULL,
                label        TEXT,
                jogos_json   TEXT NOT NULL,
                salvo_em     TEXT NOT NULL,
                FOREIGN KEY (sessao_id) REFERENCES sessoes(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS globals_salvos (
                sessao_id        INTEGER PRIMARY KEY,
                data_global      TEXT DEFAULT '',
                n_jogos          INTEGER DEFAULT 1,
                lista_importacao TEXT DEFAULT '',
                FOREIGN KEY (sessao_id) REFERENCES sessoes(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analises_salvas (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id    INTEGER NOT NULL,
                idx_jogo     INTEGER NOT NULL,
                jogo_json    TEXT NOT NULL,
                resultado_json TEXT NOT NULL,
                salvo_em     TEXT NOT NULL,
                FOREIGN KEY (sessao_id) REFERENCES sessoes(id),
                UNIQUE(sessao_id, idx_jogo)
            )
        """)
        _db_migrate(conn)


def db_sessao_ativa() -> int | None:
    try:
        with _db_conn() as conn:
            row = conn.execute(
                "SELECT id FROM sessoes WHERE ativa=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["id"] if row else None
    except Exception:
        return None


def db_criar_sessao(data_analise: str) -> int:
    with _db_conn() as conn:
        conn.execute("UPDATE sessoes SET ativa=0")
        cur = conn.execute(
            "INSERT INTO sessoes (data_analise, criado_em, n_jogos, ativa) VALUES (?,?,0,1)",
            (data_analise, datetime.now().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def db_autosave_widgets(sessao_id: int, idx: int) -> None:
    try:
        snapshot: dict = {}
        for tpl, tipo, default in WIDGET_KEYS:
            key = tpl.replace("{i}", str(idx))
            val = st.session_state.get(key, default)
            if isinstance(val, bool):
                snapshot[key] = bool(val)
            elif isinstance(val, (int, float)):
                snapshot[key] = val
            else:
                snapshot[key] = str(val) if val is not None else ""
        agora = datetime.now().isoformat()
        with _db_conn() as conn:
            conn.execute("""
                INSERT INTO widgets_salvos (sessao_id, idx_jogo, widgets_json, salvo_em)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sessao_id, idx_jogo) DO UPDATE SET
                    widgets_json = excluded.widgets_json,
                    salvo_em     = excluded.salvo_em
            """, (sessao_id, idx, json.dumps(snapshot), agora))
            conn.execute(
                "UPDATE sessoes SET n_jogos=(SELECT COUNT(*) FROM widgets_salvos WHERE sessao_id=?) WHERE id=?",
                (sessao_id, sessao_id),
            )
    except Exception:
        pass


def db_autosave_globals(sessao_id: int, data_global: str, n_jogos: int, lista_txt: str = "") -> None:
    try:
        with _db_conn() as conn:
            conn.execute("""
                INSERT INTO globals_salvos (sessao_id, data_global, n_jogos, lista_importacao)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(sessao_id) DO UPDATE SET
                    data_global      = excluded.data_global,
                    n_jogos          = excluded.n_jogos,
                    lista_importacao = excluded.lista_importacao
            """, (sessao_id, data_global, n_jogos, lista_txt))
    except Exception:
        pass


def db_autosave_lotes(sessao_id: int, lotes: list) -> None:
    try:
        with _db_conn() as conn:
            conn.execute("DELETE FROM lotes_salvos WHERE sessao_id=?", (sessao_id,))
            for lote in lotes:
                conn.execute(
                    "INSERT INTO lotes_salvos (sessao_id, label, jogos_json, salvo_em) VALUES (?,?,?,?)",
                    (sessao_id, lote.get("label", ""), json.dumps(lote.get("jogos", [])), datetime.now().isoformat()),
                )
    except Exception:
        pass


def db_salvar_analises(sessao_id: int, jogos_com_resultado: list) -> None:
    """Persiste os resultados do motor para cada jogo da sessão.
    Permite recuperar/corrigir análises mesmo após limpar a lista.
    """
    import dataclasses
    try:
        agora = datetime.now().isoformat()
        with _db_conn() as conn:
            for idx, (j, r) in enumerate(jogos_com_resultado):
                if r is None:
                    continue
                jogo_dict = dataclasses.asdict(j) if dataclasses.is_dataclass(j) else dict(j)
                conn.execute("""
                    INSERT INTO analises_salvas
                        (sessao_id, idx_jogo, jogo_json, resultado_json, salvo_em)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(sessao_id, idx_jogo) DO UPDATE SET
                        jogo_json      = excluded.jogo_json,
                        resultado_json = excluded.resultado_json,
                        salvo_em       = excluded.salvo_em
                """, (sessao_id, idx, json.dumps(jogo_dict), json.dumps(r), agora))
    except Exception:
        pass


def db_carregar_analises(sessao_id: int) -> list:
    """Carrega os resultados do motor salvos para uma sessão.
    Retorna lista de (jogo_dict, resultado_dict) em ordem de idx_jogo.
    Usado na inicialização para popular _cache_analise sem precisar reanalisar.
    """
    out = []
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT jogo_json, resultado_json FROM analises_salvas "
                "WHERE sessao_id=? ORDER BY idx_jogo",
                (sessao_id,)
            ).fetchall()
            for row in rows:
                try:
                    jogo_dict = json.loads(row["jogo_json"])
                    resultado  = json.loads(row["resultado_json"])
                    out.append((jogo_dict, resultado))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def db_carregar_sessao(sessao_id: int) -> dict:
    out: dict = {"widgets": {}, "lotes": [], "globals": {}}
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT idx_jogo, widgets_json FROM widgets_salvos WHERE sessao_id=? ORDER BY idx_jogo",
                (sessao_id,),
            ).fetchall()
            for row in rows:
                try:
                    out["widgets"][int(row["idx_jogo"])] = json.loads(row["widgets_json"])
                except Exception:
                    pass
            lrows = conn.execute(
                "SELECT label, jogos_json FROM lotes_salvos WHERE sessao_id=? ORDER BY id",
                (sessao_id,),
            ).fetchall()
            for lr in lrows:
                try:
                    out["lotes"].append({"label": lr["label"], "jogos": json.loads(lr["jogos_json"])})
                except Exception:
                    pass
            grow = conn.execute(
                "SELECT * FROM globals_salvos WHERE sessao_id=?", (sessao_id,)
            ).fetchone()
            if grow:
                out["globals"] = dict(grow)
    except Exception:
        pass
    return out


def db_sessao_info(sessao_id: int) -> dict:
    try:
        with _db_conn() as conn:
            row = conn.execute("SELECT * FROM sessoes WHERE id=?", (sessao_id,)).fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}


def db_listar_sessoes(limite: int = 10) -> list[dict]:
    try:
        with _db_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessoes ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def db_restaurar_session_state(dados: dict) -> None:
    globs = dados.get("globals", {})
    if globs.get("data_global"):
        st.session_state.setdefault("data_global", globs["data_global"])
    if globs.get("n_jogos"):
        st.session_state["d15_n_jogos_restaurado"] = int(globs["n_jogos"])
    if globs.get("lista_importacao"):
        st.session_state.setdefault("lista_importacao", globs["lista_importacao"])
    for idx, snapshot in dados.get("widgets", {}).items():
        for key, val in snapshot.items():
            if key not in st.session_state:
                st.session_state[key] = val
    lotes = dados.get("lotes", [])
    if lotes:
        st.session_state.setdefault("lotes_salvos", lotes)


db_init()
