import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import config
import notificador


class ServidorFalso:
    """Un n8n de mentira: guarda lo que recibe. Con demora, tarda en contestar."""

    def __init__(self, demora=0):
        recibidos = self.recibidos = []

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self):
                largo = int(self.headers["Content-Length"])
                recibidos.append({"cuerpo": json.loads(self.rfile.read(largo)),
                                  "secreto": self.headers.get("X-FIM-Secreto"),
                                  "ruta": self.path})
                time.sleep(demora)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        self.servidor = HTTPServer(("127.0.0.1", 0), Manejador)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.servidor.server_port}/webhook/fim-evento"

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


@pytest.fixture
def n8n_falso(monkeypatch):
    servidor = ServidorFalso()
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", servidor.url)
    monkeypatch.setattr(config, "N8N_WEBHOOK_SECRETO", "secreto-de-prueba")
    yield servidor
    servidor.cerrar()


def test_manda_solo_el_id_y_el_resultado_con_el_header_secreto(n8n_falso):
    notificador.notificar({"tipo": "evento", "evento_id": 42, "resultado": "RESTAURADO"}).join(5)

    recibido, = n8n_falso.recibidos
    assert recibido["cuerpo"] == {"tipo": "evento", "evento_id": 42, "resultado": "RESTAURADO"}
    assert recibido["secreto"] == "secreto-de-prueba"
    assert recibido["ruta"] == "/webhook/fim-evento"


def test_no_bloquea_aunque_n8n_tarde_en_contestar(monkeypatch):
    lento = ServidorFalso(demora=1.5)
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", lento.url)
    try:
        inicio = time.monotonic()
        hilo = notificador.notificar({"evento_id": 1})
        assert time.monotonic() - inicio < 0.2
        hilo.join(5)
        assert len(lento.recibidos) == 1
    finally:
        lento.cerrar()


def test_si_n8n_no_esta_no_lanza_error(monkeypatch, capsys):
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", "http://127.0.0.1:9/webhook/fim-evento")  # puerto cerrado

    notificador.notificar({"evento_id": 7}).join(5)

    assert "No se pudo avisar a n8n" in capsys.readouterr().out


def test_sin_webhook_configurado_no_manda_nada(monkeypatch):
    monkeypatch.setattr(config, "N8N_WEBHOOK_URL", "")

    assert notificador.notificar({"evento_id": 1}) is None


def test_el_monitor_avisa_con_el_id_del_evento_y_el_resultado(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("intruso\n")

    entorno_monitor.evento_modificado(ruta)

    deteccion = entorno_monitor.eventos[0]
    assert entorno_monitor.avisos == [{"tipo": "evento", "evento_id": deteccion["id"], "resultado": "RESTAURADO"}]


def test_el_monitor_no_avisa_si_no_hubo_cambios(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.avisos == []


def test_en_modo_aprobacion_avisa_que_quedo_pendiente(entorno_monitor, monkeypatch):
    monkeypatch.setattr(config, "MODO_RESTAURACION", "aprobacion")
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    with open(ruta, "a") as f:
        f.write("intruso\n")

    entorno_monitor.evento_modificado(ruta)

    assert entorno_monitor.avisos[0]["resultado"] == "PENDIENTE"
