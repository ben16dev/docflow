"""
Registro central de scripts disponibles en DocFlow.
"""

# ==========================================================
# IMPORTAR MÓDULOS
# ==========================================================

from scripts.pdf import (
    censurar_pdf_por_palabras,
    extraer_paginas_pdf,
    img_a_pdf,
    nuevo_cliente,
    numerar_doc_pdf,
    renombrar_pdfs_indice,
    rotar_paginas_pdf,
    unir_pdfs_expediente,
    unir_pdfs_orden,
    unir_pdfs_por_nombre_dni,
    limpiar_numeracion_pdf,
    optimizar_pdf,
)

from scripts.eml import eml_a_pdf

from scripts.mbox import (
    extraer_con_adjuntos,
    mbox_a_eml,
)

from scripts.metadata import extract_metadata


# ==========================================================
# REGISTRO
# ==========================================================

SCRIPTS = {

    "PDF": {

        "Numeración PDF": numerar_doc_pdf,
        "Extraer páginas PDF": extraer_paginas_pdf,
        "Rotar páginas PDF": rotar_paginas_pdf,
        "Unir PDFs por expediente": unir_pdfs_expediente,
        "Unir PDFs por orden manual": unir_pdfs_orden,
        "Unir PDFs por DNI": unir_pdfs_por_nombre_dni,
        "Renombrar PDFs por índice": renombrar_pdfs_indice,
        "Censurar PDF por palabras": censurar_pdf_por_palabras,
        "Imagen a PDF": img_a_pdf,
        "Nuevo cliente": nuevo_cliente,
        "Limpiar numeración PDF": limpiar_numeracion_pdf,
        "Optimizar PDF": optimizar_pdf,

    },

    "EML": {

        "EML a PDF": eml_a_pdf,

    },

    "MBOX": {

        "MBOX a EML": mbox_a_eml,
        "Extraer con adjuntos": extraer_con_adjuntos,

    }

}


# ==========================================================
# API
# ==========================================================

def get_scripts(tab_name: str):
    """
    Devuelve los scripts disponibles para una pestaña.
    """
    return SCRIPTS.get(tab_name, {})


# ==========================================================
# METADATOS
# ==========================================================

def get_scripts_metadata(tab_name: str):
    """
    Devuelve metadatos de los scripts de una pestaña.
    """

    scripts = SCRIPTS.get(tab_name, {})
    metadata_list = []

    for name, module in scripts.items():

        meta = extract_metadata(module)

        meta["ui_name"] = name
        meta["module"] = module.__name__

        metadata_list.append(meta)

    return metadata_list

