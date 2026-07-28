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
# TIPOGRAFÍA (tamaños; la familia se resuelve por plataforma en fases posteriores)
# =============================================================================

FONT_SIZE_XS = 8
FONT_SIZE_SM = 9
FONT_SIZE_MD = 10
FONT_SIZE_LG = 11
FONT_SIZE_XL = 13

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

TOP_BG = BACKGROUND_APP
FRAME_BG = BACKGROUND_APP
TITLE_FG = PRIMARY_INDIGO
