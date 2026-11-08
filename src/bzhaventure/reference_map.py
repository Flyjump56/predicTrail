"""Géométries allégées de toutes les références, retenues ou exclues du modèle."""
from io import BytesIO
from math import ceil
from datetime import datetime, timezone

from .analysis import pause_summary, summarize
from .gpx import describe_course, elapsed, read_gpx


def reference_map(store, directory):
    courses, skipped = [], []
    def load(data):
        course = read_gpx(BytesIO(data), timed=True)
        return course, pause_summary(BytesIO(data), course)
    for source in store.reference_sources(directory, include_excluded=True):
        try:
            value, fingerprint, error, _ = store.load_reference(source, load)
            if error:
                raise ValueError(error)
            course, pauses = value
            if elapsed(course) <= 0:
                raise ValueError("Durée nulle")
            step = max(1, ceil(sum(len(points) for _, points, _ in course)/1500))
            trace = []
            for _, points, _ in course:
                sampled = list(points[::step])
                if sampled[-1] != points[-1]:
                    sampled.append(points[-1])
                trace.append([point[:2] for point in sampled])
            courses.append(dict(key=source["key"], contentId=fingerprint, name=source["name"], enabled=source["enabled"],
                                trace=trace, classification=describe_course(course),
                                summary=summarize(course), duration=elapsed(course), pauses=pauses,
                                recordedStart=datetime.fromtimestamp(course[0][1][0][3],timezone.utc).isoformat()))
        except (ValueError, OSError, TypeError) as error:
            skipped.append(source["name"]+" · "+str(error))
    return dict(courses=courses, skipped=skipped)
