import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from intervalos_bootstrap import intervalo_bootstrap


def test_el_intervalo_contiene_a_la_mediana_y_se_repite_con_la_misma_semilla():
    valores = [float(v) for v in range(1, 52)]

    mediana, inferior, superior = intervalo_bootstrap([valores], random.Random(1), remuestras=500)

    assert mediana == 26.0
    assert inferior <= mediana <= superior
    assert (mediana, inferior, superior) == intervalo_bootstrap([valores], random.Random(1), remuestras=500)


def test_una_muestra_constante_da_un_intervalo_de_ancho_cero():
    assert intervalo_bootstrap([[7.0] * 20], random.Random(1), remuestras=200) == (7.0, 7.0, 7.0)


def test_con_estratos_cada_caso_aporta_siempre_su_cantidad_de_valores():
    # Dos casos muy distintos: remuestreando dentro de cada uno, la mediana conjunta queda siempre
    # entre los dos grupos y no puede irse a un extremo
    bajos, altos = [1.0] * 10, [100.0] * 10

    mediana, inferior, superior = intervalo_bootstrap([bajos, altos], random.Random(1), remuestras=200)

    assert (mediana, inferior, superior) == (50.5, 50.5, 50.5)
