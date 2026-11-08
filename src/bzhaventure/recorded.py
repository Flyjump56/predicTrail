"""Comparaison de chronologies GPX réellement enregistrées, sans prédiction."""
from datetime import datetime, timezone
from math import isfinite

from .analysis import geometry, summarize
from .gpx import describe_course, interpolate, sample_intervals


def recorded_sections(course, start=None):
    """Couleurs sur la grille de relief existante ; temps issus du GPX uniquement."""
    sections, offset = [], 0.0
    for segment, part in enumerate(course):
        for a, b, left, right in sample_intervals(part):
            length = right-left
            seconds = b[3]-a[3] if start is not None else 0
            sections.append(dict(segment=segment, start=a[:3], end=b[:3],
                distance=offset+left, endDistance=offset+right,
                time=a[3]-start if start is not None else 0,
                endTime=b[3]-start if start is not None else 0,
                grade=100*(b[2]-a[2])/max(1e-9,length),
                speed=3.6*length/seconds if seconds > 0 else 0))
        offset += part[0][-1]
    return sections


def recorded_run(course, interval):
    """Conserver les temps écoulés du GPX, y compris les coupures de segments.

    Les repères sont interpolés entre points horodatés à la distance demandée.
    Aucun modèle, recalage de durée ou estimation de pause n'intervient.
    """
    if not isfinite(interval) or interval <= 0:
        raise ValueError("Espacement des repères incorrect.")
    start = course[0][1][0][3]
    duration = course[-1][1][-1][3]-start
    if duration <= 0:
        raise ValueError("Le GPX ne contient pas de durée enregistrée positive.")
    total_distance = sum(axis[-1] for axis, _, _ in course)
    marks = [(0, 0, *course[0][1][0][:3], "Départ")]
    next_mark, offset = interval, 0.0
    for axis, points, _ in course:
        while next_mark <= offset+axis[-1]+1e-8:
            point = interpolate(axis, points, min(axis[-1], max(0, next_mark-offset)))
            marks.append((next_mark, point[3]-start, *point[:3], "Passage"))
            next_mark += interval
        offset += axis[-1]
    if abs(marks[-1][0]-total_distance) < 1e-8:
        marks.pop()
    marks.append((total_distance, duration, *course[-1][1][-1][:3], "Arrivée"))
    return dict(**summarize(course), trace=geometry(course), marks=marks, duration=duration,
                classification=describe_course(course), sections=recorded_sections(course,start),
                recordedStart=datetime.fromtimestamp(start, timezone.utc).isoformat(),
                exportPoints=[[[*p[:3], p[3]-start] for p in points] for _, points, _ in course],
                model=dict(scope="recorded", selectionLabel="Temps enregistrés du GPX · sans prédiction"))
