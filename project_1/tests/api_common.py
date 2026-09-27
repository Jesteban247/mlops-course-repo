"""Shared helpers for the course API examples."""

from api import GROUP_NUMBER, fetch_data


COLUMNS = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
    "wilderness_area",
    "soil_type",
    "cover_type",
]


def fetch_batch(group_number=GROUP_NUMBER, timeout=15):
    """Request one sample; the server chooses the current batch for the group."""
    return fetch_data(group_number=group_number, timeout=timeout)


def unique_rows(rows, seen_rows):
    """Return rows not previously seen and the number of duplicates in this sample."""
    new_rows = []
    duplicate_count = 0
    for row in rows:
        signature = tuple(str(value) for value in row)
        if signature in seen_rows:
            duplicate_count += 1
        else:
            seen_rows.add(signature)
            new_rows.append(row)
    return new_rows, duplicate_count
