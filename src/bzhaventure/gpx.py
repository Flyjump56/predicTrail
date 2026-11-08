"""Lecture GPX, distances géographiques et échantillonnage adapté au relief."""
from bisect import bisect_left
from datetime import datetime, timezone
from math import asin, ceil, cos, isfinite, radians, sin, sqrt
from statistics import median
import xml.etree.ElementTree as ET

from .settings import (CLASSIFICATION_VERSION, DISTANCE_CLASSES, DISTANCE_LIMITS,
                       PROFILE_FAMILIES, PROFILE_LABELS, RELIEF_GRID, RELIEF_REVERSAL, SOURCE_SAMPLING)


class Course(list):
    """Segments GPX et caches propres à une analyse.

    Un segment contient les distances cumulées, les points originaux et les
    échantillons. Les points portent latitude, longitude, altitude et secondes
    absolues. Les échantillons ajoutent leur distance locale en cinquième valeur.
    Les caches sont utilisés après lecture, pendant laquelle les données sont fixes."""
    def __init__(self, segments, classification=None):
        super().__init__(segments)
        self.classification = classification
        self.resampled = {}
        self.block_cache = None


def distance(a, b):
    """Calculer la distance horizontale en mètres par la formule de Haversine."""
    lat1, lon1, lat2, lon2 = map(radians, (*a[:2], *b[:2]))
    h = sin((lat2 - lat1) / 2)**2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2)**2
    return 12_742_000 * asin(sqrt(min(1, h)))


def interpolate(axis, values, position):
    """Interpoler les valeurs d'un point à une distance donnée, bornes comprises."""
    if position >= axis[-1]:
        return values[-1]
    i = bisect_left(axis, position)
    if i == 0 or axis[i] == position:
        return values[i]
    fraction = (position - axis[i - 1]) / (axis[i] - axis[i - 1])
    return tuple(a + fraction * (b - a) for a, b in zip(values[i - 1], values[i]))


def read_gpx(path, timed=False):
    """Lire les pistes ou routes et préparer leur échantillonnage adaptatif.

    Les références exigent des dates ordonnées. Un parcours à prédire peut
    être dépourvu de dates, mais ses coordonnées et altitudes sont requises."""
    root = ET.parse(path).getroot()
    groups = [s.findall("{*}trkpt") for s in root.findall(".//{*}trkseg")]
    if not any(groups):
        groups = [r.findall("{*}rtept") for r in root.findall("{*}rte")]
    segments = []
    previous_time = None
    for group in groups:
        points, axis = [], []
        for node in group:
            lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
            elevation = float(node.findtext("{*}ele") or "nan")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and isfinite(elevation)):
                raise ValueError("Coordonnées ou altitude manquantes ou invalides.")
            timestamp = 0
            if timed:
                raw_time = node.findtext("{*}time")
                if not raw_time:
                    raise ValueError("Horodatage manquant dans une course de référence.")
                date = datetime.fromisoformat(raw_time.strip().replace("Z", "+00:00"))
                timestamp = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
                if previous_time is not None and timestamp < previous_time:
                    raise ValueError("Horodatages dans le désordre.")
                previous_time = timestamp
            point = (lat, lon, elevation, timestamp)
            step = distance(points[-1], point) if points else 0
            if points and step < 0.01:
                if node is group[-1] and len(points) > 1:
                    points[-1] = (*points[-1][:3], timestamp)
                continue
            axis.append(axis[-1] + step if axis else 0)
            points.append(point)
        if len(points) > 1:
            count = ceil(axis[-1] / 100)
            samples = [interpolate(axis, points, axis[-1] * i / count) for i in range(count)]
            segments.append((axis, points, [*samples, points[-1]]))
    if not segments:
        raise ValueError("Le GPX ne contient aucun parcours exploitable.")
    return adapt_course(segments)


def sample_intervals(segment):
    """Itérer sur les portions avec leurs vraies bornes de distance.

    Les intervalles peuvent avoir des longueurs différentes après insertion
    des sommets et creux. Les anciennes grilles uniformes restent acceptées."""
    axis, _, samples = segment
    uniform = axis[-1] / (len(samples) - 1)
    for i, (start, end) in enumerate(zip(samples, samples[1:])):
        left = start[4] if len(start) > 4 else i * uniform
        right = end[4] if len(end) > 4 else (i + 1) * uniform
        yield start, end, left, right


def relief_turns(axis, points, threshold=20):
    """Keep relief changes exceeding 20 m, independently within each segment."""
    turns = [0]
    extreme = 0
    direction = 0
    for i in range(1, len(points)):
        delta = points[i][2] - points[extreme][2]
        if direction == 0:
            if abs(delta) >= threshold:
                direction = 1 if delta > 0 else -1
                extreme = i
        elif delta * direction >= 0:
            extreme = i
        elif abs(delta) >= threshold:
            turns.append(extreme)
            direction *= -1
            extreme = i
    if turns[-1] != len(points) - 1:
        turns.append(len(points) - 1)
    return [axis[i] for i in turns]


def resample_course(course, step, preserve_turns=False):
    """Rééchantillonner les points originaux et conserver les inversions de relief."""
    key = (step, preserve_turns)
    if isinstance(course, Course) and key in course.resampled:
        return course.resampled[key]
    result = []
    for axis, points, _ in course:
        count = ceil(axis[-1] / step)
        locations = {axis[-1] * i / count for i in range(count)}
        locations.add(axis[-1])
        if preserve_turns:
            fine_count = ceil(axis[-1] / RELIEF_GRID)
            fine_axis = [axis[-1] * i / fine_count for i in range(fine_count)] + [axis[-1]]
            fine_points = [interpolate(axis, points, position) for position in fine_axis]
            locations.update(relief_turns(fine_axis, fine_points, threshold=RELIEF_REVERSAL))
        # Coalesce near-identical extrema and grid positions.
        positions = []
        for position in sorted(locations):
            if len(positions) > 1 and position - positions[-1] < 1:
                if position == axis[-1]:
                    positions[-1] = position
            else:
                positions.append(position)
        samples = [(*interpolate(axis, points, position)[:4], position) for position in positions]
        result.append((axis, points, samples))
    result = Course(result, getattr(course, "classification", None))
    if isinstance(course, Course):
        course.resampled[key] = result
    return result


def describe_course(course):
    """Décrire le relief sur une grille commune, sans confondre volume et forme.

    Une médiane sur trois points retire les pics isolés. Les inversions de moins
    de 10 m ne coupent pas une ascension : petits replats et creux sont fusionnés.
    Les parts de dénivelé et les fréquences restent disponibles au modèle.
    """
    if (isinstance(course, Course) and course.classification is not None and
            course.classification.get("version") == CLASSIFICATION_VERSION):
        return course.classification
    canonical = resample_course(course, RELIEF_GRID)
    total = sum(axis[-1] for axis, _, _ in canonical)
    ascent = descent = steep_distance = 0.0
    climbs, lengths = [], []
    for segment in canonical:
        _, _, samples = segment
        axis = [point[4] for point in samples]
        smooth = []
        for i, point in enumerate(samples):
            altitude = point[2] if i in (0, len(samples)-1) else median(p[2] for p in samples[i-1:i+2])
            smooth.append((*point[:2], altitude, *point[3:]))
        for i in range(len(axis)-1):
            # Pente sur une fenêtre de 100 m pour limiter les effets du bruit GPS.
            center = (axis[i]+axis[i+1])/2
            left, right = max(0,center-50), min(axis[-1],center+50)
            grade = 100*(interpolate(axis,smooth,right)[2]-interpolate(axis,smooth,left)[2])/max(.01,right-left)
            if abs(grade) > 3:
                steep_distance += axis[i+1]-axis[i]
        turns = relief_turns(axis, smooth, threshold=RELIEF_REVERSAL)
        for left, right in zip(turns, turns[1:]):
            gain = interpolate(axis,smooth,right)[2]-interpolate(axis,smooth,left)[2]
            length = right-left
            if abs(gain) < RELIEF_REVERSAL:
                continue
            lengths.append(length)
            if gain < 0:
                descent -= gain
                continue
            ascent += gain
            kind = ("large" if gain >= 500 or (gain >= 300 and length >= 5000) else
                    "small" if gain < 100 else "intermediate")
            climbs.append(dict(gain=gain, length=length, kind=kind))
    density = ascent/(total/1000)
    shares = {kind: sum(c["gain"] for c in climbs if c["kind"] == kind)/ascent if ascent else 0
              for kind in ("small", "intermediate", "large")}
    frequency = len(climbs)*10000/total
    small_frequency = sum(c["kind"] == "small" for c in climbs)*10000/total
    small_length = median([c["length"] for c in climbs if c["kind"] == "small"]) if shares["small"] else 0
    steep_share = steep_distance/total
    if shares["large"] >= .5:
        profile, reason = "mountain", "Au moins 50 % du D+ dans les grandes ascensions"
    elif density < 5 and steep_share < .1:
        profile, reason = "flat", "D+ inférieur à 5 m/km et moins de 10 % de portions pentues"
    elif shares["small"] >= .6 and small_frequency >= 4 and density >= 10 and small_length <= 1000:
        profile, reason = "sawtooth", "Au moins 60 % du D+ dans de petites bosses, au moins 4 par 10 km et longueur médiane ≤ 1 km"
    elif density < 20:
        profile, reason = "rolling", "D+ inférieur à 20 m/km sans répétition dominante de petites bosses"
    elif shares["intermediate"] >= .5:
        profile, reason = "intermediate", "Au moins 50 % du D+ dans les ascensions intermédiaires"
    else:
        profile, reason = "mixed", "Aucune forme dominante selon les seuils retenus"
    index = next((i for i,limit in enumerate(DISTANCE_LIMITS) if total/1000 < limit), len(DISTANCE_LIMITS))
    category, label, _ = DISTANCE_CLASSES[index]
    source_profile = profile
    profile = PROFILE_FAMILIES[source_profile]
    return dict(version=CLASSIFICATION_VERSION, sourceProfile=source_profile, profile=profile, profileLabel=PROFILE_LABELS[profile],
                classificationReason=reason, distanceClass=category, distanceLabel=label,
                distance=total, ascent=ascent, descent=descent, ascentDensity=density,
                reliefDensity=(ascent+descent)/(total/1000), steepDistanceShare=steep_share,
                climbShares=shares, climbCount=len(climbs), climbsPer10Km=frequency,
                smallClimbsPer10Km=small_frequency, medianSmallClimbLength=small_length,
                climbCounts={kind:sum(c["kind"]==kind for c in climbs) for kind in shares},
                medianClimbGain=median([c["gain"] for c in climbs]) if climbs else 0,
                medianClimbLength=median([c["length"] for c in climbs]) if climbs else 0,
                maxClimbGain=max([c["gain"] for c in climbs], default=0),
                longReliefShare=shares["large"], medianReliefLength=median(lengths) if lengths else 0,
                sampling=SOURCE_SAMPLING[source_profile][index])


def adapt_course(course):
    """Appliquer le pas du groupe et mémoriser sa classification."""
    descriptor = describe_course(course)
    result = resample_course(course, descriptor["sampling"], preserve_turns=True)
    result.classification = descriptor
    return result


def blocks(segments):
    """Fournir longueur en mètres, pente en pourcentage et durée en secondes."""
    if isinstance(segments, Course) and segments.block_cache is not None:
        yield from segments.block_cache
        return
    cached = []
    for segment in segments:
        for a, b, left, right in sample_intervals(segment):
            length = right - left
            block = (length, 100 * (b[2] - a[2]) / length, b[3] - a[3])
            cached.append(block)
            yield block
    if isinstance(segments, Course):
        segments.block_cache = cached


def elapsed(course):
    """Calculer le temps écoulé entre départ et arrivée, interruptions comprises."""
    return course[-1][1][-1][3] - course[0][1][0][3]
