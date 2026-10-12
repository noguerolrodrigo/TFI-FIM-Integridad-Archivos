import hashlib

from hashes import get_sha256


def test_coincide_con_hashlib_en_un_archivo_mas_grande_que_un_bloque(tmp_path):
    archivo = tmp_path / "grande.bin"
    contenido = bytes(range(256)) * 100  # 25600 bytes: varios bloques de 4096
    archivo.write_bytes(contenido)

    assert get_sha256(str(archivo)) == hashlib.sha256(contenido).hexdigest()


def test_hash_conocido_del_archivo_vacio(tmp_path):
    archivo = tmp_path / "vacio.txt"
    archivo.write_bytes(b"")

    assert get_sha256(str(archivo)) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_devuelve_none_si_el_archivo_no_existe(tmp_path):
    assert get_sha256(str(tmp_path / "no_existe")) is None
