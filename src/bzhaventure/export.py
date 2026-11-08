"""Chronologie des points originaux destinée à l'export GPX du navigateur."""
from .gpx import sample_intervals


def export_points(course, model):
    """Conserver les coupures et intégrer le même modèle que les repères.

    Les horodatages d'origine sont remplacés par des secondes depuis le départ.
    L'interpolation temporelle conserve chaque coordonnée et altitude d'origine.
    """
    result, offset = [], 0.0
    for segment in course:
        axis, points, _ = segment
        intervals = list(sample_intervals(segment))
        index, seconds = 0, offset
        output = []
        for position, point in zip(axis, points):
            while index < len(intervals) and position > intervals[index][3]:
                a, b, left, right = intervals[index]
                seconds += (right-left) * model(100*(b[2]-a[2])/(right-left))
                index += 1
            current = seconds
            if index < len(intervals):
                a, b, left, right = intervals[index]
                current += max(0, position-left) * model(100*(b[2]-a[2])/(right-left))
            output.append([*point[:3], current])
        # Une portion sans distance conserve le temps cumulé précédent.
        offset = output[-1][3] if output else offset
        result.append(output)
    return result
