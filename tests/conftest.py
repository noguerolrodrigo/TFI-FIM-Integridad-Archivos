import json
import os
from types import SimpleNamespace

import pytest

import boveda
import monitor_fim
import pendientes
from hashes import get_sha256
from metadatos import leer_owner_y_permisos


class EntornoMonitor:
    """Directorio vigilado, bóveda y cuarentena temporales, con la BD reemplazada por memoria."""

    def __init__(self):
        self.directorio = "./directorio_prueba"
        self.baseline = {}   # ruta -> {hash, permisos, owner}, hace de baseline_vigente
        self.eventos = []    # lo que el monitor habría insertado en la BD
        self.bd_caida = False
        os.makedirs(self.directorio)
        os.makedirs(monitor_fim.DIRECTORIO_CUARENTENA)

    def ruta(self, nombre):
        return f"{self.directorio}/{nombre}"

    def crear_en_baseline(self, nombre, contenido, modo=0o644):
        """Crea el archivo, lo respalda en la bóveda y lo anota en la baseline."""
        ruta = self.ruta(nombre)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "wb") as f:
            f.write(contenido)
        os.chmod(ruta, modo)
        boveda.respaldar(ruta)
        owner, permisos = leer_owner_y_permisos(ruta)
        self.baseline[ruta] = {"hash": get_sha256(ruta), "permisos": permisos, "owner": owner}
        return ruta

    def hash_baseline(self, ruta):
        return self.baseline[ruta]["hash"]

    # Los eventos que manda watchdog, simulados

    def evento_modificado(self, ruta):
        monitor_fim.FIMEventHandler().on_modified(SimpleNamespace(is_directory=False, src_path=ruta))

    def evento_creado(self, ruta):
        monitor_fim.FIMEventHandler().on_created(SimpleNamespace(is_directory=False, src_path=ruta))

    def evento_eliminado(self, ruta, es_directorio=False):
        monitor_fim.FIMEventHandler().on_deleted(SimpleNamespace(is_directory=es_directorio, src_path=ruta))

    def evento_movido(self, origen, destino, es_directorio=False):
        monitor_fim.FIMEventHandler().on_moved(
            SimpleNamespace(is_directory=es_directorio, src_path=origen, dest_path=destino))

    def tipos_de_evento(self):
        return [e["evento"] for e in self.eventos]

    def obtener_baseline(self, ruta):
        if self.bd_caida:
            raise ConnectionError("BD caída (simulada)")
        return self.baseline.get(ruta)

    def rutas_de_la_baseline(self):
        if self.bd_caida:
            raise ConnectionError("BD caída (simulada)")
        return sorted(self.baseline)

    def pendientes(self):
        """Devuelve los eventos del log local de pendientes."""
        if not os.path.exists(pendientes.ARCHIVO_PENDIENTES):
            return []
        with open(pendientes.ARCHIVO_PENDIENTES, encoding="utf-8") as f:
            return [json.loads(linea) for linea in f]

    def registrar(self, nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff="",
                  hash_anterior=None, ruta_cuarentena=None):
        self.eventos.append({
            "nombre_archivo": nombre_archivo, "ruta_completa": ruta_completa, "hash_sha256": hash_sha256,
            "evento": evento, "detalles_diff": detalles_diff, "hash_anterior": hash_anterior,
            "ruta_cuarentena": ruta_cuarentena,
        })


@pytest.fixture
def entorno_monitor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entorno = EntornoMonitor()
    monkeypatch.setattr(monitor_fim, "obtener_baseline", entorno.obtener_baseline)
    monkeypatch.setattr(monitor_fim, "rutas_de_la_baseline", entorno.rutas_de_la_baseline)
    monkeypatch.setattr(monitor_fim, "log_to_db", entorno.registrar)
    return entorno
