"""Intégration des allures prédites et interpolation des temps aux repères."""
from math import isfinite

from .gpx import interpolate, sample_intervals


def predict(segments, pace_at, interval, waypoints=None):
    """Intégrer les durées et interpoler les temps de passage aux distances demandées.

    Les repères contiennent distance, durée cumulée, latitude, longitude,
    altitude et libellé. Le départ et l'arrivée sont toujours présents."""
    if not isfinite(interval) or interval <= 0:
        raise ValueError("L'espacement des repères doit être positif.")
    if hasattr(pace_at, "for_course"):
        pace_at = pace_at.for_course(segments)
    km = seconds = 0
    marks = [(0, 0, *segments[0][1][0][:3], "Départ")]
    next_mark = interval
    for segment in segments:
        axis, points, _ = segment
        for a, b, left, right in sample_intervals(segment):
            length = right - left
            end = km + length
            pace = pace_at(100 * (b[2] - a[2]) / length)
            while next_mark <= end + 1e-8:
                position = min(axis[-1], left + next_mark - km)
                point = interpolate(axis, points, position)
                marks.append((next_mark, seconds + (next_mark - km) * pace, *point[:3], "Passage"))
                next_mark += interval
            seconds += length * pace
            km = end
    if abs(marks[-1][0] - km) < 1e-8:
        marks.pop()
    marks.append((km, seconds, *segments[-1][1][-1][:3], "Arrivée"))
    if waypoints:
        if len(waypoints) > 200:
            raise ValueError("Le parcours accepte au maximum 200 repères personnalisés.")
        for waypoint in waypoints:
            position = float(waypoint["km"]) * 1000
            comment = str(waypoint.get("comment", "")).strip()
            if not isfinite(position) or position < 0 or position > km + 1e-6:
                raise ValueError("Un repère est situé en dehors du parcours.")
            if len(comment) > 500:
                raise ValueError("Un commentaire dépasse 500 caractères.")
            position = min(position, km)
            offset = cumulative = 0
            point = None
            for segment in segments:
                axis, originals, _ = segment
                for a, b, left, right in sample_intervals(segment):
                    length = right - left
                    pace = pace_at(100 * (b[2] - a[2]) / length)
                    if position <= offset + right + 1e-8:
                        point = interpolate(axis, originals, max(0, position - offset))
                        cumulative += max(0, position - offset - left) * pace
                        break
                    cumulative += length * pace
                if point is not None:
                    break
                offset += axis[-1]
            label = "Repère personnalisé" + (" · " + comment if comment else "")
            existing = next((i for i, row in enumerate(marks) if abs(row[0] - position) < 1e-6), None)
            if existing is None:
                marks.append((position, cumulative, *point[:3], label))
            else:
                row = marks[existing]
                marks[existing] = (*row[:5], row[5] + " · " + label)
        marks.sort(key=lambda row: row[0])
    return marks
