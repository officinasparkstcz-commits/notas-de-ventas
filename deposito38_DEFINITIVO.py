"""
deposito38_DEFINITIVO.py

Avvia esclusivamente deposito37.py e applica i permessi richiesti senza
modificare la grafica nuova, le immagini integrate, le tabelle o Supabase.

Tenere questo file nella stessa cartella di deposito37.py.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


QUESTO_FILE = Path(__file__).resolve()


def _trova_file_base() -> Path:
    """Usa soltanto deposito37.py e rifiuta qualsiasi versione diversa."""
    file_base = QUESTO_FILE.parent / "deposito37.py"

    if not file_base.is_file():
        raise FileNotFoundError(
            "Manca deposito37.py nella stessa cartella di "
            "deposito38_DEFINITIVO.py."
        )

    return file_base.resolve()

BLOCCO_PERMESSI = r'''

# =========================================================
# PERMESSI DEPOSITO38
# =========================================================
def _nome_utente_normalizzato():
    """Normalizza il nome indicato nei secrets, tollerando spazi e accenti."""
    import re as _re
    import unicodedata as _unicodedata

    valore = str(usuario_actual() or "").strip().lower()
    valore = "".join(
        carattere
        for carattere in _unicodedata.normalize("NFKD", valore)
        if not _unicodedata.combining(carattere)
    )
    return _re.sub(r"[^a-z0-9]+", "", valore)


def utente_toni():
    nome = _nome_utente_normalizzato()
    return nome in {"toni", "tony"} or nome.startswith("toni")


def sede_utente():
    nome = _nome_utente_normalizzato()
    if nome in {"santacruz", "santacruiz"} or "santacruz" in nome:
        return "SANTACRUZ"
    if nome == "tarija" or "tarija" in nome:
        return "TARIJA"
    if nome == "camioncito" or "camioncito" in nome:
        return "CAMIONCITO"
    return None


def puede_editar_sede(sede):
    """Toni modifica tutte le note; gli altri soltanto la propria sede."""
    sede = str(sede or "").strip().upper()
    return utente_toni() or sede_utente() == sede


def aplicar_interfaz_por_usuario():
    """Nasconde i comandi tecnici Streamlit ai tre utenti di sede."""
    if utente_toni():
        return

    st.markdown(
        """
        <style>
        #MainMenu,
        footer,
        header[data-testid="stHeader"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"],
        [data-testid="stDecoration"],
        [data-testid="stHeaderActionElements"],
        [data-testid="stMainMenu"],
        [data-testid="stToolbarActions"],
        [data-testid="stAppToolbar"],
        .stAppToolbar,
        [data-testid="manage-app-button"],
        [data-testid="stManageAppButton"],
        [data-testid="stViewerBadge"],
        [data-testid*="ViewerBadge"],
        [data-testid*="viewerBadge"],
        [data-testid*="manage-app"],
        [data-testid*="ManageApp"],
        button[aria-label="Manage app"],
        a[aria-label="Manage app"],
        .viewerBadge_container__1QSob,
        .viewerBadge_link__1S137 {
            display: none !important;
            visibility: hidden !important;
            width: 0 !important;
            height: 0 !important;
            min-width: 0 !important;
            min-height: 0 !important;
            overflow: hidden !important;
            pointer-events: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
'''


DOPO_LOGIN = r'''

# Applica la visualizzazione riservata subito dopo il login.
aplicar_interfaz_por_usuario()
'''



def _verifica_versione_grafica(sorgente: str) -> None:
    """Blocca l'avvio se deposito37.py non è la versione grafica nuova."""
    marcatori_richiesti = (
        "GNV_VECTOR_URI",
        "TITLE_BOX_VECTOR_URI",
        "SANTA_CRUZ_BUTTON_URI",
        "CAMIONCITO_BUTTON_URI",
        "DEPOSITO_PRIMER_VECTOR_URI",
        "def editor_coloreado_aggrid",
        "deposito-vectores-linea",
    )
    mancanti = [
        marcatore
        for marcatore in marcatori_richiesti
        if marcatore not in sorgente
    ]
    if mancanti:
        raise RuntimeError(
            "deposito37.py non è la versione grafica nuova. "
            "Marcatori mancanti: " + ", ".join(mancanti)
        )

def _inserisci_permessi(sorgente: str) -> str:
    """Inserisce le funzioni dei permessi prima della schermata di login."""
    marcatore = "\ndef exigir_login():"
    if marcatore not in sorgente:
        raise RuntimeError("Non trovo la funzione exigir_login nel file base.")

    return sorgente.replace(
        marcatore,
        BLOCCO_PERMESSI + marcatore,
        1,
    )


def _proteggi_funzioni_database(sorgente: str) -> str:
    """Blocca anche lato logico ogni scrittura su una sede non autorizzata."""
    sostituzioni = {
        "def crear_nota(sede):\n": (
            "def crear_nota(sede):\n"
            "    if not puede_editar_sede(sede):\n"
            "        st.error(\"Non hai il permesso di aggiungere note in questa sede.\")\n"
            "        return False\n"
        ),
        "def guardar_cambios_notas(sede, anterior, editado):\n": (
            "def guardar_cambios_notas(sede, anterior, editado):\n"
            "    if not puede_editar_sede(sede):\n"
            "        return 0\n"
        ),
    }

    for originale, nuovo in sostituzioni.items():
        if originale in sorgente:
            sorgente = sorgente.replace(originale, nuovo, 1)

    # Alcune versioni hanno eliminar_notas(ids), altre possono già avere sede.
    if "def eliminar_notas(ids):\n" in sorgente:
        sorgente = sorgente.replace(
            "def eliminar_notas(ids):\n",
            "def eliminar_notas(ids, sede=None):\n"
            "    if sede is not None and not puede_editar_sede(sede):\n"
            "        st.error(\"Non hai il permesso di eliminare note in questa sede.\")\n"
            "        return False\n",
            1,
        )

    # Passa la sede alle chiamate di eliminazione presenti nel ciclo delle note.
    sorgente = re.sub(
        r"eliminar_notas\(ids_eliminar\)",
        "eliminar_notas(ids_eliminar, tid)",
        sorgente,
    )

    return sorgente


def _aggiungi_variabile_permesso(sorgente: str) -> str:
    """Calcola il permesso una volta per ogni tabella."""
    schema = r'(?m)^(\s*)tid = t\["id"\]\s*$'

    def sostituisci(corrispondenza: re.Match[str]) -> str:
        indentazione = corrispondenza.group(1)
        return (
            f'{indentazione}tid = t["id"]\n'
            f"{indentazione}puede_editar = puede_editar_sede(tid)"
        )

    sorgente, numero = re.subn(schema, sostituisci, sorgente, count=1)
    if numero == 0:
        raise RuntimeError("Non trovo il ciclo delle tre tabelle nel file base.")
    return sorgente


def _disabilita_pulsanti_note(sorgente: str) -> str:
    """Disabilita Aggiungi ed Elimina nelle tabelle visibili in sola lettura."""
    sorgente = re.sub(
        r'st\.button\(\s*"➕ Añadir Nota",\s*key=f"add_\{tid\}"\s*\)',
        'st.button("➕ Añadir Nota", key=f"add_{tid}", disabled=not puede_editar)',
        sorgente,
    )
    sorgente = re.sub(
        r'st\.button\(\s*"🗑️ Eliminar Seleccionadas",\s*key=f"del_\{tid\}"\s*\)',
        'st.button("🗑️ Eliminar Seleccionadas", key=f"del_{tid}", disabled=not puede_editar)',
        sorgente,
    )
    return sorgente


def _rendi_editor_sola_lettura(sorgente: str) -> str:
    """Gestisce sia st.data_editor sia la variante AgGrid usata in altre revisioni."""
    # st.data_editor delle note. L'editor dell'inventario non viene toccato.
    sorgente = re.sub(
        r'(key=f"editor_\{tid\}"\s*,?\s*)(\n\s*\))',
        r'key=f"editor_{tid}",\n                    disabled=not puede_editar,\2',
        sorgente,
        count=1,
    )

    # AgGrid: limita la modifica nella funzione che riceve la sede.
    inizio = sorgente.find("def editor_coloreado_aggrid(dataframe, sede, key):")
    if inizio != -1:
        fine = sorgente.find("\n\ndef ", inizio + 10)
        if fine == -1:
            fine = len(sorgente)
        blocco = sorgente[inizio:fine]
        blocco = blocco.replace(
            "editable=True,",
            "editable=puede_editar_sede(sede),",
        )
        blocco = blocco.replace(
            "singleClickEdit=True,",
            "singleClickEdit=puede_editar_sede(sede),",
        )
        sorgente = sorgente[:inizio] + blocco + sorgente[fine:]

    return sorgente


def _applica_interfaccia_dopo_login(sorgente: str) -> str:
    """Inserisce il CSS dopo la chiamata reale a exigir_login()."""
    chiamata = re.compile(r"(?m)^exigir_login\(\)\s*$")
    sorgente, numero = chiamata.subn(
        "exigir_login()" + DOPO_LOGIN,
        sorgente,
        count=1,
    )
    if numero == 0:
        raise RuntimeError("Non trovo la chiamata exigir_login() nel file base.")
    return sorgente


def _prepara_sorgente(sorgente: str) -> str:
    _verifica_versione_grafica(sorgente)
    sorgente = _inserisci_permessi(sorgente)
    sorgente = _proteggi_funzioni_database(sorgente)
    sorgente = _aggiungi_variabile_permesso(sorgente)
    sorgente = _disabilita_pulsanti_note(sorgente)
    sorgente = _rendi_editor_sola_lettura(sorgente)
    sorgente = _applica_interfaccia_dopo_login(sorgente)
    return sorgente


def _avvia() -> None:
    file_base = _trova_file_base()
    sorgente = file_base.read_text(encoding="utf-8-sig")
    sorgente_modificato = _prepara_sorgente(sorgente)

    # Il codice viene compilato con il nome del file originale, così eventuali
    # percorsi relativi e messaggi di errore restano comprensibili.
    codice = compile(sorgente_modificato, str(file_base), "exec")
    ambiente = globals()
    ambiente["__file__"] = str(file_base)
    ambiente["__name__"] = "__main__"
    exec(codice, ambiente, ambiente)


if __name__ == "__main__":
    _avvia()
