#!/usr/bin/env bash
#
# Importa y publica los workflows del FIM en n8n.   Uso: ./n8n/importar_workflows.sh
#
# Hay que correrlo con n8n DETENIDO y después de crear en la UI las credenciales "Telegram FIM" y
# "Postgres FIM (fim_n8n)" (ver n8n/README.md). Los JSON del repo no tienen ids de credenciales:
# este script busca esas credenciales por nombre y les pone el id que tienen en esta instalación.
#
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATOS_N8N="${DATOS_N8N:-$HOME/n8n_fim}"
PUERTO="${PUERTO:-5678}"
BASE_SQLITE="$DATOS_N8N/.n8n/database.sqlite"

export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use 24 >/dev/null
export N8N_USER_FOLDER="$DATOS_N8N"

if curl -s -o /dev/null "http://localhost:$PUERTO/healthz"; then
    echo "[!] n8n está corriendo en el puerto $PUERTO. Detenelo (Ctrl+C) y volvé a ejecutar este script." >&2
    exit 1
fi
if [ ! -f "$BASE_SQLITE" ]; then
    echo "[!] No encuentro los datos de n8n en $DATOS_N8N. ¿Ya lo arrancaste una vez con iniciar_n8n.sh?" >&2
    exit 1
fi

TEMPORAL="$(mktemp -d)"
trap 'rm -rf "$TEMPORAL"' EXIT

# Pone los ids de las credenciales (solo lee id, nombre y tipo; nunca los datos cifrados)
python3 - "$BASE_SQLITE" "$PROYECTO/n8n" "$TEMPORAL" <<'PY'
import json, pathlib, sqlite3, sys
base, origen, destino = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
conexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
credenciales = {(nombre, tipo): id_ for id_, nombre, tipo in
                conexion.execute("SELECT id, name, type FROM credentials_entity")}
faltan = set()
for archivo in sorted(origen.glob("*.json")):
    workflow = json.loads(archivo.read_text(encoding="utf-8"))
    for nodo in workflow["nodes"]:
        for tipo, credencial in nodo.get("credentials", {}).items():
            clave = (credencial["name"], tipo)
            if clave in credenciales:
                credencial["id"] = credenciales[clave]
            else:
                faltan.add(clave)
    (destino / archivo.name).write_text(json.dumps(workflow, ensure_ascii=False), encoding="utf-8")
    print(workflow["id"], archivo.name)
if faltan:
    sys.exit("[!] Faltan credenciales en n8n: " + ", ".join(f'"{n}" ({t})' for n, t in sorted(faltan)))
PY
python3 - "$TEMPORAL" > "$TEMPORAL/ids.txt" <<'PY'
import json, pathlib, sys
for archivo in sorted(pathlib.Path(sys.argv[1]).glob("*.json")):
    print(json.loads(archivo.read_text(encoding="utf-8"))["id"], archivo.name)
PY

while read -r id archivo; do
    echo "[*] Importando $archivo"
    n8n import:workflow --input="$TEMPORAL/$archivo" 2>&1 | grep -v -i 'deprecat\|^$' || true
    n8n publish:workflow --id="$id" 2>&1 | grep -v -i 'deprecat\|^$' || true
done < "$TEMPORAL/ids.txt"

echo "[*] Listo. Arrancá n8n con ./n8n/iniciar_n8n.sh"
