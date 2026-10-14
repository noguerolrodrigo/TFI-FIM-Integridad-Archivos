import json
import os
from types import SimpleNamespace

import pytest

import boveda
import config
import monitor_fim
import notificador
from hashes import get_sha256
from metadatos import leer_owner_y_permisos


class EntornoMonitor:
    """Directorio vigilado, bóveda y cuarentena temporales, con la BD reemplazada por memoria."""

    def __init__(self):
        self.directorio = config.RUTAS_MONITOREADAS[0]
        self.baseline = {}   # ruta -> {hash, permisos, owner}, hace de baseline_vigente
        self.eventos = []    # lo que el monitor habría insertado en la BD
        self.bd_caida = False
        self.avisos = []     # lo que el monitor le habría mandado a n8n
        self.ventanas = []   # (id, ruta) de las ventanas de mantenimiento abiertas
        self.ejecuciones = []   # (decision_id, resultado, detalle) que habría registrado el monitor
        self.versiones = 0
        os.makedirs(self.directorio)
        os.makedirs(config.DIRECTORIO_CUARENTENA)

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

    def decision(self, evento_id, decision, decidido_por="rodrigo", canal="telegram", decision_id=1):
        """Arma la decisión tal como la devuelve decisiones_pendientes()."""
        evento = next(e for e in self.eventos if e["id"] == evento_id)
        owner, permisos = evento["owner_permisos"]
        return {"id": decision_id, "decision": decision, "decidido_por": decidido_por, "canal": canal,
                "evento_id": evento_id, "evento": evento["evento"], "ruta": evento["ruta_completa"],
                "hash": evento["hash_sha256"], "permisos": permisos, "owner": owner,
                "ruta_cuarentena": evento["ruta_cuarentena"]}

    def actualizar_archivo(self, ruta, motivo):
        """Hace de generar_baseline.actualizar_archivo: la baseline nueva solo cambia este archivo."""
        self.versiones += 1
        if os.path.isfile(ruta):
            owner, permisos = leer_owner_y_permisos(ruta)
            self.baseline[ruta] = {"hash": get_sha256(ruta), "permisos": permisos, "owner": owner}
            boveda.respaldar(ruta)
        else:
            self.baseline.pop(ruta, None)
            boveda.quitar(ruta)
        return self.versiones

    def registrar_ejecucion(self, decision_id, resultado, detalle):
        self.ejecuciones.append((decision_id, resultado, detalle))

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
        if not os.path.exists(config.ARCHIVO_PENDIENTES):
            return []
        with open(config.ARCHIVO_PENDIENTES, encoding="utf-8") as f:
            return [json.loads(linea) for linea in f]

    def registrar(self, nombre_archivo, ruta_completa, hash_sha256, evento, detalles_diff="",
                  hash_anterior=None, ruta_cuarentena=None):
        self.eventos.append({
            "id": len(self.eventos) + 1,
            "nombre_archivo": nombre_archivo, "ruta_completa": ruta_completa, "hash_sha256": hash_sha256,
            "evento": evento, "detalles_diff": detalles_diff, "hash_anterior": hash_anterior,
            "ruta_cuarentena": ruta_cuarentena,
            # lo que log_to_db lee del disco al registrar
            "owner_permisos": leer_owner_y_permisos(ruta_completa),
        })
        return len(self.eventos)


@pytest.fixture(autouse=True)
def configuracion_aislada(tmp_path, monkeypatch):
    """Todos los tests trabajan en una carpeta temporal: nunca tocan la bóveda ni la cuarentena reales."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "RUTAS_MONITOREADAS", [str(tmp_path / "directorio_prueba")])
    monkeypatch.setattr(config, "DIRECTORIO_BOVEDA", str(tmp_path / "boveda"))
    monkeypatch.setattr(config, "DIRECTORIO_CUARENTENA", str(tmp_path / "cuarentena"))
    monkeypatch.setattr(config, "ARCHIVO_PENDIENTES", str(tmp_path / "logs" / "eventos_pendientes.jsonl"))
    monkeypatch.setattr(config, "PATRONES_IGNORADOS", ["*.swp", "*.swo", "*.swx", "*~", "*.tmp"])
    monkeypatch.setattr(config, "MODO_RESTAURACION", "automatica")
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", "")
    monitor_fim.avisados.clear()
    monitor_fim.decisiones_ejecutadas.clear()


@pytest.fixture
def entorno_monitor(monkeypatch):
    entorno = EntornoMonitor()
    monkeypatch.setattr(monitor_fim, "obtener_baseline", entorno.obtener_baseline)
    monkeypatch.setattr(monitor_fim, "rutas_de_la_baseline", entorno.rutas_de_la_baseline)
    monkeypatch.setattr(monitor_fim, "log_to_db", entorno.registrar)
    monkeypatch.setattr(monitor_fim, "ventanas_vigentes", lambda: list(entorno.ventanas))
    monkeypatch.setattr(monitor_fim, "registrar_ejecucion", entorno.registrar_ejecucion)
    monkeypatch.setattr(monitor_fim.generar_baseline, "actualizar_archivo", entorno.actualizar_archivo)
    monkeypatch.setattr(notificador, "notificar", entorno.avisos.append)
    return entorno
