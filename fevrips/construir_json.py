# ============================================================
#  CONSTRUCTOR DE JSON RIPS — Resolución 2275 de 2023
#  Mapea los datos de la BD GCE al formato exacto del MUV
# ============================================================

from datetime import datetime
from config import IPS


# ─── Tablas de referencia (Resolución 2275) ──────────────────
# Mapa tipo documento SIGO → código RIPS
TIPO_DOC = {
    "CC":  "CC",   # Cédula de ciudadanía
    "TI":  "TI",   # Tarjeta de identidad
    "RC":  "RC",   # Registro civil
    "CE":  "CE",   # Cédula de extranjería
    "PA":  "PA",   # Pasaporte
    "MS":  "MS",   # Menor sin identificación
    "AS":  "AS",   # Adulto sin identificación
    "CD":  "CD",   # Carné diplomático
    "PE":  "PE",   # Permiso especial de permanencia
    "PT":  "PT",   # Permiso temporal de protección
    # TODO: agregar más si el sistema SIGO usa otros códigos
}

# Mapa sexo SIGO → código RIPS
SEXO = {
    "M": "M",   # Masculino
    "F": "F",   # Femenino
    "I": "I",   # Indeterminado/intersexual
    "N": "N",   # No aplica (recién nacidos sin definir)
    # TODO: confirmar cómo guarda el género la BD SIGO de esta IPS
}

# Zona territorial
ZONA = {
    "U": "01",  # Urbana → código 01
    "R": "02",  # Rural  → código 02
    # TODO: confirmar valores del campo PacZona en GCEPACIENTE
}


def _fmt_fecha(valor, con_hora=False):
    """Convierte datetime o string al formato que pide el RIPS."""
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    if con_hora:
        return valor.strftime("%Y-%m-%d %H:%M")
    return valor.strftime("%Y-%m-%d")


def _tipo_doc(codigo_sigo):
    """Traduce código de tipo de documento de SIGO al código RIPS."""
    return TIPO_DOC.get(str(codigo_sigo).strip().upper(), codigo_sigo)


def _sexo(codigo_sigo):
    return SEXO.get(str(codigo_sigo).strip().upper(), "N")


def _zona(codigo_sigo):
    return ZONA.get(str(codigo_sigo).strip().upper(), "01")


def _cod_municipio(tg_ci_codigo):
    """
    Convierte el código de ciudad interno de SIGO al código DIVIPOLA de 5 dígitos.

    TODO: implementar lookup a la tabla TGCIUDAD de la BD para obtener
    el código DIVIPOLA real. Por ahora retorna el código del municipio
    de la IPS como fallback.

    Ejemplo de query a implementar:
        SELECT TgCiDivipola FROM TGCIUDAD WHERE TgCiCodigo = ?
    """
    # TEMPORAL: retorna municipio de la IPS hasta implementar el lookup
    return IPS["cod_municipio"]


def construir_consulta(c, consecutivo):
    """
    Construye el objeto consulta según la estructura del MUV.
    'c' es una fila de obtener_consultas_factura().
    """
    return {
        "codPrestador":                 IPS["cod_prestador"],
        "fechaInicioAtencion":          _fmt_fecha(c["FechaAtencion"], con_hora=True),
        "numAutorizacion":              c.get("NumAutorizacion") or None,
        "codConsulta":                  str(c["CodCUPS"]).strip(),
        "modalidadGrupoServicioTecSal": "TODO: código modalidad, ej: 01",
        # Referencia de modalidades:
        # 01=Consulta externa, 02=Urgencias, 03=Hospitalización,
        # 04=Procedimiento ambulatorio, 05=Procedimiento hospitalario,
        # 06=Domiciliaria, 07=Telemedicina, 09=Otros
        "grupoServicios":               "TODO: código grupo, ej: 01",
        # Grupos: 01=Consultas, 02=Procedimientos, 03=Urgencias, etc.
        "codServicio":                  "TODO: código servicio habilitado REPS",
        "finalidadTecnologiaSalud":     "TODO: código finalidad, ej: 13",
        # Finalidades: 13=Atención del parto, 14=Atención RN, 15=Detección,
        # 16=Diagnóstico, 17=Tratamiento, 18=Rehabilitación, etc.
        "causaMotivoAtencion":          "TODO: código causa, ej: 23",
        # Causas: 21=Enfermedad general, 23=Accidente trabajo, 26=Maternidad, etc.
        "codDiagnosticoPrincipal":      str(c.get("DiagPrincipal") or "").strip() or None,
        "codDiagnosticoRelacionado1":   str(c.get("DiagRelacionado1") or "").strip() or None,
        "codDiagnosticoRelacionado2":   str(c.get("DiagRelacionado2") or "").strip() or None,
        "codDiagnosticoRelacionado3":   None,
        "tipoDiagnosticoPrincipal":     str(c.get("TipoDiagnostico") or "01").strip(),
        # 01=Impresión diagnóstica, 02=Confirmado nuevo, 03=Confirmado repetido
        "tipoDocumentoIdentificacion":  "TODO: tipo doc del médico tratante",
        "numDocumentoIdentificacion":   "TODO: número doc del médico tratante",
        "vrServicio":                   float(c.get("ValorServicio") or 0),
        "conceptoRecaudo":              "TODO: código concepto recaudo, ej: 05",
        # 01=Copago, 02=Cuota moderadora, 03=Pagos compartidos,
        # 04=Descuento, 05=Sin cobro al usuario
        "valorPagoModerador":           0,
        "numFEVPagoModerador":          None,
        "consecutivo":                  consecutivo,
    }


def construir_procedimiento(p, consecutivo):
    """Construye el objeto procedimiento según la estructura del MUV."""
    return {
        "codPrestador":                 IPS["cod_prestador"],
        "fechaInicioAtencion":          _fmt_fecha(p["FechaAtencion"], con_hora=True),
        "idMIPRES":                     None,
        "numAutorizacion":              p.get("NumAutorizacion") or None,
        "codProcedimiento":             str(p["CodCUPS"]).strip(),
        "viaIngresoServicioSalud":      "TODO: código vía ingreso, ej: 01",
        # 01=Consulta externa, 02=Urgencias, 03=Hospitalización, etc.
        "modalidadGrupoServicioTecSal": "TODO: código modalidad, ej: 01",
        "grupoServicios":               "TODO: código grupo, ej: 02",
        "codServicio":                  "TODO: código servicio habilitado REPS",
        "finalidadTecnologiaSalud":     "TODO: código finalidad, ej: 15",
        "tipoDocumentoIdentificacion":  "TODO: tipo doc del médico",
        "numDocumentoIdentificacion":   "TODO: número doc del médico",
        "codDiagnosticoPrincipal":      str(p.get("DiagPrincipal") or "").strip() or None,
        "codDiagnosticoRelacionado":    str(p.get("DiagRelacionado1") or "").strip() or None,
        "codComplicacion":              None,
        "vrServicio":                   float(p.get("ValorServicio") or 0),
        "valorPagoModerador":           0,
        "numFEVPagoModerador":          None,
        "conceptoRecaudo":              "TODO: código concepto recaudo, ej: 05",
        "consecutivo":                  consecutivo,
    }


def construir_medicamento(m, consecutivo):
    """Construye el objeto medicamento según la estructura del MUV."""
    return {
        "codPrestador":                 IPS["cod_prestador"],
        "numAutorizacion":              None,
        "idMIPRES":                     None,
        "fechaDispensAdmon":            _fmt_fecha(m.get("FechaDispensa"), con_hora=True),
        "codDiagnosticoPrincipal":      m.get("DiagPrincipal") or "TODO: CIE10 del diagnóstico",
        "codDiagnosticoRelacionado":    None,
        "tipoMedicamento":              m.get("TipoMedicamento") or "TODO: 01=PBS, 02=NoPBS, 03=Otro",
        "codTecnologiaSalud":           str(m.get("CodMedicamento") or "").strip(),
        # Es el código del INVIMA o del sistema, según configuración
        "nomTecnologiaSalud":           m.get("NombreMedicamento") or None,
        "concentracionMedicamento":     m.get("Concentracion") or 0,
        "unidadMedida":                 m.get("UnidadMedida") or "TODO: código unidad medida",
        "formaFarmaceutica":            None,
        "unidadMinDispensa":            1,
        "cantidadMedicamento":          int(m.get("Cantidad") or 1),
        "diasTratamiento":              int(m.get("DiasTratamiento") or 1),
        "tipoDocumentoIdentificacion":  "TODO: tipo doc médico que prescribió",
        "numDocumentoIdentificacion":   "TODO: número doc médico que prescribió",
        "vrUnitMedicamento":            0,
        "vrServicio":                   0,
        "conceptoRecaudo":              "TODO: código concepto recaudo",
        "valorPagoModerador":           0,
        "numFEVPagoModerador":          None,
        "consecutivo":                  consecutivo,
    }


def construir_usuario(fac, consultas_rows, procedimientos_rows, medicamentos_rows, consecutivo_usuario):
    """
    Arma el objeto usuario completo con todos sus servicios.
    'fac' es una fila de obtener_facturas_pendientes().
    """
    servicios = {}

    if consultas_rows:
        servicios["consultas"] = [
            construir_consulta(c, i + 1)
            for i, c in enumerate(consultas_rows)
        ]

    if procedimientos_rows:
        servicios["procedimientos"] = [
            construir_procedimiento(p, i + 1)
            for i, p in enumerate(procedimientos_rows)
        ]

    if medicamentos_rows:
        servicios["medicamentos"] = [
            construir_medicamento(m, i + 1)
            for i, m in enumerate(medicamentos_rows)
        ]

    return {
        "consecutivo":                      consecutivo_usuario,
        "tipoDocumentoIdentificacion":      _tipo_doc(fac["PacTipId"]),
        "numDocumentoIdentificacion":       str(fac["PacNumId"]).strip(),
        "tipoUsuario":                      str(fac.get("TipoUsuario") or "TODO: 01-13").strip(),
        # Tipo usuario: 01=Contributivo cotizante, 02=Contributivo beneficiario,
        # 03=Vinculado, 04=Particular, 05=Desplazado cotizante, etc.
        "fechaNacimiento":                  _fmt_fecha(fac.get("PacFecNac")),
        "codSexo":                          _sexo(fac.get("PacGenero")),
        "codPaisResidencia":                "170",       # Colombia
        "codMunicipioResidencia":           _cod_municipio(fac.get("TgCiCodigo")),
        "codZonaTerritorialResidencia":     _zona(fac.get("PacZona")),
        "incapacidad":                      "NO",        # TODO: leer de HC si aplica
        "codPaisOrigen":                    "170",
        "servicios":                        servicios,
    }


def construir_json_rips(fac, consultas, procedimientos, medicamentos):
    """
    Punto de entrada principal. Construye el JSON completo de RIPS
    listo para enviarse al endpoint CargarFevRips del MUV.

    Retorna un dict con las claves 'rips' y 'xmlFevFile'.
    """
    usuario = construir_usuario(fac, consultas, procedimientos, medicamentos, consecutivo_usuario=1)

    rips = {
        "numDocumentoIdObligado": IPS["nit"].replace("-", "").replace(".", ""),
        "numFactura":             str(fac["FacNumero"]).strip(),
        "tipoNota":               None,
        "numNota":                None,
        "usuarios":               [usuario],
    }

    return {
        "rips":       rips,
        "xmlFevFile": "TODO: contenido Base64 del XML de la factura DIAN",
        # Este valor debe reemplazarse con el Base64 real del AttachedDocument
        # XML que genera el software de facturación electrónica (DIAN).
        # Ver función cargar_xml_factura() en muv_client.py
    }
