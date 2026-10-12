import os
import bd
import boveda
from hashes import get_sha256
from metadatos import leer_owner_y_permisos

# Directorio de prueba
DIRECTORIO_A_MONITOREAR = "./directorio_prueba"

def generar_baseline():
    print(f"[*] Iniciando escaneo de baseline en: {DIRECTORIO_A_MONITOREAR}")
    
    # Si la carpeta no existe, la creamos y le metemos un archivo
    if not os.path.exists(DIRECTORIO_A_MONITOREAR):
        os.makedirs(DIRECTORIO_A_MONITOREAR)
        with open(os.path.join(DIRECTORIO_A_MONITOREAR, "config_test.txt"), "w") as f:
            f.write("Archivo de configuración inicial. Estado cero.")

    try:
        # Toda la baseline va en una sola transacción: o entra completa o no entra
        conn = bd.conectar()
        cursor = conn.cursor()
        archivos_procesados = 0
        rutas_vigentes = []

        # Cada corrida es una versión nueva: la vigente es siempre la más alta
        cursor.execute("SELECT COALESCE(MAX(version_baseline), 0) + 1 FROM registros_archivos WHERE evento = 'BASELINE'")
        version = cursor.fetchone()[0]
        print(f"[*] Versión de baseline: {version}")

        for root, dirs, files in os.walk(DIRECTORIO_A_MONITOREAR):
            for file in files:
                ruta_completa = os.path.join(root, file)
                hash_archivo = get_sha256(ruta_completa)
                
                if hash_archivo:
                    owner, permisos = leer_owner_y_permisos(ruta_completa)

                    query = """
                        INSERT INTO registros_archivos 
                        (nombre_archivo, ruta_completa, hash_sha256, evento, owner_archivo, permisos, version_baseline) 
                        VALUES (%s, %s, %s, 'BASELINE', %s, %s, %s)
                    """
                    cursor.execute(query, (file, ruta_completa, hash_archivo, owner, permisos, version))

                    # Copia confiable en disco: de acá restaura el monitor
                    boveda.respaldar(ruta_completa)
                    rutas_vigentes.append(ruta_completa)
                    archivos_procesados += 1
                    print(f"[+] Registrado: {file} -> Hash: {hash_archivo[:15]}...")

        conn.commit()
        cursor.close()
        bd.cerrar()

        # La bóveda tiene que reflejar solo la baseline vigente
        borrados = boveda.limpiar_huerfanos(DIRECTORIO_A_MONITOREAR, rutas_vigentes)
        if borrados:
            print(f"[*] Bóveda: {borrados} respaldo(s) de archivos que ya no existen eliminado(s).")

        print(f"\n[*] Baseline versión {version} completada. {archivos_procesados} archivo(s) guardado(s).")

    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    generar_baseline()