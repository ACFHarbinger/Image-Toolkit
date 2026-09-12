"""Gallery card color-label palette (§2.18B+C). Hex values live here for audit."""

# Preview-window highlight border (amber). Kept as a literal because the
# widget overlay component (gallery_card_preview_overlay.qss) is amber and the
# color must stay distinct from the accent/success state colors.
GALLERY_PREVIEW_COLOR = "#f39c12"

GALLERY_LABEL_COLORS: dict[str, str] = {
    "red": "#e74c3c",
    "orange": "#e67e22",
    "yellow": "#f1c40f",
    "green": "#2ecc71",
    "blue": "#3498db",
    "purple": "#9b59b6",
}

GALLERY_LABEL_ICONS: dict[str, str] = {
    "red": "🔴",
    "orange": "🟠",
    "yellow": "🟡",
    "green": "🟢",
    "blue": "🔵",
    "purple": "🟣",
}
