"""25 curated beautiful gradient presets for tweet backgrounds."""

GRADIENTS = [
    {
        "name": "Sunset Blaze",
        "colors": ["#FF6B6B", "#FFE66D"],
        "angle": 135
    },
    {
        "name": "Ocean Deep",
        "colors": ["#00D4FF", "#0099FF"],
        "angle": 180
    },
    {
        "name": "Forest Dawn",
        "colors": ["#11998E", "#38EF7D"],
        "angle": 120
    },
    {
        "name": "Purple Haze",
        "colors": ["#9D50BB", "#6E48AA"],
        "angle": 135
    },
    {
        "name": "Fire Burst",
        "colors": ["#FF512F", "#DD2476"],
        "angle": 45
    },
    {
        "name": "Candy Floss",
        "colors": ["#FFA8D5", "#FF85E4"],
        "angle": 90
    },
    {
        "name": "Northern Lights",
        "colors": ["#00C9FF", "#92FE9D"],
        "angle": 45
    },
    {
        "name": "Peachy Keen",
        "colors": ["#FF9A56", "#FFBE76"],
        "angle": 180
    },
    {
        "name": "Neon Nights",
        "colors": ["#FF006E", "#8338EC"],
        "angle": 135
    },
    {
        "name": "Emerald Sea",
        "colors": ["#08AEEA", "#2AF598"],
        "angle": 90
    },
    {
        "name": "Lavender Dream",
        "colors": ["#B993D6", "#8CA6DB"],
        "angle": 120
    },
    {
        "name": "Cosmic Dust",
        "colors": ["#7F00FF", "#E100FF"],
        "angle": 45
    },
    {
        "name": "Mango Tango",
        "colors": ["#FF8008", "#FFC837"],
        "angle": 90
    },
    {
        "name": "Sky Blue",
        "colors": ["#56CCF2", "#2F80ED"],
        "angle": 180
    },
    {
        "name": "Rose Gold",
        "colors": ["#F093FB", "#F5576C"],
        "angle": 135
    },
    {
        "name": "Mint Fresh",
        "colors": ["#A8EDEA", "#FED6E3"],
        "angle": 120
    },
    {
        "name": "Electric Violet",
        "colors": ["#4776E6", "#8E54E9"],
        "angle": 45
    },
    {
        "name": "Citrus Burst",
        "colors": ["#FDFC47", "#24FE41"],
        "angle": 90
    },
    {
        "name": "Cherry Blossom",
        "colors": ["#FBC2EB", "#A6C1EE"],
        "angle": 135
    },
    {
        "name": "Aqua Marine",
        "colors": ["#1CB5E0", "#000851"],
        "angle": 180
    },
    {
        "name": "Golden Hour",
        "colors": ["#FDBB2D", "#22C1C3"],
        "angle": 45
    },
    {
        "name": "Berry Smoothie",
        "colors": ["#E94057", "#8A2387"],
        "angle": 120
    },
    {
        "name": "Ice Blue",
        "colors": ["#AAFFA9", "#11FFBD"],
        "angle": 90
    },
    {
        "name": "Sunset Purple",
        "colors": ["#6D28D9", "#DB2777"],
        "angle": 135
    },
    {
        "name": "Coral Reef",
        "colors": ["#FF7E5F", "#FEB47B"],
        "angle": 180
    }
]

def get_gradient_css(index: int) -> str:
    """Generate CSS gradient string for a given preset index."""
    if not 0 <= index < len(GRADIENTS):
        index = 0  # Default to first gradient

    gradient = GRADIENTS[index]
    colors = ", ".join(gradient["colors"])
    return f"linear-gradient({gradient['angle']}deg, {colors})"

def get_gradient_by_name(name: str) -> dict:
    """Get gradient preset by name."""
    for gradient in GRADIENTS:
        if gradient["name"].lower() == name.lower():
            return gradient
    return GRADIENTS[0]  # Default

# Hero gradient indexes - these are the 8 best gradients for tweets
HERO_GRADIENT_INDEXES = [
    0,   # Sunset Blaze
    1,   # Ocean Deep
    3,   # Purple Haze
    4,   # Fire Burst
    9,   # Emerald Sea
    12,  # Mango Tango
    14,  # Rose Gold
    24,  # Coral Reef
]

def get_hero_gradient(index: int) -> dict:
    """Return one of the 8 hero gradients by safe index (0..7)."""
    if not 0 <= index < len(HERO_GRADIENT_INDEXES):
        index = 0
    return GRADIENTS[HERO_GRADIENT_INDEXES[index]]

def get_hero_gradients() -> list:
    """Return all 8 hero gradients."""
    return [GRADIENTS[idx] for idx in HERO_GRADIENT_INDEXES]

__all__ = ['GRADIENTS', 'get_gradient_css', 'get_gradient_by_name', 'HERO_GRADIENT_INDEXES', 'get_hero_gradient', 'get_hero_gradients']