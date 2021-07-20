from kivymd.color_definitions import colors

__all__ = [
    'PRIMARY_PALETTE',
    'SECONDARY_PALETTE',
    'THEME',
]

PRIMARY_PALETTE = "Green"
SECONDARY_PALETTE = "Orange"
_THEME = {
    PRIMARY_PALETTE: {
        "50": "b0da8e",
        "100": "a3d47b",
        "200": "95cd69",
        "300": "88c756",
        # "400": "7bc143",
        # "500": "6fae3c",
        "400": "abd55a",
        "500": "abd55a",
        "600": "629a36",
        "700": "56872f",
        "800": "4a7428",
        "900": "486363",
        "A100": "3e6122",
        "A200": "314d1b",
        "A400": "253a14",
        "A700": "19270d",
    },
    SECONDARY_PALETTE: {
        "50": "fdd39a",
        "100": "fcca85",
        "200": "fcc171",
        "300": "fbaf48",
        "400": "faa634",
        "500": "e1952f",
        "600": "c8852a",
        "700": "af7424",
        "800": "96641f",
        "900": "7d531a",
        "A100": "644215",
        "A200": "32210a",
        "A400": "191105",
        "A700": "000000",
    }
}
colors.update(_THEME)
THEME = colors.copy()
