# ============================================================
#  CLIENTE API MUV — Comunicación con el validador local
#  Implementa LoginSISPRO + CargarFevRips según manual v4.3
# ============================================================

import gzip
import json
import base64
import os
import requests
import urllib3
from pathlib import Path
from config import MUV, SISPRO, RUTAS
from fevrips.logger import log

# Silenciar advertencia de certificado SSL autofirmado del MUV local
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Token en memoria durante la sesión (se renueva llamando a login())
_token_sesion = None


# ─── Autenticación ───────────────────────────────────────────

def login():
    """
    Obtiene el token Bearer del MUV local.
    Debe llamarse antes de cualquier envío.
    Renueva _token_sesion globalmente.
    """
    global _token_sesion

    url = f"{MUV['base_url']}/api/Auth/LoginSISPRO"
    body = {
        "persona": {
            "identificacion": {
                "tipo":   SISPRO["tipo_documento"],
                "numero": SISPRO["numero_documento"],
            }
        },
        "clave":       SISPRO["clave"],
        "nit":         SISPRO["nit"],
        "tipoUsuario": SISPRO["tipo_usuario"],
    }

    log.info("Autenticando en MUV local...")
    try:
        resp = requests.post(
            url,
            json=body,
            headers={"Content-Type": "application/json"},
            verify=MUV["verify_ssl"],
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # El token viene en distintos campos según versión del MUV
        token = data.get("token") or data.get("Token") or data.get("access_token")
        if not token:
            raise ValueError(f"Login exitoso pero no se encontró token en respuesta: {data}")

        _token_sesion = token
        log.info("Login exitoso. Token obtenido.")
        return token

    except requests.exceptions.ConnectionError:
        log.error(
            "No se pudo conectar al MUV en "
            f"{MUV['base_url']}. "
            "Verifique que el servicio FEV-RIPS esté corriendo."
        )
        raise
    except Exception as e:
        log.error(f"Error en login MUV: {e}")
        raise


# ─── Carga del XML de la factura DIAN ────────────────────────

def cargar_xml_factura(num_factura):
    """
    Busca el archivo XML AttachedDocument de la DIAN para la factura
    y lo retorna en Base64 como string.

    Los XML deben estar en la ruta configurada en RUTAS['xml_facturas'].
    El nombre del archivo debe coincidir con el número de factura.

    Convenciones de nombre que se intentan:
        FA-001234.xml
        FA001234.xml
        001234.xml

    TODO: ajustar si el software de facturación usa otra convención de nombres.
    """
    carpeta = Path(RUTAS["xml_facturas"])
    if not carpeta.exists():
        log.warning(f"Carpeta de XML no existe: {carpeta}")
        return ""

    # Intentar variantes del nombre
    variantes = [
        f"{num_factura}.xml",
        f"{num_factura.replace('-', '')}.xml",
        f"{num_factura.replace('-', '_')}.xml",
    ]

    for nombre in variantes:
        ruta = carpeta / nombre
        if ruta.exists():
            with open(ruta, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    log.warning(
        f"XML no encontrado para factura {num_factura} "
        f"en {carpeta}. Se enviará xmlFevFile vacío — "
        "esto puede causar rechazo en el MUV si es requerido."
    )
    return ""


# ─── Compresión GZIP ─────────────────────────────────────────

def _comprimir_gzip(payload_dict):
    """Serializa el dict a JSON y lo comprime con GZIP. Retorna bytes."""
    json_bytes = json.dumps(payload_dict, ensure_ascii=False).encode("utf-8")
    return gzip.compress(json_bytes)


# ─── Envío principal ─────────────────────────────────────────

def enviar_fev_rips(payload):
    """
    Envía un paquete FEV-RIPS al MUV local.

    payload: dict con claves 'rips' (dict) y 'xmlFevFile' (str Base64)

    Retorna el dict de respuesta del MUV con:
        ResultState, CodigoUnicoValidacion, ResultadosValidacion, etc.
    """
    global _token_sesion

    if not _token_sesion:
        login()

    url = f"{MUV['base_url']}/api/PaquetesFevRips/CargarFevRips"
    cuerpo_gzip = _comprimir_gzip(payload)

    headers = {
        "Content-Type":     "application/json",
        "Content-Encoding": "gzip",
        "Authorization":    f"Bearer {_token_sesion}",
    }

    num_factura = payload.get("rips", {}).get("numFactura", "?")
    log.info(f"Enviando factura {num_factura} al MUV...")

    try:
        resp = requests.post(
            url,
            data=cuerpo_gzip,
            headers=headers,
            verify=MUV["verify_ssl"],
            timeout=120,
        )

        # Si el token expiró (401), renovar y reintentar una vez
        if resp.status_code == 401:
            log.warning("Token expirado. Renovando sesión...")
            login()
            headers["Authorization"] = f"Bearer {_token_sesion}"
            resp = requests.post(
                url,
                data=cuerpo_gzip,
                headers=headers,
                verify=MUV["verify_ssl"],
                timeout=120,
            )

        resp.raise_for_status()
        resultado = resp.json()
        _loguear_resultado(num_factura, resultado)
        return resultado

    except requests.exceptions.ConnectionError:
        log.error(f"Sin conexión al MUV para factura {num_factura}.")
        raise
    except Exception as e:
        log.error(f"Error enviando factura {num_factura}: {e}")
        raise


def consultar_cuv(cuv):
    """
    Consulta el estado de un CUV ya emitido.
    No requiere autenticación (acceso público según manual).
    """
    url = f"{MUV['base_url']}/api/ConsultasFevRips/ConsultarCUV"
    body = {"codigoUnicoValidacion": cuv}

    resp = requests.post(
        url,
        json=body,
        headers={"Content-Type": "application/json"},
        verify=MUV["verify_ssl"],
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ─── Helpers internos ────────────────────────────────────────

def _loguear_resultado(num_factura, resultado):
    """Escribe en el log el resultado del MUV de forma legible."""
    estado = "APROBADO ✓" if resultado.get("ResultState") else "RECHAZADO ✗"
    cuv = resultado.get("CodigoUnicoValidacion", "—")
    log.info(f"  Factura {num_factura}: {estado} | CUV: {cuv[:20]}...")

    validaciones = resultado.get("ResultadosValidacion", [])
    rechazos = [v for v in validaciones if v.get("Clase") == "RECHAZADO"]
    notificaciones = [v for v in validaciones if v.get("Clase") == "NOTIFICACION"]

    if rechazos:
        log.warning(f"  Rechazos ({len(rechazos)}):")
        for r in rechazos:
            log.warning(f"    [{r.get('Codigo')}] {r.get('Descripcion')} — {r.get('PathFuente')}")

    if notificaciones:
        log.info(f"  Notificaciones ({len(notificaciones)}):")
        for n in notificaciones:
            log.info(f"    [{n.get('Codigo')}] {n.get('Descripcion')}")
