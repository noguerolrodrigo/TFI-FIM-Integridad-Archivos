import getpass
import os
import sys

import bd
import monitor_fim

# Restaura un archivo desde la bóveda con aprobación de una persona.
# Es el paso manual del modo MODO_RESTAURACION=aprobacion (después lo va a disparar n8n).
#
# Uso: python restaurar.py <ruta del archivo>

MENSAJES = {
    monitor_fim.RESTAURADO: "[+] Restaurado según la baseline.",
    monitor_fim.SIN_CAMBIOS: "[*] El archivo ya coincide con la baseline: no había nada que restaurar.",
    monitor_fim.CREADO: "[-] El archivo no está en la baseline: no se puede restaurar.",
    monitor_fim.NO_RESTAURADO: "[-] No se pudo restaurar. Revisá el motivo en los mensajes de arriba.",
    monitor_fim.SIN_VERIFICAR: "[-] No se pudo verificar contra la baseline. Revisá que PostgreSQL esté levantado.",
}

def restaurar(ruta):
    """Restaura el archivo dejando registrado quién lo aprobó. Devuelve 0 si quedó como en la baseline."""
    resultado = monitor_fim.procesar(os.path.abspath(ruta), aprobado_por=getpass.getuser())
    print(MENSAJES[resultado])
    return 0 if resultado in (monitor_fim.RESTAURADO, monitor_fim.SIN_CAMBIOS) else 1

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python restaurar.py <ruta del archivo>")
        sys.exit(2)
    codigo = restaurar(sys.argv[1])
    bd.cerrar()
    sys.exit(codigo)
