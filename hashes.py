import hashlib

def get_sha256(filepath):
    """Calcula el hash SHA-256 de un archivo leyéndolo en bloques. Devuelve None si no se puede leer."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None
