# ui/styles.py
"""
DocFlow Light Indigo Design System — tokens visuales centralizados.

Fuente única de colores, tipografía y espaciados para la interfaz.
Las constantes BTN_* / TOP_BG / FRAME_BG / TITLE_FG se conservan como
aliases legacy para no romper imports de módulos aún no migrados.
"""

# =============================================================================
# COLORES CORPORATIVOS
# =============================================================================

PRIMARY_INDIGO = "#1E3A8A"
PRIMARY_INDIGO_HOVER = "#1D4ED8"

ACCENT_TEAL = "#14B8A6"
ACCENT_TEAL_DARK = "#0F766E"

ACTION_CANCEL = "#C2410C"
ACTION_CANCEL_HOVER = "#9A3412"
ACTION_CANCEL_PRESSED = "#7C2D12"

ACTION_SUCCESS = "#047857"
ACTION_SUCCESS_HOVER = "#065F46"
ACTION_SUCCESS_PRESSED = "#064E3B"

PRIMARY_INDIGO_PRESSED = "#172554"

# =============================================================================
# SUPERFICIES
# =============================================================================

BACKGROUND_APP = "#F8FAFC"
BACKGROUND_PANEL = "#FFFFFF"
BACKGROUND_MUTED = "#F1F5F9"

# =============================================================================
# TEXTO
# =============================================================================

TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#64748B"
TEXT_DISABLED = "#94A3B8"
TEXT_ON_PRIMARY = "#FFFFFF"

# =============================================================================
# BORDES
# =============================================================================

BORDER_DEFAULT = "#CBD5E1"

# =============================================================================
# ESTADOS (feedback de proceso / timer)
# =============================================================================

STATE_IDLE = TEXT_SECONDARY
STATE_RUNNING = PRIMARY_INDIGO_HOVER
STATE_SUCCESS = ACTION_SUCCESS
STATE_ERROR = ACTION_CANCEL
# Ámbar oscuro: distinto de idle, error (coral), success y running.
STATE_CANCELLED = "#B45309"

# =============================================================================
# TIPOGRAFÍA
# Preferencia tipográfica UI. Tk sustituye si la familia no está instalada;
# no se garantiza la misma cara en macOS, Windows y Linux.
# TkFixedFont / Courier son alias genéricos seguros para monoespaciado.
# =============================================================================

FONT_FAMILY_UI = "Segoe UI"
FONT_FAMILY_MONO = "TkFixedFont"

FONT_SIZE_XS = 8
FONT_SIZE_SM = 9
FONT_SIZE_MD = 10
FONT_SIZE_LG = 11
FONT_SIZE_XL = 13


def font_ui(size, *styles):
    """Tupla tipográfica UI: (familia, tamaño[, estilo...])."""
    if styles:
        return (FONT_FAMILY_UI, size) + tuple(styles)
    return (FONT_FAMILY_UI, size)


def font_mono(size, *styles):
    """Tupla tipográfica monoespaciada genérica de Tk."""
    if styles:
        return (FONT_FAMILY_MONO, size) + tuple(styles)
    return (FONT_FAMILY_MONO, size)

# =============================================================================
# ESPACIADOS BÁSICOS
# =============================================================================

SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 20
SPACE_XL = 30

PAGE_PADX = SPACE_XL
SECTION_PADY = SPACE_LG

# =============================================================================
# CABECERA Y NOTEBOOK (navegación)
# =============================================================================

HEADER_BG = BACKGROUND_PANEL
HEADER_BORDER = BORDER_DEFAULT
HEADER_PADY_TOP = SPACE_MD
HEADER_PADY_BOTTOM = SPACE_SM
HEADER_PADX = SPACE_XL

NOTEBOOK_BG = BACKGROUND_APP
TAB_BG = BACKGROUND_MUTED
TAB_FG = TEXT_SECONDARY
TAB_ACTIVE_BG = BACKGROUND_PANEL
TAB_ACTIVE_FG = PRIMARY_INDIGO
TAB_HOVER_BG = BACKGROUND_PANEL
TAB_HOVER_FG = PRIMARY_INDIGO
TAB_BORDER = BORDER_DEFAULT
TAB_ACCENT = ACCENT_TEAL
TAB_PADDING_X = 14
TAB_PADDING_Y = 8

# =============================================================================
# PROGRESS PANEL Y STATUS BAR (franja inferior)
# =============================================================================

PROGRESS_PANEL_BG = BACKGROUND_MUTED
PROGRESS_PANEL_BORDER = BORDER_DEFAULT
PROGRESS_PANEL_HEIGHT = 50
PROGRESS_PERCENT_FG = TEXT_SECONDARY

STATUS_BAR_HEIGHT = 46

# =============================================================================
# TARJETAS DE HERRAMIENTA (ToolCard)
# =============================================================================

CARD_BG = BACKGROUND_PANEL
CARD_HOVER_BG = BACKGROUND_MUTED
CARD_DISABLED_BG = BACKGROUND_MUTED
CARD_BORDER = BORDER_DEFAULT
CARD_BORDER_HOVER = PRIMARY_INDIGO_HOVER
CARD_BORDER_FOCUS = ACCENT_TEAL
CARD_BORDER_PRESSED = PRIMARY_INDIGO
CARD_ACCENT = ACCENT_TEAL
CARD_TITLE_FG = TEXT_PRIMARY
CARD_DESC_FG = TEXT_SECONDARY
CARD_DISABLED_FG = TEXT_DISABLED
CARD_PADX = SPACE_MD
CARD_PADY = SPACE_MD
CARD_TITLE_GAP = SPACE_XS
CARD_GAP = SPACE_SM
CARD_ACCENT_WIDTH = 4
CARD_MIN_WIDTH = 240
CARD_WRAPLENGTH = 220

# =============================================================================
# INDICADOR DE PASOS (StepIndicator)
# =============================================================================

STEP_PENDING_BG = BACKGROUND_MUTED
STEP_PENDING_FG = TEXT_DISABLED
STEP_ACTIVE_BG = PRIMARY_INDIGO
STEP_ACTIVE_FG = TEXT_ON_PRIMARY
STEP_COMPLETED_BG = ACCENT_TEAL
STEP_COMPLETED_FG = TEXT_ON_PRIMARY
STEP_CONNECTOR = BORDER_DEFAULT
STEP_LABEL_PENDING_FG = TEXT_SECONDARY
STEP_LABEL_ACTIVE_FG = PRIMARY_INDIGO
STEP_LABEL_COMPLETED_FG = ACCENT_TEAL_DARK
STEP_MARKER_SIZE = 22
STEP_GAP = SPACE_SM

# =============================================================================
# TREEVIEW (DocFlow.Treeview)
# =============================================================================

TREE_BG = BACKGROUND_PANEL
TREE_FG = TEXT_PRIMARY
TREE_HEADING_BG = BACKGROUND_MUTED
TREE_HEADING_FG = TEXT_PRIMARY
TREE_SELECTED_BG = PRIMARY_INDIGO
TREE_SELECTED_FG = TEXT_ON_PRIMARY
TREE_BORDER = BORDER_DEFAULT
TREE_ROWHEIGHT = 26
TREE_TAG_OK_FG = ACTION_SUCCESS
TREE_TAG_CONFLICT_FG = ACTION_CANCEL

# =============================================================================
# ESTADO VACÍO / AVISOS DE FLUJO
# =============================================================================

EMPTY_STATE_BG = BACKGROUND_PANEL
EMPTY_STATE_TITLE_FG = TEXT_PRIMARY
EMPTY_STATE_HINT_FG = TEXT_SECONDARY

FLOW_NOTICE_SAFE_BG = "#FFFBEB"
FLOW_NOTICE_SAFE_FG = STATE_CANCELLED
FLOW_HEADER_TITLE_FG = PRIMARY_INDIGO
FLOW_HEADER_DESC_FG = TEXT_SECONDARY
FLOW_SECTION_FG = TEXT_SECONDARY
FLOW_INFO_FG = TEXT_SECONDARY
FLOW_SUMMARY_OK_FG = ACTION_SUCCESS
FLOW_SUMMARY_ERROR_FG = ACTION_CANCEL

# =============================================================================
# SELECTOR DE RUTAS (create_route_frame)
# =============================================================================

ROUTE_BG = BACKGROUND_PANEL
ROUTE_FG = TEXT_PRIMARY
ROUTE_PLACEHOLDER_FG = TEXT_DISABLED
ROUTE_BORDER = BORDER_DEFAULT
ROUTE_BORDER_FOCUS = PRIMARY_INDIGO
ROUTE_DISABLED_BG = BACKGROUND_MUTED
ROUTE_DISABLED_FG = TEXT_DISABLED
ROUTE_INSERT = TEXT_PRIMARY

# =============================================================================
# PANEL DE AYUDA (create_help_panel)
# =============================================================================

HELP_PANEL_BG = BACKGROUND_PANEL
HELP_PANEL_TITLE_FG = PRIMARY_INDIGO
HELP_PANEL_TEXT_FG = TEXT_SECONDARY
HELP_PANEL_WRAPLENGTH = 900

# =============================================================================
# DIÁLOGO GENERAL DE ERROR
# =============================================================================

ERROR_DIALOG_BG = BACKGROUND_APP
ERROR_DIALOG_HEADER_FG = ACTION_CANCEL
ERROR_DIALOG_LABEL_FG = TEXT_PRIMARY
ERROR_DIALOG_DETAIL_BG = BACKGROUND_PANEL
ERROR_DIALOG_DETAIL_FG = TEXT_PRIMARY
ERROR_DIALOG_DETAIL_BORDER = BORDER_DEFAULT
ERROR_DIALOG_LOG_FG = TEXT_SECONDARY
ERROR_DIALOG_PADX = SPACE_LG
ERROR_DIALOG_PADY = SPACE_MD

# =============================================================================
# DIÁLOGO CONFIGURACIÓN NUMERACIÓN PDF
# =============================================================================

CONFIG_DIALOG_BG = BACKGROUND_APP
CONFIG_DIALOG_PANEL_BG = BACKGROUND_PANEL
CONFIG_DIALOG_PANEL_BORDER = BORDER_DEFAULT
CONFIG_DIALOG_TITLE_FG = PRIMARY_INDIGO
CONFIG_DIALOG_LABEL_FG = TEXT_PRIMARY
CONFIG_DIALOG_PADX = SPACE_MD
CONFIG_DIALOG_PADY = SPACE_MD
CONFIG_DIALOG_PREVIEW_BORDER = BORDER_DEFAULT

# =============================================================================
# ALIASES LEGACY — botones de ejecución (CorporateButton y consumidores actuales)
# Conservar valores originales hasta migrar variantes en una fase posterior.
# =============================================================================

BTN_WIDTH = 40
BTN_PADX = 30

BTN_BG = "#0a2744"
BTN_BG_HOVER = "#145a8c"
BTN_BG_PRESSED = "#061c33"
BTN_BG_DISABLED = "#3d4a56"
BTN_FG = "#ffffff"
# Gris medio-oscuro: legible sobre el fondo nativo claro de Aqua (tk.Button).
BTN_FG_DISABLED = "#4f5b66"
# Texto secundario sobre superficie oscura controlada (CorporateButton).
BTN_FG_DISABLED_SURFACE = "#b0bbc6"
BTN_FOCUS_COLOR = "#7ec8e8"

CANCEL_BG = "#ED8F7B"
CANCEL_HOVER = "#E5735C"

# =============================================================================
# VARIANTES DE BOTÓN (CorporateButton) — solo colores centralizados
# =============================================================================

BTN_SECONDARY_BG = BACKGROUND_PANEL
BTN_SECONDARY_HOVER = BACKGROUND_MUTED
BTN_SECONDARY_PRESSED = BORDER_DEFAULT
BTN_SECONDARY_FG = TEXT_PRIMARY
BTN_SECONDARY_DISABLED_BG = BACKGROUND_MUTED
BTN_SECONDARY_DISABLED_FG = TEXT_DISABLED

# Superficie disabled compartida para variantes semánticas oscuras.
BTN_VARIANT_DISABLED_BG = "#64748B"
BTN_VARIANT_DISABLED_FG = "#E2E8F0"
BTN_VARIANT_FOCUS = "#93C5FD"

BUTTON_VARIANTS = {
    # primary: apariencia legacy de herramientas (evita regresiones en pestañas).
    "primary": {
        "bg": BTN_BG,
        "hover": BTN_BG_HOVER,
        "pressed": BTN_BG_PRESSED,
        "fg": BTN_FG,
        "disabled_bg": BTN_BG_DISABLED,
        "disabled_fg": BTN_FG_DISABLED_SURFACE,
        "focus": BTN_FOCUS_COLOR,
    },
    "secondary": {
        "bg": BTN_SECONDARY_BG,
        "hover": BTN_SECONDARY_HOVER,
        "pressed": BTN_SECONDARY_PRESSED,
        "fg": BTN_SECONDARY_FG,
        "disabled_bg": BTN_SECONDARY_DISABLED_BG,
        "disabled_fg": BTN_SECONDARY_DISABLED_FG,
        "focus": BTN_VARIANT_FOCUS,
    },
    # Destructiva discreta: superficie neutra, texto de acción cancel/error.
    "destructive": {
        "bg": BTN_SECONDARY_BG,
        "hover": BTN_SECONDARY_HOVER,
        "pressed": BTN_SECONDARY_PRESSED,
        "fg": ACTION_CANCEL,
        "disabled_bg": BTN_SECONDARY_DISABLED_BG,
        "disabled_fg": BTN_SECONDARY_DISABLED_FG,
        "focus": BTN_VARIANT_FOCUS,
    },
    "cancel": {
        "bg": ACTION_CANCEL,
        "hover": ACTION_CANCEL_HOVER,
        "pressed": ACTION_CANCEL_PRESSED,
        "fg": TEXT_ON_PRIMARY,
        "disabled_bg": BTN_VARIANT_DISABLED_BG,
        "disabled_fg": BTN_VARIANT_DISABLED_FG,
        "focus": BTN_VARIANT_FOCUS,
    },
    "success": {
        "bg": ACTION_SUCCESS,
        "hover": ACTION_SUCCESS_HOVER,
        "pressed": ACTION_SUCCESS_PRESSED,
        "fg": TEXT_ON_PRIMARY,
        "disabled_bg": BTN_VARIANT_DISABLED_BG,
        "disabled_fg": BTN_VARIANT_DISABLED_FG,
        "focus": BTN_VARIANT_FOCUS,
    },
    "diagnostic": {
        "bg": PRIMARY_INDIGO,
        "hover": PRIMARY_INDIGO_HOVER,
        "pressed": PRIMARY_INDIGO_PRESSED,
        "fg": TEXT_ON_PRIMARY,
        "disabled_bg": BTN_VARIANT_DISABLED_BG,
        "disabled_fg": BTN_VARIANT_DISABLED_FG,
        "focus": BTN_VARIANT_FOCUS,
    },
}

# =============================================================================
# ALIASES LEGACY — superficies y títulos (redirigen al Light Indigo DS)
# =============================================================================

TOP_BG = HEADER_BG
FRAME_BG = BACKGROUND_APP
TITLE_FG = PRIMARY_INDIGO
