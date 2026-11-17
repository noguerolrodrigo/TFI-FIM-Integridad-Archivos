#!/usr/bin/python3
"""Exporta el informe a PDF con LibreOffice, actualizando antes los índices.

Uso (desde la raíz del proyecto, con el Python del sistema, que es el que trae el módulo uno):
    /usr/bin/python3 docs/informe/exportar_pdf.py
    /usr/bin/python3 docs/informe/exportar_pdf.py entrada.docx salida.pdf

Por defecto lee docs/informe/TFI_Noguerol_2026.docx y escribe docs/informe/vista_previa_TFI.pdf
(los vista_previa_*.pdf están en .gitignore).

armar_docx.py deja el índice general, el de figuras y el de tablas como campos, sin números de
página: hay que actualizarlos. Convertir con "soffice --convert-to pdf" no los actualiza. Este
script abre el documento en un LibreOffice sin ventana, actualiza todos los índices (dos veces,
porque al llenarse pueden correr las páginas) y recién entonces exporta.

Requiere LibreOffice y python3-uno (en Ubuntu: sudo apt install libreoffice-writer python3-uno).
No usa el entorno virtual del proyecto. El PDF es una vista previa: la paginación de Word o de
Google Docs puede diferir de la de LibreOffice.
"""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

AQUI = os.path.dirname(os.path.abspath(__file__))
PUERTO = 2002


def propiedad(nombre, valor):
    p = PropertyValue()
    p.Name = nombre
    p.Value = valor
    return p


def exportar(entrada, salida):
    proceso = subprocess.Popen(
        ["soffice", "--headless", "--norestore", f"--accept=socket,host=localhost,port={PUERTO};urp;"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        contexto = None
        for _ in range(60):   # LibreOffice tarda unos segundos en aceptar conexiones
            try:
                contexto = resolver.resolve(
                    f"uno:socket,host=localhost,port={PUERTO};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        if contexto is None:
            sys.exit("[!] No se pudo conectar con LibreOffice.")
        escritorio = contexto.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", contexto)
        documento = escritorio.loadComponentFromURL(uno.systemPathToFileUrl(entrada), "_blank", 0,
                                                    (propiedad("Hidden", True),))
        indices = documento.getDocumentIndexes()
        cantidad = indices.getCount()
        for _ in range(2):
            for i in range(cantidad):
                indices.getByIndex(i).update()
        documento.storeToURL(uno.systemPathToFileUrl(salida), (propiedad("FilterName", "writer_pdf_Export"),))
        documento.close(True)
        return cantidad
    finally:
        proceso.terminate()


if __name__ == "__main__":
    entrada = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(AQUI, "TFI_Noguerol_2026.docx")
    salida = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(AQUI, "vista_previa_TFI.pdf")
    cantidad = exportar(entrada, salida)
    print(f"[*] {cantidad} índice(s) actualizado(s). PDF en {salida}")
