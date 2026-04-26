# ============================================================
#  CONSULTAS SQL — Esquema real GCEV2
# ============================================================
import pyodbc
from config import DB
from logger import log


def conectar():
    conn_str = (
        f"DRIVER={{{DB['driver']}}};"
        f"SERVER={DB['server']},{DB['port']};"
        f"DATABASE={DB['database']};"
        f"UID={DB['username']};"
        f"PWD={DB['password']};"
        "TrustServerCertificate=yes;Encrypt=no;"
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
    GCEFACTURA + GCEPACIENTE + GCEASEGURA + GCEMEDICO
    Joins confirmados del esquema:
      GCEFACTURA.PacCodigoF → GCEPACIENTE.PacCodigo
      GCEFACTURA.AseIdAsegF → GCEASEGURA.AseIdAseg
      GCEFACTURA.MedCodF    → GCEMEDICO.MedCod
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
        f.CmIdCentroF,

        p.PacCodigo,
        p.PacTipId,
        p.PacNumId,
        p.PacPriNom,
        p.PacSegNom,
        p.PacPriApe,
        p.PacSegApe,
        p.PacFecNac,
        p.PacGenero,
        p.PacZona,
        p.TgPaCodigo,
        p.TgDpCodigo,
        p.TgCiCodigo,

        a.AseIdAseg,
        a.AseNombre,
        a.AseNumId       AS AseNit,
        a.AseTipId       AS AseTipoId,
        a.AseCodRips     AS CoberturaPlan,
        a.AseTipoUsuRips AS TipoUsuario,
        a.AseNomRIPs     AS AseNombreRips,

        m.MedTipId,
        m.MedNumId

    FROM GCEFACTURA f
    INNER JOIN GCEPACIENTE p ON p.PacCodigo = f.PacCodigoF
    LEFT  JOIN GCEASEGURA  a ON a.AseIdAseg = f.AseIdAsegF
    LEFT  JOIN GCEMEDICO   m ON m.MedCod    = f.MedCodF
    WHERE f.FacEstado = 'A'
      {where_extra}
    ORDER BY f.FacFecha ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def obtener_consultas_factura(conn, num_factura, pac_num_id):
    """
    GCERIPSCONSULTA + GCESERVICIO + GCEAGENDA + GCEMEDICO
    Joins confirmados:
      GCERIPSCONSULTA.RCFacNum  → GCEFACTURA.FacNumero
      GCERIPSCONSULTA.RPacNumId → GCEPACIENTE.PacNumId
      GCERIPSCONSULTA.RSvCodigo → GCESERVICIO.SvCodigo
      GCERIPSCONSULTA.RAgIdAge  → GCEAGENDA.AgIdAge
      GCEAGENDA.MedCod          → GCEMEDICO.MedCod
    """
    sql = """
    SELECT
        rc.RAgeFechaC  AS FechaAtencion,
        rc.RAgeVolante AS NumAutorizacion,
        rc.RSvCodigo   AS CodCUPS,
        rc.RCeCodigo   AS CodEspecialidad,
        rc.RValor      AS ValorServicio,
        rc.RDx1        AS DiagPrincipal,
        rc.RDx2        AS DiagRelacionado1,
        rc.RDx3        AS DiagRelacionado2,
        rc.RTipoDx     AS TipoDiagnostico,

        sv.SvDescrip   AS NombreServicio,
        sv.SvClase     AS ClaseServicio,
        sv.SvSubClase  AS SubclaseServicio,

        ag.AgVolante   AS AgVolante,
        ag.AgPlan      AS AgPlan,

        m.MedTipId     AS MedTipId,
        m.MedNumId     AS MedNumId

    FROM GCERIPSCONSULTA rc
    LEFT JOIN GCESERVICIO sv ON sv.SvCodigo = rc.RSvCodigo
    LEFT JOIN GCEAGENDA   ag ON ag.AgIdAge  = rc.RAgIdAge
    LEFT JOIN GCEMEDICO    m ON m.MedCod    = ag.MedCod
    WHERE rc.RCFacNum  = ?
      AND rc.RPacNumId = ?
    ORDER BY rc.RAgeFechaC ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def obtener_procedimientos_factura(conn, num_factura, pac_num_id):
    """
    GCERIPSPROCEDIM + GCESERVICIO + GCEAGENDA + GCEMEDICO
    Joins confirmados:
      GCERIPSPROCEDIM.RPNumFac    → GCEFACTURA.FacNumero
      GCERIPSPROCEDIM.RPPacNumId  → GCEPACIENTE.PacNumId
      GCERIPSPROCEDIM.RPSvCodigo  → GCESERVICIO.SvCodigo
      GCERIPSPROCEDIM.RPAgIdAge   → GCEAGENDA.AgIdAge
    """
    sql = """
    SELECT
        rp.RPAgeFechaC  AS FechaAtencion,
        rp.RPAgeVolante AS NumAutorizacion,
        rp.RPSvCodigo   AS CodCUPS,
        rp.RPCeCodigo   AS CodEspecialidad,
        rp.RPValor      AS ValorServicio,
        rp.RPDx1        AS DiagPrincipal,
        rp.RPDx2        AS DiagRelacionado1,
        rp.RPDx3        AS DiagRelacionado2,
        rp.RPTipoDx     AS TipoDiagnostico,

        sv.SvDescrip    AS NombreServicio,
        sv.SvClase      AS ClaseServicio,

        ag.AgVolante    AS AgVolante,

        m.MedTipId      AS MedTipId,
        m.MedNumId      AS MedNumId

    FROM GCERIPSPROCEDIM rp
    LEFT JOIN GCESERVICIO sv ON sv.SvCodigo = rp.RPSvCodigo
    LEFT JOIN GCEAGENDA   ag ON ag.AgIdAge  = rp.RPAgIdAge
    LEFT JOIN GCEMEDICO    m ON m.MedCod    = ag.MedCod
    WHERE rp.RPNumFac   = ?
      AND rp.RPPacNumId = ?
    ORDER BY rp.RPAgeFechaC ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def obtener_medicamentos_factura(conn, num_factura, pac_num_id):
    """
    GCEFACTSERV → GCEPACIENTE → GCEHCHISTORIA → GCEHCMEDICAMENTOS
                                               → GCEMEDICAMENTO → GCEMEDICAMUNDM
                                               → GCEHCDX (HcDxClase='P')
                                               → GCEMEDICO
    Joins confirmados:
      GCEFACTSERV.RfFacNumero  → GCEFACTURA.FacNumero
      GCEFACTSERV.RfPacNumId   → GCEPACIENTE.PacNumId
      GCEHCMEDICAMENTOS.MdCodigo → GCEMEDICAMENTO.MdCodigo
      GCEMEDICAMENTO.MdUndMed    → GCEMEDICAMUNDM.MdUndMed
    Nota: GCEFACTSERV no tiene valor unitario en el esquema.
    """
    sql = """
    SELECT
        hm.MdCodigo      AS CodMedicamento,
        md.MdDescripcion AS NombreMedicamento,
        md.MdConcentra   AS Concentracion,
        md.Mdpos         AS EsPOS,
        hm.MedCant       AS Cantidad,
        hm.MedPresc      AS Prescripcion,
        um.MdUndDesc     AS UnidadMedida,
        h.HcFechaIng     AS FechaDispensa,
        h.HcIdHisto      AS IdHistoria,
        dx.DxCodigo      AS DiagPrincipal,
        me.MedTipId      AS MedTipId,
        me.MedNumId      AS MedNumId

    FROM GCEFACTSERV fs
    INNER JOIN GCEPACIENTE      pac ON pac.PacNumId    = fs.RfPacNumId
    INNER JOIN GCEHCHISTORIA      h ON h.PacCodigo     = pac.PacCodigo
    INNER JOIN GCEHCMEDICAMENTOS hm ON hm.HcIdHisto    = h.HcIdHisto
    LEFT  JOIN GCEMEDICAMENTO    md ON md.MdCodigo     = hm.MdCodigo
    LEFT  JOIN GCEMEDICAMUNDM    um ON um.MdUndMed     = md.MdUndMed
    LEFT  JOIN GCEHCDX           dx ON dx.HcIdHisto    = h.HcIdHisto
                                    AND dx.HcDxClase   = 'P'
    LEFT  JOIN GCEMEDICO         me ON me.MedCod       = h.MedCodH
    WHERE fs.RfFacNumero = ?
      AND fs.RfPacNumId  = ?
    ORDER BY h.HcFechaIng ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [num_factura, pac_num_id])
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def obtener_hospitalizaciones_factura(conn, pac_num_id):
    """
    GCEHCHISTORIA + GCEHCDX + GCEMEDICO para hctipoHis = 'H'
    Joins confirmados:
      GCEHCHISTORIA.PacCodigo  → GCEPACIENTE.PacCodigo
      GCEHCHISTORIA.MedCodH    → GCEMEDICO.MedCod
      GCEHCDX.HcIdHisto        → GCEHCHISTORIA.HcIdHisto
        HcDxClase='P' → principal, 'R' → relacionado
    TODO: confirmar valor de hctipoHis para hospitalización en esta IPS.
    """
    sql = """
    SELECT
        h.HcIdHisto    AS IdHistoria,
        h.HcFechaIng   AS FechaIngreso,
        h.HcFechaEgr   AS FechaEgreso,
        h.HcEstado     AS Estado,
        h.HcCondUsua   AS CondicionUsuario,
        h.hctipoHis    AS TipoHistoria,
        h.CexCodigo    AS CausaExterna,
        h.HcPriCon     AS PrimeraVez,
        dx.DxCodigo    AS CodDiagnostico,
        dx.HcDxClase   AS ClaseDx,
        dx.HcDxTp      AS TipoDx,
        m.MedTipId     AS MedTipId,
        m.MedNumId     AS MedNumId

    FROM GCEHCHISTORIA h
    INNER JOIN GCEPACIENTE pac ON pac.PacCodigo = h.PacCodigo
    LEFT  JOIN GCEHCDX     dx  ON dx.HcIdHisto  = h.HcIdHisto
    LEFT  JOIN GCEMEDICO    m  ON m.MedCod      = h.MedCodH
    WHERE pac.PacNumId = ?
      AND h.hctipoHis  = 'H'
    ORDER BY h.HcFechaIng ASC
    """
    cursor = conn.cursor()
    cursor.execute(sql, [pac_num_id])
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def obtener_divipola(tg_dp_codigo, tg_ci_codigo):
    """
    Construye código DIVIPOLA de 5 dígitos desde TgDpCodigo + TgCiCodigo.
    TGCIUDAD no tiene columna DIVIPOLA directa — se arma por concatenación.
    TODO: validar contra tabla oficial si hay discrepancias.
    """
    if tg_dp_codigo and tg_ci_codigo:
        return f"{int(tg_dp_codigo):02d}{int(tg_ci_codigo):03d}"
    return None