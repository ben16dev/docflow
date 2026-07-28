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

ACTION_SUCCESS = "#047857"
ACTION_SUCCESS_HOVER = "#065F46"

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
STATE_CANCELLED = TEXT_DISABLED

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
# ALIASES LEGACY — superficies y títulos (redirigen al Light Indigo DS)
# =============================================================================

TOP_BG = BACKGROUND_APP
FRAME_BG = BACKGROUND_APP
TITLE_FG = PRIMARY_INDIGO
