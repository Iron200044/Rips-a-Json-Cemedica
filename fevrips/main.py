# ============================================================
#  FEVRIPS IPS TRANSMITTER — Programa principal
#  Uso:
#    python main.py                         → envía facturas pendientes de hoy
#    python main.py --desde 2026-04-01      → desde una fecha
#    python main.py --hasta 2026-04-15      → hasta una fecha
#    python main.py --factura FA-001234     → solo una factura específica
#    python main.py --solo-generar          → genera JSON sin enviar
#    python main.py --devueltas             → muestra facturas rechazadas
#    python main.py --resumen               → muestra totales de envíos
#    python main.py --test-conexion         → prueba BD y MUV sin enviar nada
# ============================================================

import argparse
import sys
import time
import json
from datetime import datetime
from pathlib import Path

from config import ENVIO, RUTAS
from fevrips.logger import log
from fevrips.db_queries import conectar, obtener_facturas_pendientes, \
    obtener_consultas_factura, obtener_procedimientos_factura, \
    obtener_medicamentos_factura
from fevrips.construir_json import construir_json_rips
from fevrips.muv_client import login, enviar_fev_rips, cargar_xml_factura
from fevrips.estado_db import inicializar, registrar_envio, registrar_error, \
    ya_fue_enviada, obtener_devueltas, resumen


# ─── Comandos ────────────────────────────────────────────────

def cmd_test_conexion():
    """Verifica que la BD y el MUV estén accesibles."""
    print("\n── Test de conexión ──────────────────────")
    try:
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM GCEFACTURA")
        n = cursor.fetchone()[0]
        conn.close()
        print(f"  ✓ SQL Server OK — {n} facturas en GCEFACTURA")
    except Exception as e:
        print(f"  ✗ SQL Server ERROR: {e}")

    try:
        login()
        print("  ✓ MUV local OK — Login exitoso")
    except Exception as e:
        print(f"  ✗ MUV ERROR: {e}")
    print()


def cmd_devueltas():
    """Muestra las facturas rechazadas por el MUV."""
    filas = obtener_devueltas()
    if not filas:
        print("\nNo hay facturas rechazadas.\n")
        return

    print(f"\n── Facturas rechazadas ({len(filas)}) ────────────────")
    for f in filas:
        print(f"\n  {f['num_factura']}  |  {f['eps_nombre']}  |  ${f['valor_total']:,.0f}")
        print(f"  Paciente: {f['pac_num_id']}  |  Enviado: {f['fecha_envio']}")
        for g in f["glosas"]:
            print(f"  ✗ [{g.get('Codigo', '?')}] {g.get('Descripcion', g.get('error', ''))}")
    print()


def cmd_enviar(fecha_desde=None, fecha_hasta=None, num_factura=None):
    """Flujo principal de extracción → construcción → envío."""

    log.info("=" * 60)
    log.info("Iniciando proceso FEV-RIPS")
    log.info("=" * 60)

    # 1. Inicializar BD local y autenticación
    inicializar()

    if not ENVIO["modo_solo_generar"]:
        try:
            login()
        except Exception as e:
            log.error(f"No se pudo autenticar en el MUV. Abortando. ({e})")
            sys.exit(1)

    # 2. Conectar a SQL Server y obtener facturas
    try:
        conn = conectar()
    except Exception as e:
        log.error(f"No se pudo conectar a SQL Server. Abortando. ({e})")
        sys.exit(1)

    facturas = obtener_facturas_pendientes(
        conn,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        num_factura=num_factura,
    )

    if not facturas:
        log.info("No se encontraron facturas para los filtros indicados.")
        conn.close()
        return

    log.info(f"Facturas encontradas: {len(facturas)}")

    # 3. Procesar por lotes
    aprobadas = rechazadas = errores = omitidas = 0
    Path(RUTAS["json_salida"]).mkdir(parents=True, exist_ok=True)

    for i, fac in enumerate(facturas):
        num = fac["FacNumero"]

        # Saltar si ya fue aprobada anteriormente
        if ya_fue_enviada(num):
            log.info(f"[{i+1}/{len(facturas)}] {num} — Ya aprobada. Omitiendo.")
            omitidas += 1
            continue

        log.info(f"[{i+1}/{len(facturas)}] Procesando {num}...")

        try:
            # 3a. Extraer servicios de la BD
            pac_id = str(fac["PacNumId"]).strip()
            consultas      = obtener_consultas_factura(conn, num, pac_id)
            procedimientos = obtener_procedimientos_factura(conn, num, pac_id)
            medicamentos   = obtener_medicamentos_factura(conn, num, pac_id)

            # 3b. Cargar XML de la DIAN
            xml_b64 = cargar_xml_factura(num)

            # 3c. Construir JSON RIPS
            payload = construir_json_rips(fac, consultas, procedimientos, medicamentos)
            payload["xmlFevFile"] = xml_b64

            # 3d. Guardar JSON generado en disco (para auditoría)
            ruta_json = Path(RUTAS["json_salida"]) / f"{num}.json"
            with open(ruta_json, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            if ENVIO["modo_solo_generar"]:
                log.info(f"  JSON guardado en {ruta_json} (modo solo-generar)")
                continue

            # 3e. Enviar al MUV
            respuesta = enviar_fev_rips(payload)
            registrar_envio(fac, payload, respuesta)

            if respuesta.get("ResultState"):
                aprobadas += 1
            else:
                rechazadas += 1

        except Exception as e:
            log.error(f"  Error procesando {num}: {e}")
            registrar_error(num, str(e))
            errores += 1

        # Pausa entre envíos
        if i < len(facturas) - 1:
            time.sleep(ENVIO["delay_entre_envios"])

    conn.close()

    # 4. Resumen final
    log.info("=" * 60)
    log.info(f"PROCESO FINALIZADO")
    log.info(f"  Aprobadas:  {aprobadas}")
    log.info(f"  Rechazadas: {rechazadas}")
    log.info(f"  Errores:    {errores}")
    log.info(f"  Omitidas:   {omitidas}")
    log.info("=" * 60)

    resumen()


# ─── Entry point ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FEV-RIPS IPS Transmitter — Envío automático al MUV SISPRO"
    )
    parser.add_argument("--desde",        help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--hasta",        help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--factura",      help="Número de factura específica")
    parser.add_argument("--solo-generar", action="store_true",
                        help="Genera JSONs sin enviar al MUV")
    parser.add_argument("--devueltas",    action="store_true",
                        help="Muestra facturas rechazadas")
    parser.add_argument("--resumen",      action="store_true",
                        help="Muestra resumen de envíos")
    parser.add_argument("--test-conexion", action="store_true",
                        help="Prueba conexión a BD y MUV")

    args = parser.parse_args()

    if args.test_conexion:
        cmd_test_conexion()
        return

    if args.devueltas:
        inicializar()
        cmd_devueltas()
        return

    if args.resumen:
        inicializar()
        resumen()
        return

    # Parsear fechas
    fecha_desde = datetime.strptime(args.desde, "%Y-%m-%d") if args.desde else None
    fecha_hasta = datetime.strptime(args.hasta, "%Y-%m-%d") if args.hasta else None

    # Si modo_solo_generar viene por argumento, sobreescribir config
    if args.solo_generar:
        ENVIO["modo_solo_generar"] = True

    cmd_enviar(
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        num_factura=args.factura,
    )


if __name__ == "__main__":
    main()
