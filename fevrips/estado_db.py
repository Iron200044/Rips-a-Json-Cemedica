# ============================================================
#  BASE DE DATOS LOCAL DE ESTADO — SQLite
#  Guarda qué facturas se enviaron, su CUV y las glosas
# ============================================================

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from config import RUTAS
from fevrips.logger import log


def _conectar():
    Path(RUTAS["db_local"]).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(RUTAS["db_local"])


def inicializar():
    """Crea las tablas si no existen. Llamar al inicio del programa."""
    with _conectar() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS envios (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            num_factura      TEXT    NOT NULL UNIQUE,
            fecha_factura    TEXT,
            pac_num_id       TEXT,
            eps_nombre       TEXT,
            valor_total      REAL,
            fecha_envio      TEXT,
            resultado        TEXT,    -- 'APROBADO' | 'RECHAZADO' | 'ERROR'
            cuv              TEXT,
            proceso_id       INTEGER,
            ambiente         TEXT,
            periodo_inicio   TEXT,
            periodo_fin      TEXT,
            json_enviado     TEXT,    -- JSON completo para auditoría
            json_respuesta   TEXT,    -- Respuesta completa del MUV
            glosas           TEXT     -- JSON array de glosas si fue rechazado
        );

        CREATE TABLE IF NOT EXISTS log_envios (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT    NOT NULL,
            num_factura  TEXT,
            nivel        TEXT,   -- INFO | WARNING | ERROR
            mensaje      TEXT
        );
        """)
        log.info("Base de datos local inicializada.")


def registrar_envio(fac, payload, respuesta_muv):
    """
    Guarda o actualiza el resultado de un envío en la BD local.
    Llama después de cada respuesta del MUV.
    """
    resultado = "APROBADO" if respuesta_muv.get("ResultState") else "RECHAZADO"
    cuv = respuesta_muv.get("CodigoUnicoValidacion")
    glosas = [
        v for v in respuesta_muv.get("ResultadosValidacion", [])
        if v.get("Clase") == "RECHAZADO"
    ]
    periodo = respuesta_muv.get("PeriodoAtencion") or {}

    with _conectar() as conn:
        conn.execute("""
        INSERT INTO envios (
            num_factura, fecha_factura, pac_num_id, eps_nombre, valor_total,
            fecha_envio, resultado, cuv, proceso_id, ambiente,
            periodo_inicio, periodo_fin, json_enviado, json_respuesta, glosas
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(num_factura) DO UPDATE SET
            fecha_envio    = excluded.fecha_envio,
            resultado      = excluded.resultado,
            cuv            = excluded.cuv,
            proceso_id     = excluded.proceso_id,
            ambiente       = excluded.ambiente,
            periodo_inicio = excluded.periodo_inicio,
            periodo_fin    = excluded.periodo_fin,
            json_enviado   = excluded.json_enviado,
            json_respuesta = excluded.json_respuesta,
            glosas         = excluded.glosas
        """, [
            fac["FacNumero"],
            str(fac.get("FacFecha", "")),
            str(fac.get("PacNumId", "")),
            str(fac.get("AseNombre", "")),
            float(fac.get("FacTotal") or 0),
            datetime.now().isoformat(),
            resultado,
            cuv,
            respuesta_muv.get("ProcesoId"),
            respuesta_muv.get("Ambiente"),
            str(periodo.get("FechaInicio", "") or ""),
            str(periodo.get("FechaFin", "") or ""),
            json.dumps(payload, ensure_ascii=False),
            json.dumps(respuesta_muv, ensure_ascii=False),
            json.dumps(glosas, ensure_ascii=False),
        ])


def registrar_error(num_factura, mensaje_error):
    """Registra un error técnico (no rechazo del MUV) en la BD."""
    with _conectar() as conn:
        conn.execute("""
        INSERT INTO envios (num_factura, fecha_envio, resultado, glosas)
        VALUES (?, ?, 'ERROR', ?)
        ON CONFLICT(num_factura) DO UPDATE SET
            fecha_envio = excluded.fecha_envio,
            resultado   = 'ERROR',
            glosas      = excluded.glosas
        """, [num_factura, datetime.now().isoformat(), json.dumps([{"error": mensaje_error}])])


def ya_fue_enviada(num_factura):
    """Retorna True si la factura ya tiene un envío exitoso (APROBADO)."""
    with _conectar() as conn:
        fila = conn.execute(
            "SELECT resultado FROM envios WHERE num_factura = ?",
            [num_factura]
        ).fetchone()
    return fila is not None and fila[0] == "APROBADO"


def obtener_devueltas():
    """Retorna lista de facturas rechazadas para revisión manual."""
    with _conectar() as conn:
        filas = conn.execute("""
        SELECT num_factura, fecha_factura, pac_num_id, eps_nombre,
               valor_total, fecha_envio, glosas
        FROM envios
        WHERE resultado = 'RECHAZADO'
        ORDER BY fecha_envio DESC
        """).fetchall()
    return [
        {
            "num_factura":   f[0],
            "fecha_factura": f[1],
            "pac_num_id":    f[2],
            "eps_nombre":    f[3],
            "valor_total":   f[4],
            "fecha_envio":   f[5],
            "glosas":        json.loads(f[6] or "[]"),
        }
        for f in filas
    ]


def resumen():
    """Imprime un resumen rápido del estado de envíos."""
    with _conectar() as conn:
        totales = conn.execute("""
        SELECT resultado, COUNT(*), SUM(valor_total)
        FROM envios GROUP BY resultado
        """).fetchall()

    print("\n─── RESUMEN DE ENVÍOS ─────────────────────")
    for fila in totales:
        print(f"  {fila[0]:12s}  {fila[1]:5d} facturas   ${fila[2]:,.0f}")
    print("───────────────────────────────────────────\n")
