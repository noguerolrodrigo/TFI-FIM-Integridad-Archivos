import os
import subprocess
import sys
import threading

import boveda
import config

# restaurar.py corre en otro proceso que el monitor. Mientras restaura, su temporal existe en el
# directorio vigilado y el monitor (que ya no ignora nada por el prefijo) no tiene que tomarlo
# por un archivo nuevo: tiene que esperar a que el otro proceso termine.

# Hace de restaurar.py: toma el candado, crea su temporal, avisa, y cuando le escriben una línea
# lo renombra sobre el original (como hace la restauración) y termina.
OTRO_PROCESO = """
import os, sys
sys.path.insert(0, sys.argv[1])
import config
config.ARCHIVO_PENDIENTES = sys.argv[2]
import monitor_fim
temporal, original = sys.argv[3], sys.argv[4]
with monitor_fim.exclusion():
    with open(temporal, "w") as f:
        f.write("estado cero\\n")
    print("temporal creado", flush=True)
    sys.stdin.readline()
    os.replace(temporal, original)
"""


def test_el_temporal_de_una_restauracion_en_otro_proceso_no_se_registra_como_creado(entorno_monitor):
    ruta = entorno_monitor.crear_en_baseline("config.txt", b"estado cero\n")
    temporal = entorno_monitor.ruta(boveda.PREFIJO_TEMPORAL + "a1b2c3d4")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    otro = subprocess.Popen([sys.executable, "-c", OTRO_PROCESO, raiz, config.ARCHIVO_PENDIENTES, temporal, ruta],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert otro.stdout.readline().strip() == "temporal creado"
        assert os.path.exists(temporal)

        # Al monitor le llega el aviso de inotify mientras el temporal todavía existe
        aviso = threading.Thread(target=entorno_monitor.evento_creado, args=(temporal,))
        aviso.start()
        aviso.join(timeout=1)
        esperaba = aviso.is_alive()

        otro.stdin.write("seguir\n")
        otro.stdin.flush()
        aviso.join(timeout=10)
        assert otro.wait(timeout=10) == 0
    finally:
        otro.kill()

    assert esperaba, "el monitor procesó el temporal sin esperar al otro proceso"
    assert entorno_monitor.eventos == []
    assert os.listdir("./cuarentena") == []
    assert os.listdir(entorno_monitor.directorio) == ["config.txt"]
