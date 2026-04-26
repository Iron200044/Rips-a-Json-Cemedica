# ============================================================
#  CONSTRUCTOR JSON RIPS — Mapeado al esquema real GCEV2
#  Resolución 2275 de 2023
# ============================================================
from datetime import datetime
from config import IPS
from db_queries import obtener_divipola

# GCEPACIENTE.PacTipId → código RIPS
TIPO_DOC = {
    "CC": "CC", "TI": "TI", "RC": "RC", "CE": "CE",
    "PA": "PA", "MS": "MS", "AS": "AS", "CD": "CD",
    "PE": "PE", "PT": "PT",
}

# GCEPACIENTE.PacGenero → código RIPS
SEXO = {"M": "M", "F": "F", "I": "I", "N": "N"}

# GCEPACIENTE.PacZona → código RIPS
ZONA = {"U": "01", "R": "02"}

# GCEMEDICAMENTO.Mdpos → tipoMedicamento RIPS
TIPO_MEDICAMENTO = {"S": "01", "N": "02"}   # S=PBS, N=NoPBS


def _fmt(valor, con_hora=False):
    if valor is None:
        return None
    if isinstance(valor, str):
        try:
            valor = datetime.fromisoformat(valor)
        except Exception:
            return valor
    return valor.strftime("%Y-%m-%d %H:%M") if con_hora else valor.strftime("%Y-%m-%d")


def _tdoc(cod):
    return TIPO_DOC.get(str(cod or "").strip().upper(), cod)

def _sexo(cod):
    return SEXO.get(str(cod or "").strip().upper(), "N")

def _zona(cod):
    return ZONA.get(str(cod or "").strip().upper(), "01")


def construir_consulta(c, consecutivo):
    # Autorización: RAgeVolante de GCERIPSCONSULTA, fallback AgVolante de GCEAGENDA
    autorizacion = c.get("NumAutorizacion") or c.get("AgVolante") or None

    return {
        "codPrestador":                  IPS["cod_prestador"],
        "fechaInicioAtencion":           _fmt(c["FechaAtencion"], con_hora=True),
        # GCERIPSCONSULTA.RAgeFechaC
        "numAutorizacion":               autorizacion,
        "codConsulta":                   str(c["CodCUPS"]).strip(),
        # GCERIPSCONSULTA.RSvCodigo
        "modalidadGrupoServicioTecSal":  "TODO: ej 01=Consulta externa, 02=Urgencias",
        "grupoServicios":                "TODO: ej 01=Consultas, 02=Procedimientos",
        "codServicio":                   "TODO: código servicio habilitado REPS",
        "finalidadTecnologiaSalud":      "TODO: ej 16=Diagnóstico, 17=Tratamiento",
        "causaMotivoAtencion":           "TODO: ej 21=Enfermedad general, 26=Maternidad",
        "codDiagnosticoPrincipal":       str(c.get("DiagPrincipal") or "").strip() or None,
        # GCERIPSCONSULTA.RDx1
        "codDiagnosticoRelacionado1":    str(c.get("DiagRelacionado1") or "").strip() or None,
        # GCERIPSCONSULTA.RDx2
        "codDiagnosticoRelacionado2":    str(c.get("DiagRelacionado2") or "").strip() or None,
        # GCERIPSCONSULTA.RDx3
        "codDiagnosticoRelacionado3":    None,
        "tipoDiagnosticoPrincipal":      str(c.get("TipoDiagnostico") or "01").strip(),
        # GCERIPSCONSULTA.RTipoDx — 01=Impresión, 02=Confirmado nuevo, 03=Confirmado repetido
        "tipoDocumentoIdentificacion":   _tdoc(c.get("MedTipId")),
        # GCEMEDICO.MedTipId (via GCEAGENDA.MedCod)
        "numDocumentoIdentificacion":    str(c.get("MedNumId") or "").strip() or None,
        # GCEMEDICO.MedNumId (via GCEAGENDA.MedCod)
        "vrServicio":                    float(c.get("ValorServicio") or 0),
        # GCERIPSCONSULTA.RValor
        "conceptoRecaudo":               "TODO: ej 05=Sin cobro, 01=Copago, 02=Cuota moderadora",
        "valorPagoModerador":            0,
        "numFEVPagoModerador":           None,
        "consecutivo":                   consecutivo,
    }


def construir_procedimiento(p, consecutivo):
    autorizacion = p.get("NumAutorizacion") or p.get("AgVolante") or None
    return {
        "codPrestador":                  IPS["cod_prestador"],
        "fechaInicioAtencion":           _fmt(p["FechaAtencion"], con_hora=True),
        # GCERIPSPROCEDIM.RPAgeFechaC
        "idMIPRES":                      None,
        "numAutorizacion":               autorizacion,
        "codProcedimiento":              str(p["CodCUPS"]).strip(),
        # GCERIPSPROCEDIM.RPSvCodigo
        "viaIngresoServicioSalud":       "TODO: ej 01=Consulta externa, 02=Urgencias, 03=Hospitalización",
        "modalidadGrupoServicioTecSal":  "TODO: ej 01",
        "grupoServicios":                "TODO: ej 02=Procedimientos",
        "codServicio":                   "TODO: código servicio habilitado REPS",
        "finalidadTecnologiaSalud":      "TODO: ej 15=Detección, 17=Tratamiento",
        "tipoDocumentoIdentificacion":   _tdoc(p.get("MedTipId")),
        # GCEMEDICO.MedTipId (via GCEAGENDA.MedCod)
        "numDocumentoIdentificacion":    str(p.get("MedNumId") or "").strip() or None,
        # GCEMEDICO.MedNumId (via GCEAGENDA.MedCod)
        "codDiagnosticoPrincipal":       str(p.get("DiagPrincipal") or "").strip() or None,
        # GCERIPSPROCEDIM.RPDx1
        "codDiagnosticoRelacionado":     str(p.get("DiagRelacionado1") or "").strip() or None,
        # GCERIPSPROCEDIM.RPDx2
        "codComplicacion":               None,
        "vrServicio":                    float(p.get("ValorServicio") or 0),
        # GCERIPSPROCEDIM.RPValor
        "valorPagoModerador":            0,
        "numFEVPagoModerador":           None,
        "conceptoRecaudo":               "TODO: ej 05=Sin cobro, 01=Copago",
        "consecutivo":                   consecutivo,
    }


def construir_medicamento(m, consecutivo):
    # GCEMEDICAMENTO.Mdpos: 'S'=PBS → "01", 'N'=NoPBS → "02"
    tipo_med = TIPO_MEDICAMENTO.get(str(m.get("EsPOS") or "").strip().upper(), "TODO: 01=PBS, 02=NoPBS")
    return {
        "codPrestador":                  IPS["cod_prestador"],
        "numAutorizacion":               None,
        "idMIPRES":                      None,
        "fechaDispensAdmon":             _fmt(m.get("FechaDispensa"), con_hora=True),
        # GCEHCHISTORIA.HcFechaIng
        "codDiagnosticoPrincipal":       m.get("DiagPrincipal") or "TODO: CIE10",
        # GCEHCDX.DxCodigo donde HcDxClase='P'
        "codDiagnosticoRelacionado":     None,
        "tipoMedicamento":               tipo_med,
        # GCEMEDICAMENTO.Mdpos → 'S'=01=PBS, 'N'=02=NoPBS
        "codTecnologiaSalud":            str(m.get("CodMedicamento") or "").strip(),
        # GCEHCMEDICAMENTOS.MdCodigo
        "nomTecnologiaSalud":            m.get("NombreMedicamento") or None,
        # GCEMEDICAMENTO.MdDescripcion
        "concentracionMedicamento":      m.get("Concentracion") or 0,
        # GCEMEDICAMENTO.MdConcentra
        "unidadMedida":                  m.get("UnidadMedida") or "TODO: código unidad",
        # GCEMEDICAMUNDM.MdUndDesc (via GCEMEDICAMENTO.MdUndMed)
        "formaFarmaceutica":             None,
        "unidadMinDispensa":             1,
        "cantidadMedicamento":           int(m.get("Cantidad") or 1),
        # GCEHCMEDICAMENTOS.MedCant
        "diasTratamiento":               1,
        # GCEHCMEDICAMENTOS no tiene columna de días — TODO: confirmar fuente
        "tipoDocumentoIdentificacion":   _tdoc(m.get("MedTipId")),
        # GCEMEDICO.MedTipId (via GCEHCHISTORIA.MedCodH)
        "numDocumentoIdentificacion":    str(m.get("MedNumId") or "").strip() or None,
        # GCEMEDICO.MedNumId (via GCEHCHISTORIA.MedCodH)
        "vrUnitMedicamento":             0,
        "vrServicio":                    0,
        "conceptoRecaudo":               "TODO: ej 05=Sin cobro",
        "valorPagoModerador":            0,
        "numFEVPagoModerador":           None,
        "consecutivo":                   consecutivo,
    }


def construir_usuario(fac, consultas_rows, procedimientos_rows, medicamentos_rows, consecutivo_usuario):
    servicios = {}
    if consultas_rows:
        servicios["consultas"] = [construir_consulta(c, i+1) for i, c in enumerate(consultas_rows)]
    if procedimientos_rows:
        servicios["procedimientos"] = [construir_procedimiento(p, i+1) for i, p in enumerate(procedimientos_rows)]
    if medicamentos_rows:
        servicios["medicamentos"] = [construir_medicamento(m, i+1) for i, m in enumerate(medicamentos_rows)]

    # Municipio: construido desde GCEPACIENTE.TgDpCodigo + TgCiCodigo
    cod_mpio = obtener_divipola(fac.get("TgDpCodigo"), fac.get("TgCiCodigo")) or IPS["cod_municipio"]

    return {
        "consecutivo":                      consecutivo_usuario,
        "tipoDocumentoIdentificacion":       _tdoc(fac["PacTipId"]),
        # GCEPACIENTE.PacTipId
        "numDocumentoIdentificacion":        str(fac["PacNumId"]).strip(),
        # GCEPACIENTE.PacNumId
        "tipoUsuario":                       str(fac.get("TipoUsuario") or "TODO: 01-13").strip(),
        # GCEASEGURA.AseTipoUsuRips
        "fechaNacimiento":                   _fmt(fac.get("PacFecNac")),
        # GCEPACIENTE.PacFecNac
        "codSexo":                           _sexo(fac.get("PacGenero")),
        # GCEPACIENTE.PacGenero
        "codPaisResidencia":                 "170",
        "codMunicipioResidencia":            cod_mpio,
        # GCEPACIENTE.TgDpCodigo + TgCiCodigo → DIVIPOLA
        "codZonaTerritorialResidencia":      _zona(fac.get("PacZona")),
        # GCEPACIENTE.PacZona
        "incapacidad":                       "NO",
        "codPaisOrigen":                     "170",
        "servicios":                         servicios,
    }


def construir_json_rips(fac, consultas, procedimientos, medicamentos):
    usuario = construir_usuario(fac, consultas, procedimientos, medicamentos, 1)
    rips = {
        "numDocumentoIdObligado": IPS["nit"].replace("-", "").replace(".", ""),
        "numFactura":             str(fac["FacNumero"]).strip(),
        "tipoNota":               None,
        "numNota":                None,
        "usuarios":               [usuario],
    }
    return {
        "rips":       rips,
        "xmlFevFile": "TODO: Base64 del AttachedDocument XML de la DIAN",
    }