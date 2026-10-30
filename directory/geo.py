"""Map positions for atolls and islands.

Island coordinates come from Wikipedia / GeoNames where available (see the island's sources) and are
accurate to within a few hundred metres; those marked "approx." are estimates good to about 1 km.
Atolls are drawn as ellipses: centre (lat, lng) and half-height / half-width in degrees. They are a
schematic outline of each atoll's reef, for clicking on the map, not a survey.
"""

ISLAND_COORDS = {
    "Malé": (4.1755, 73.5093),
    "Hulhumalé": (4.2120, 73.5400),  # approx.
    "Maafushi": (3.9403, 73.4889),
    "Guraidhoo": (3.9006, 73.4681),
    "Gulhi": (3.9889, 73.5089),
    "Huraa": (4.3330, 73.6000),  # approx.
    "Thulusdhoo": (4.3728, 73.6489),
    "Himmafushi": (4.3092, 73.5708),
    "Dhiffushi": (4.4419, 73.7136),
    "Fulidhoo": (3.6806, 73.4155),
    "Rasdhoo": (4.2630, 72.9910),  # approx.
    "Ukulhas": (4.2150, 72.8640),  # approx.
    "Mathiveri": (4.1920, 72.7450),  # approx.
    "Thoddoo": (4.4380, 72.9570),  # approx.
    "Dhigurah": (3.5300, 72.9260),  # approx.
    "Dhangethi": (3.6070, 72.9550),  # approx.
    "Fenfushi": (3.4898, 72.7835),
    "Omadhoo": (3.7914, 72.9619),
    "Dharavandhoo": (5.1560, 73.1330),
    "Hanimaadhoo": (6.7480, 73.1700),
    "Fuvahmulah": (-0.2990, 73.4240),
    "Hithadhoo": (-0.6155, 73.0945),
}

# name: (centre lat, centre lng, half-height°, half-width°)
ATOLL_SHAPES = {
    "Haa Alif": (6.95, 72.98, 0.30, 0.20),
    "Haa Dhaalu": (6.62, 73.07, 0.20, 0.17),
    "Shaviyani": (6.28, 73.18, 0.20, 0.18),
    "Noonu": (5.85, 73.38, 0.24, 0.15),
    "Raa": (5.58, 72.95, 0.30, 0.17),
    "Baa": (5.12, 73.02, 0.22, 0.20),
    "Lhaviyani": (5.33, 73.52, 0.17, 0.13),
    "North Malé": (4.42, 73.52, 0.30, 0.18),
    "South Malé": (3.96, 73.42, 0.17, 0.13),
    "North Ari": (4.22, 72.88, 0.26, 0.16),
    "South Ari": (3.68, 72.86, 0.24, 0.16),
    "Vaavu": (3.50, 73.52, 0.25, 0.18),
    "Meemu": (2.95, 73.52, 0.24, 0.15),
    "Faafu": (3.17, 72.95, 0.15, 0.12),
    "Dhaalu": (2.82, 72.93, 0.17, 0.13),
    "Thaa": (2.38, 73.10, 0.22, 0.24),
    "Laamu": (1.92, 73.43, 0.20, 0.17),
    "Huvadhoo North": (0.62, 73.25, 0.24, 0.32),
    "Huvadhoo South": (0.28, 73.18, 0.15, 0.30),
    "Fuvahmulah": (-0.30, 73.42, 0.05, 0.04),
    "Addu": (-0.64, 73.15, 0.09, 0.11),
}


def apply(Atoll, Island):
    """Fill in missing map positions by name. Used by the seed command and a data migration."""
    for atoll in Atoll.objects.filter(map_lat__isnull=True):
        shape = ATOLL_SHAPES.get(atoll.name)
        if shape:
            atoll.map_lat, atoll.map_lng, atoll.map_rlat, atoll.map_rlng = shape
            atoll.save(update_fields=["map_lat", "map_lng", "map_rlat", "map_rlng"])
    for island in Island.objects.filter(latitude__isnull=True):
        pos = ISLAND_COORDS.get(island.name)
        if pos:
            island.latitude, island.longitude = pos
            island.save(update_fields=["latitude", "longitude"])
