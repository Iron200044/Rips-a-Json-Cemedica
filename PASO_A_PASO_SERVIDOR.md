# Guía de instalación y configuración — FEV-RIPS IPS
# Ministerio de Salud · Resolución 2275 de 2023

## PARTE 1 — Preparar el servidor (una sola vez)

### Requisitos mínimos del servidor
- Windows 10 SP1 o superior / Windows Server 2016+
- Procesador: mínimo 3 núcleos a 2GHz (recomendado 4 núcleos a 3GHz)
- RAM: mínimo 4 GB (recomendado 8 GB)
- Disco: 100 GB libres
- Conexión a internet: mínimo 2 Mbps subida / 4 Mbps bajada
- .NET Framework 4.8 instalado
- Python 3.10 o superior instalado

---

## PARTE 2 — Instalar el MUV (Validador local del Ministerio)

### Paso 1 — Descargar el instalador
1. Abrir el navegador en el servidor
2. Ir a: https://www.sispro.gov.co/central-financiamiento/Pages/facturacion-electronica.aspx
3. Buscar la sección **Producción** → **Instalador Versión 1.4.7.0**
4. Descargar el archivo: `FVE.ValidadorLocalBundleInstaller.exe`

### Paso 2 — Ejecutar el instalador
1. Clic derecho sobre el `.exe` → "Ejecutar como administrador"
2. Si Windows muestra advertencia de seguridad:
   - Clic en "Más información"
   - Clic en "Ejecutar de todas formas"
3. Aceptar los términos de licencia → marcar la casilla
4. Clic en **Install**
5. Cuando pregunte la ruta de instalación, dejar la ruta por defecto
6. Clic en **Next** → **Install**
   (Este paso puede tardar varios minutos — instala SQL Server Express LocalDB)
7. Clic en **Finish**
8. Cuando pregunte reiniciar → clic en **Restart**

### Paso 3 — Verificar que quedó instalado
1. Después del reinicio, buscar en el Escritorio el ícono **FEV-RIPS Validador**
2. Abrir el programa
3. Debería aparecer la pantalla de login del MUV
4. El servicio queda corriendo en segundo plano en el puerto **9443**

### Paso 4 — Registrar la IPS en SISPRO (si no está registrada)
1. Ir a: https://www.miseguridadsocial.gov.co
2. Registrar o verificar el usuario del representante legal de la IPS
3. El usuario debe estar vinculado al NIT de la IPS
4. Guardar las credenciales (las necesita el programa Python)

---

## PARTE 3 — Instalar el programa Python

### Paso 1 — Verificar que Python esté instalado
Abrir la consola de Windows (cmd) y escribir:
```
python --version
```
Si no está instalado, descargarlo de https://www.python.org/downloads/
(marcar la opción "Add Python to PATH" durante la instalación)

### Paso 2 — Copiar los archivos del programa
Crear la carpeta `C:\FEVRIPS\programa\` y copiar ahí todos estos archivos:
```
config.py
db_queries.py
construir_json.py
muv_client.py
estado_db.py
logger.py
main.py
requirements.txt
```

### Paso 3 — Instalar el driver ODBC para SQL Server
1. Descargar de Microsoft: "ODBC Driver 17 for SQL Server"
   URL: https://go.microsoft.com/fwlink/?linkid=2168524
2. Ejecutar el instalador → siguiente → siguiente → instalar

### Paso 4 — Instalar las dependencias Python
Abrir cmd en la carpeta del programa y ejecutar:
```
cd C:\FEVRIPS\programa
pip install -r requirements.txt
```

### Paso 5 — Configurar el archivo config.py
Abrir `config.py` con el Bloc de notas o cualquier editor y completar
TODOS los campos marcados con **TODO**:

```python
# Datos de conexión a SQL Server
DB["server"]   = "192.168.1.10"      # IP del servidor SQL
DB["username"] = "conexion"           # Usuario que ya existe en la BD
DB["password"] = "la_contraseña"

# Credenciales SISPRO del representante legal
SISPRO["numero_documento"] = "12345678"
SISPRO["clave"]            = "la_clave_de_miseguridadsocial"
SISPRO["nit"]              = "800123456"

# Datos de la IPS
IPS["nit"]           = "800123456-7"
IPS["nombre"]        = "IPS EJEMPLO S.A.S."
IPS["cod_prestador"] = "110010000000"   # Código REPS habilitación
IPS["cod_municipio"] = "11001"          # Código DIVIPOLA

# Ruta donde el software de facturación guarda los XML de la DIAN
RUTAS["xml_facturas"] = "C:/FacturacionElectronica/XML/"
```

---

## PARTE 4 — Probar y ejecutar

### Prueba de conexión (sin enviar nada)
```
cd C:\FEVRIPS\programa
python main.py --test-conexion
```
Debe mostrar:
```
  ✓ SQL Server OK — 1234 facturas en GCEFACTURA
  ✓ MUV local OK — Login exitoso
```

### Generar JSON sin enviar (para revisar antes de enviar real)
```
python main.py --solo-generar --desde 2026-04-01 --hasta 2026-04-15
```
Los JSON se guardan en `C:\FEVRIPS\json_generados\`
Revisar que tengan la estructura correcta antes de enviar.

### Enviar una sola factura de prueba
```
python main.py --factura FA-001234
```

### Enviar todas las facturas de un período
```
python main.py --desde 2026-04-01 --hasta 2026-04-30
```

### Ver facturas rechazadas
```
python main.py --devueltas
```

### Ver resumen de todos los envíos
```
python main.py --resumen
```

---

## PARTE 5 — Campos TODO pendientes de completar en el código

Estos campos requieren información que debe confirmar la IPS.
Están marcados con `# TODO` en el código:

| Archivo | Campo | Qué confirmar |
|---|---|---|
| `config.py` | `cod_prestador` | Código habilitación REPS de la IPS |
| `config.py` | `xml_facturas` | Ruta donde el facturador guarda los XML DIAN |
| `construir_json.py` | `modalidadGrupoServicioTecSal` | Modalidades que usa esta IPS |
| `construir_json.py` | `finalidadTecnologiaSalud` | Finalidades por tipo de consulta |
| `construir_json.py` | `causaMotivoAtencion` | Causas de atención configuradas |
| `construir_json.py` | `conceptoRecaudo` | Concepto de recaudo por aseguradora |
| `construir_json.py` | Doc médico tratante | Cómo obtenerlo de la BD SIGO |
| `db_queries.py` | Join medicamentos-factura | Confirmar relación GCEFACTSERV→HC |
| `db_queries.py` | Hospitalizaciones | Confirmar código `hctipoHis` |

---

## NOTAS IMPORTANTES

1. **NO instalar producción y pruebas en el mismo servidor** — el MUV no
   permite los dos ambientes al mismo tiempo.

2. **Hacer cargas dosificadas** — el Ministerio recomienda no enviar
   lotes masivos en horas pico. Programar los envíos en la noche.

3. **Los XML de la DIAN son obligatorios** — sin el `xmlFevFile` en Base64
   el MUV rechazará la factura. Verificar con el área de facturación
   dónde los guarda el software actual.

4. **Actualizar el MUV cuando el Ministerio publique nuevas versiones** —
   seguir el micrositio de SISPRO. Hay que desinstalar la versión anterior
   antes de instalar la nueva.

5. **Soporte del Ministerio**:
   - Correo: Soporte-fev-rips@Minsalud.gov.co
   - Bogotá: (601) 330 5043
   - Nacional: 018000960020
   - Lunes a viernes 7am-6pm / Sábados 8am-1pm
