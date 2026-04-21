# ============================================================
#  LOGGER — Configuración de logs para la aplicación
# ============================================================

import logging
import sys
from pathlib import Path
from datetime import datetime
from config import RUTAS

Path(RUTAS["logs"]).mkdir(parents=True, exist_ok=True)

_nombre_log = f"fevrips_{datetime.now().strftime('%Y%m%d')}.log"
_ruta_log = Path(RUTAS["logs"]) / _nombre_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_ruta_log, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

log = logging.getLogger("fevrips")
