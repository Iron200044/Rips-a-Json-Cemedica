# ============================================================
#  CONSULTAS SQL — Extracción de datos desde SIGO/GCE
#  Basado en el schema real de la BD (script_prueba.sql)
# ============================================================

import pyodbc
from config import DB
from fevrips.logger import log


def conectar():
    """Abre la conexión a SQL Server. Retorna el objeto connection."""
    conn_str = (
        f"DRIVER={{{DB['driver']}}};"
        f"SERVER={DB['server']},{DB['port']};"
        f"DATABASE={DB['database']};"
        f"UID={DB['username']};"
        f"PWD={DB['password']};"
        "TrustServerCertificate=yes;"
        "Encrypt=no;"
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=30)
        log.info("Conexión a SQL Server exitosa.")
        return conn
    except Exception as e:
        log.error(f"Error conectando a SQL Server: {e}")
        raise


def obtener_facturas_pendientes(conn, fecha_desde=None, fecha_hasta=None, num_factura=None):
    """
    Retorna lista de facturas de GCEFACTURA que aún no tienen CUV
    y tienen paciente + aseguradora asociados.

    Parámetros opcionales:
      fecha_desde / fecha_hasta : filtrar por rango de fechas (datetime)
      num_factura               : buscar una factura específica
    """
    where_extra = ""
    params = []

    if num_factura:
        where_extra += " AND f.FacNumero = ?"
        params.append(num_factura)
    if fecha_desde:
        where_extra += " AND f.FacFecha >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        where_extra += " AND f.FacFecha <= ?"
        params.append(fecha_hasta)

    sql = f"""
    SELECT
        f.FacNumero,
        f.FacFecha,
        f.FacFechaI,
        f.FacFechaF,
        f.FacEstado,
        f.FacTotal,
        f.PacCodigoF,

        -- Datos del paciente
        p.PacTipId,
        p.PacNumId,
        p.PacPriNom,
        p.PacSegNom,
        p.PacPriApe,
        p.PacSegApe,
        p.PacFecNac,
        p.PacGenero,
        p.PacZona,
        p.TgPaCodigo,     -- código país
        p.TgDpCodigo,     -- código departamento
        p.TgCiCodigo,     -- código ciudad/municipio

        -- Datos de la aseguradora
        a.AseNombre,
        a.AseNumId        AS AseNit,
        a.AseTipoUsuRips  AS TipoUsuario,
        a.AseCodRips      AS CoberturaPlan

    FROM GCEFACTURA f
    INNER JOIN GCEPACIENTE  p ON p.PacCodigo = f.PacCodigoF
    LEFT  JOIN GCEASEGURA   a ON a.AseIdAseg = f.AseIdAsegF
    WHERE f.FacEstado = 'A'   -- 'A' = Activa/Aprobada. TODO: confirmar código de estado
      {where_extra}
    ORDER BY f.FacFecha ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, params)
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in cursor.fetchall()]


def obtener_consultas_factura(conn, num_factura, pac_num_id):
    """
    Retorna las consultas médicas de una factura desde GCERIPSCONSULTA.
    Incluye diagnósticos desde GCEHCDX (a través de la historia).
    """
    sql = """
    SELECT
        rc.RAgeFechaC        AS FechaAtencion,
        rc.RAgeVolante       AS NumAutorizacion,
        rc.RSvCodigo         AS CodCUPS,
        rc.RCeCodigo         AS CodEspecialidad,
        rc.RValor            AS ValorServicio,
        rc.RDx1              AS DiagPrincipal,
        rc.RDx2              AS DiagRelacionado1,
        rc.RDx3              AS DiagRelacionado2,
        rc.RTipoDx           AS TipoDiagnostico,
        rc.RAgIdAge          AS IdAgenda,

        -- Servicio: descripción y clase
        sv.SvDescrip         AS NombreServicio,
        sv.SvClase           AS ClaseServicio,
        sv.SvSubClase        AS SubclaseServicio,

        -- Datos del médico desde la agenda/historia
        -- TODO: ajustar join si la IPS usa otra tabla para médico tratante
        ag.MedCod            AS CodMedico

    FROM GCERIPSCONSULTA rc
    LEFT JOIN GCESERVICIO sv ON sv.SvCodigo = rc.RSvCodigo
    LEFT JOIN GCEAGENDA   ag ON ag.AgIdAge  = rc.RAgIdAge
    WHERE rc.RCFacNum   = ?
      AND rc.RPacNumId  = ?
    ORDER BY rc.RAgeFechaC ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in cursor.fetchall()]


def obtener_procedimientos_factura(conn, num_factura, pac_num_id):
    """
    Retorna los procedimientos de una factura desde GCERIPSPROCEDIM.
    """
    sql = """
    SELECT
        rp.RPAgeFechaC       AS FechaAtencion,
        rp.RPAgeVolante      AS NumAutorizacion,
        rp.RPSvCodigo        AS CodCUPS,
        rp.RPCeCodigo        AS CodEspecialidad,
        rp.RPValor           AS ValorServicio,
        rp.RPDx1             AS DiagPrincipal,
        rp.RPDx2             AS DiagRelacionado1,
        rp.RPDx3             AS DiagRelacionado2,
        rp.RPTipoDx          AS TipoDiagnostico,
        rp.RPAgIdAge         AS IdAgenda,

        sv.SvDescrip         AS NombreServicio,
        sv.SvClase           AS ClaseServicio

    FROM GCERIPSPROCEDIM rp
    LEFT JOIN GCESERVICIO sv ON sv.SvCodigo = rp.RPSvCodigo
    WHERE rp.RPNumFac   = ?
      AND rp.RPPacNumId = ?
    ORDER BY rp.RPAgeFechaC ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in cursor.fetchall()]


def obtener_medicamentos_factura(conn, num_factura, pac_num_id):
    """
    Retorna medicamentos de GCEHCMEDICAMENTOS asociados a la historia
    cuya atención está en la factura indicada.

    TODO: Confirmar el join correcto entre la factura y la historia clínica
    en el sistema SIGO de esta IPS específica. La relación puede pasar
    por GCEFACTSERV → GCEAGENDA → GCEHCHISTORIA.
    """
    sql = """
    SELECT
        fs.RfFechaServ       AS FechaDispensa,
        fs.RfSvCodigo        AS CodMedicamento,
        sv.SvDescrip         AS NombreMedicamento,
        fs.RfCantidad        AS Cantidad,

        -- TODO: agregar valor unitario y total cuando se confirme la columna
        -- fs.RfValorUnit    AS ValorUnitario,

        -- Diagnóstico principal: viene de la historia clínica
        -- TODO: confirmar join a GCEHCMEDICAMENTOS si la IPS lo usa
        NULL                 AS DiagPrincipal,
        NULL                 AS TipoMedicamento,   -- 01=Pos, 02=NoPBS, etc.
        NULL                 AS Concentracion,
        NULL                 AS UnidadMedida,
        NULL                 AS DiasTratemiento

    FROM GCEFACTSERV fs
    LEFT JOIN GCESERVICIO sv ON sv.SvCodigo = fs.RfSvCodigo
    WHERE fs.RfFacNumero = ?
      AND fs.RfPacNumId  = ?
    ORDER BY fs.RfFechaServ ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in cursor.fetchall()]


def obtener_hospitalizaciones_factura(conn, num_factura, pac_num_id):
    """
    Retorna hospitalizaciones desde GCEHCHISTORIA para facturas
    con tipo de historia de hospitalización (hctipoHis = 'H' o similar).

    TODO: confirmar el valor de hctipoHis que usa esta IPS para hospitalización.
    """
    sql = """
    SELECT
        h.HcIdHisto          AS IdHistoria,
        h.HcFechaIng         AS FechaIngreso,
        h.HcFechaEgr         AS FechaEgreso,
        h.HcEstado           AS Estado,
        h.HcCondUsua         AS CondicionUsuario,
        h.hctipoHis          AS TipoHistoria,
        h.CexCodigo          AS CausaExterna,

        -- Diagnósticos de la hospitalización
        dx.DxCodigo          AS CodDiagnostico,
        dx.HcDxClase         AS ClaseDx,   -- 'P'=Principal, 'R'=Relacionado
        dx.HcDxTp            AS TipoDx,

        -- Médico tratante
        h.MedCodH            AS CodMedico

    FROM GCEHCHISTORIA h
    INNER JOIN GCEHCDX dx ON dx.HcIdHisto = h.HcIdHisto
    -- TODO: confirmar join con factura. Puede ser via GCEAGENDA o GCEFACTSERV
    WHERE h.PacCodigo = (
        SELECT PacCodigoF FROM GCEFACTURA WHERE FacNumero = ?
    )
      AND h.hctipoHis = 'H'   -- TODO: confirmar código de hospitalización
    ORDER BY h.HcFechaIng ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura])
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, row)) for row in cursor.fetchall()]
