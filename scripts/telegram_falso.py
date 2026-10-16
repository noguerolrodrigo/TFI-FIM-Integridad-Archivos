"""Telegram simulado para las pruebas: responde como la Bot API y no manda nada a internet.

Cada pedido queda como una línea JSON en el archivo indicado (método y datos), así las pruebas
pueden ver qué habría recibido el celular.

Uso: python3 scripts/telegram_falso.py <puerto> <archivo.jsonl>
"""
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

ARCHIVO = sys.argv[2]
contador = 0


class Manejador(BaseHTTPRequestHandler):
    def do_POST(self):
        global contador
        contador += 1
        cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        if "json" in self.headers.get("Content-Type", ""):
            datos = json.loads(cuerpo or "{}")
        else:
            datos = dict(urllib.parse.parse_qsl(cuerpo))
        metodo = self.path.rsplit("/", 1)[-1]
        with open(ARCHIVO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"metodo": metodo, "datos": datos}, ensure_ascii=False) + "\n")

        if metodo == "answerCallbackQuery":
            resultado = True
        else:
            resultado = {"message_id": contador, "date": 0, "text": datos.get("text", ""),
                         "chat": {"id": datos.get("chat_id"), "type": "private"}}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "result": resultado}).encode("utf-8"))

    do_GET = do_POST

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", int(sys.argv[1])), Manejador).serve_forever()
