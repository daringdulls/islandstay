"""Dates that change a visit to a local island, and what they mean for guests.

Islamic dates follow the moon sighting in the Maldives, so they are marked as expected and can move by a day.
Add next year's dates here each December.
"""
import datetime as dt

D = dt.date
EVENTS = [
    # (first day, last day, name, expected?, what it means for visitors)
    (D(2027, 1, 1), D(2027, 1, 1), "New Year's Day", False, "Public holiday: government offices closed, ferries may run a holiday schedule."),
    (D(2027, 2, 8), D(2027, 3, 9), "Ramadan", True,
     "Locals fast from dawn to sunset. Most guest houses serve guests as usual, but cafés may open only after sunset. "
     "Avoid eating or drinking in public in the village during the day."),
    (D(2027, 3, 10), D(2027, 3, 12), "Eid al-Fitr", True, "Celebrations after Ramadan: public holidays, island events and busier ferries. Book transfers early."),
    (D(2027, 5, 16), D(2027, 5, 19), "Eid al-Adha", True, "Public holidays: offices closed, families travel between islands. Book boats ahead."),
    (D(2027, 6, 6), D(2027, 6, 6), "Islamic New Year", True, "Public holiday."),
    (D(2027, 7, 26), D(2027, 7, 26), "Independence Day", False, "National celebrations, parades in Malé and on many islands."),
    (D(2027, 8, 15), D(2027, 8, 15), "Prophet's Birthday", True, "Public holiday."),
    (D(2027, 11, 3), D(2027, 11, 3), "Victory Day", False, "Public holiday."),
    (D(2027, 11, 11), D(2027, 11, 11), "Republic Day", False, "Public holiday."),
    (D(2026, 11, 11), D(2026, 11, 11), "Republic Day", False, "Public holiday."),
    (D(2026, 12, 31), D(2026, 12, 31), "New Year's Eve", False, "Island celebrations on many local islands; resorts host fireworks nearby."),
]

FRIDAY = ("Every Friday", "Most public ferries don't run, and shops close for midday prayers (about 11:30–14:00).")


def upcoming(today=None, days=120):
    """Events that start or are going on within the next `days` days."""
    today = today or dt.date.today()
    until = today + dt.timedelta(days=days)
    out = []
    for start, end, name, expected, note in sorted(EVENTS):
        if end >= today and start <= until:
            out.append({"start": start, "end": end, "name": name, "expected": expected, "note": note,
                        "now": start <= today <= end, "single": start == end})
    return out
