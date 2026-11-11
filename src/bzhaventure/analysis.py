"""Analyses exposées au tableau de bord, comparaison des modèles et pauses."""
from copy import copy
from io import BytesIO
from datetime import datetime, timezone
from statistics import median
from math import isfinite
from xml.etree.ElementTree import ParseError, parse

from .gpx import blocks, describe_course, distance, elapsed, read_gpx, resample_course, sample_intervals
from .models import learn_curve, PaceModel, fit, fit_baseline, inclination_band, weighted_median
from .prediction import predict
from .settings import DISTANCE_CLASSES, INCLINATION_BANDS, PROFILE_FAMILIES, PROFILE_LABELS, REFERENCES, SAMPLING


def summarize(course):
    """Produire distance, dénivelés et profil altimétrique sur la grille retenue."""
    distance = ascent = descent = offset = 0
    profile = []
    for axis, points, samples in course:
        distance += axis[-1]
        intervals = list(sample_intervals((axis, points, samples)))
        positions = [intervals[0][2]] + [right for _, _, _, right in intervals]
        profile.append([[round(offset + position, 1), round(point[2], 1)]
                        for position, point in zip(positions, samples)])
        for start, end in zip(samples, samples[1:]):
            change = end[2] - start[2]
            ascent += max(change, 0)
            descent += max(-change, 0)
        offset = distance
    return dict(distance=distance, ascent=round(ascent), descent=round(descent), profile=profile)


def terrain_breakdown(course, model, timed=False):
    """Répartir distances et durées entre montée, plat et descente."""
    if hasattr(model, "for_course"):
        model = model.for_course(course)
    terrain = {name: dict(name=name, distance=0, actual=0 if timed else None,
                          estimated=0 if model else None)
               for name in ("Montée", "Plat", "Descente")}
    for length, grade, seconds in blocks(course):
        name = "Montée" if grade > 3 else "Descente" if grade < -3 else "Plat"
        row = terrain[name]
        row["distance"] += length
        if timed:
            row["actual"] += seconds
        if model:
            row["estimated"] += length * model(grade)
    return list(terrain.values())


def pause_summary(path, course):
    """Estimate stops on original points, keeping recording gaps separate."""
    root = parse(path).getroot()
    groups = [segment.findall("{*}trkpt") for segment in root.findall(".//{*}trkseg")]
    if not any(groups):
        groups = [route.findall("{*}rtept") for route in root.findall("{*}rte")]
    start_time, end_time = course[0][1][0][3], course[-1][1][-1][3]
    runs = []
    unobserved = 0
    previous_end = None
    for group in groups:
        points = []
        for node in group:
            date = datetime.fromisoformat(node.findtext("{*}time").strip().replace("Z", "+00:00"))
            seconds = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp()
            if start_time <= seconds <= end_time:
                points.append((float(node.attrib["lat"]), float(node.attrib["lon"]), seconds))
        if not points:
            continue
        if previous_end is not None:
            unobserved += max(0, points[0][2] - previous_end)
        runs.append(0)
        for first, second in zip(points, points[1:]):
            seconds = second[2] - first[2]
            if seconds <= 0:
                continue
            if seconds > 300:
                unobserved += seconds
            elif 3.6 * distance(first, second) / seconds <= 0.5:
                runs[-1] += seconds
                continue
            if runs[-1]:
                runs.append(0)
        previous_end = points[-1][2]
    stops = [seconds for seconds in runs if seconds >= 60]
    return dict(duration=sum(stops), count=len(stops), unobserved=unobserved)


def read_references(progress=None, store=None, directory=None):
    """Charger les références modifiées et restaurer les autres depuis le cache."""
    names, courses, pauses, skipped = [], [], [], []
    directory = REFERENCES if directory is None else directory
    sources = store.reference_sources(directory) if store else [
        dict(key=str(path), name=path.stem, path=path)
        for path in sorted(directory.iterdir()) if path.suffix.lower() == ".gpx" and path.is_file()]
    reused = 0
    seen = set()

    def parse_reference(data):
        course = read_gpx(BytesIO(data), timed=True)
        if elapsed(course) <= 0:
            raise ValueError("Durée nulle")
        return course, pause_summary(BytesIO(data), course)

    for index, source in enumerate(sources):
        if progress:
            progress("references", f"Référence · {source['name']}", 0.2 * index / max(1, len(sources)),
                     index, len(sources))
        try:
            if store:
                value, fingerprint, error, cached = store.load_reference(source, parse_reference)
                reused += int(cached)
                if error:
                    raise ValueError(error)
                if fingerprint in seen:
                    skipped.append(source["name"] + " — trace déjà présente")
                    continue
                seen.add(fingerprint)
                course, pause = value
            else:
                course, pause = parse_reference(source["path"].read_bytes())
        except (ValueError, KeyError, ParseError, OSError) as error:
            skipped.append(f"{source['name']} — {error}")
            continue
        names.append(source["name"])
        courses.append(course)
        pauses.append(pause)
    return names, courses, pauses, skipped, dict(reused=reused, total=len(sources),
        fingerprint=store.manifest(sources) if store else None)


def load_references(progress=None, store=None):
    names, courses, pauses, skipped, _ = read_references(progress, store)
    return validate_references(names, courses, pauses, skipped, progress)


def validate_references(names, courses, pauses, skipped, progress=None):
    """Valider à nouveau les modèles dès que l'ensemble des références change."""
    rows = []
    evaluation_cache = {}
    band_errors = [dict(label=label, distance=0, actual=0, current=0, experimental=0, count=0)
                   for label, _ in INCLINATION_BANDS]
    for i, (name, course) in enumerate(zip(names, courses)):
        if progress:
            progress("validation", f"Validation et test des inclinaisons · {name}",
                     0.2 + 0.55 * i / max(1, len(courses)), i, len(courses))
        others = courses[:i] + courses[i + 1:]
        fitted = fit(others, evaluation_cache=evaluation_cache) if others else None
        if progress:
            progress("validation", f"Courbe et validation du profil · {name}",
                     .2 + .55*(i+.2)/max(1,len(courses)), i, len(courses))
        model = fitted.for_course(course) if fitted else None
        terrain = terrain_breakdown(course, model, timed=True)
        estimated = sum(row["estimated"] for row in terrain) if model else None
        unassigned = max(0, elapsed(course) - sum(row["actual"] for row in terrain))
        baseline = fit_baseline([resample_course(other, 100) for other in others]) if others else None
        baseline_estimated = predict(resample_course(course, 100), baseline, 5000)[-1][1] if baseline else None
        if progress:
            progress("validation", f"Test des classes d’inclinaison · {name}",
                     .2 + .55*(i+.6)/max(1,len(courses)), i, len(courses))
        inclination = fitted.inclination_model() if fitted else None
        inclination_estimated = sum(length * inclination(grade) for length, grade, _ in blocks(course)) if inclination else None
        if inclination:
            for length, grade, seconds in blocks(course):
                if seconds <= 0:
                    continue
                band = band_errors[inclination_band(grade)]
                band["distance"] += length
                band["actual"] += seconds
                band["current"] += length * model(grade)
                band["experimental"] += length * inclination(grade)
                band["count"] += 1
        # Classement local : apprentissage strictement limité au même profil
        # ET à la même classe de distance, en excluant la course évaluée.
        descriptor = describe_course(course)
        peers = [other for other in others if all(describe_course(other)[key] == descriptor[key]
                 for key in ("profile", "distanceClass"))]
        group_curve = learn_curve(peers, [1.0] * len(peers)) if peers else None
        group_estimated = sum(length * group_curve(grade) for length, grade, _ in blocks(course)) if group_curve else None
        rows.append(dict(name=name, actual=elapsed(course), estimated=estimated,
                         groupEstimated=group_estimated, groupReferenceCount=len(peers),
                         inclinationEstimated=inclination_estimated,
                         baselineEstimated=baseline_estimated, classification=describe_course(course),
                         model=model.metadata if model else None,
                         terrain=terrain, unassigned=unassigned, pauses=pauses[i], **summarize(course)))
    errors = [abs(row["estimated"] / row["actual"] - 1) * 100
              for row in rows if row["estimated"] is not None]
    baseline_errors = [abs(row["baselineEstimated"] / row["actual"] - 1) * 100
                       for row in rows if row["baselineEstimated"] is not None]
    inclination_errors = [abs(row["inclinationEstimated"] / row["actual"] - 1) * 100
                          for row in rows if row["inclinationEstimated"] is not None]
    for band in band_errors:
        for key in ("current", "experimental"):
            band[key + "Error"] = (band[key] / band["actual"] - 1) * 100 if band["actual"] else None
    experiment = dict(courseCount=len(inclination_errors),
                      medianError=median(inclination_errors) if inclination_errors else None,
                      meanError=sum(inclination_errors) / len(inclination_errors) if inclination_errors else None,
                      bands=band_errors)
    if progress:
        progress("models", "Validation des références terminée · construction des modèles", 0.75, len(courses), len(courses))
    return courses, dict(courses=rows, skipped=skipped, error=median(errors) if errors else None,
                         baselineError=median(baseline_errors) if baseline_errors else None,
                         meanError=sum(errors) / len(errors) if errors else None,
                         inclinationTest=experiment,
                         baselineMeanError=sum(baseline_errors) / len(baseline_errors) if baseline_errors else None)


def geometry(course):
    """Restituer les coordonnées originales en conservant les coupures de segments."""
    return [[point[:2] for point in points] for _, points, _ in course]


def model_summary(courses, model=None):
    """Préparer une courbe et ses informations d'apprentissage pour le navigateur."""
    if model is None:
        model = fit(courses).global_model
    observations = model.observations
    low, high = model.grades[0], model.grades[-1]
    candidate = getattr(model, "candidate_curve", [])
    return dict(curve=[dict(grade=grade, speed=3.6 / model(grade))
                       for grade in range(low, high + 1)],
                candidateCurve=[dict(grade=grade, speed=3.6 / pace) for grade, pace in candidate],
                observations=observations,
                samples=sum(entry["count"] for entry in observations), **model.metadata)


def model_catalog(model, references, progress=None):
    """Construire les groupes de profil et de distance et leurs informations de validation."""
    result = []
    group_count = len(PROFILE_LABELS)*len(DISTANCE_CLASSES)
    for profile in PROFILE_LABELS:
        for index, (category, _, center) in enumerate(DISTANCE_CLASSES):
            if progress:
                progress("catalog", PROFILE_LABELS[profile] + " · " + DISTANCE_CLASSES[index][1],
                         0.8 + 0.18 * len(result) / group_count, len(result), group_count)
            exact = [i for i, d in enumerate(model.descriptors)
                     if d["profile"] == profile and d["distanceClass"] == category]
            target = median([model.descriptors[i]["distance"] for i in exact]) if exact else center * 1000
            selected = model.select(profile, category, target)
            chart = model_summary(model.courses, selected)
            chart["sampling"] = SAMPLING[profile][index]
            chart["references"] = [references[i]["name"] for i in exact]
            errors = [abs(references[i]["estimated"] / references[i]["actual"] - 1) * 100
                      for i in exact if references[i]["estimated"] is not None]
            chart["error"] = median(errors) if errors else None
            result.append(chart)
    return result


def predicted_sections(course, model):
    """Construire la chronologie commune à la carte et au profil de lecture."""
    if hasattr(model, "for_course"):
        model = model.for_course(course)
    sections = []
    distance = seconds = 0
    for segment, part in enumerate(course):
        for start, end, left, right in sample_intervals(part):
            length = right - left
            grade = 100 * (end[2] - start[2]) / length
            duration = length * model(grade)
            sections.append(dict(segment=segment, start=start[:3], end=end[:3],
                                 distance=distance, endDistance=distance + length,
                                 time=seconds, endTime=seconds + duration,
                                 grade=grade, speed=3.6 * length / duration))
            distance += length
            seconds += duration
    return sections


def choose_model(bank, course, choice):
    """Appliquer le choix du parcours et isoler ses métadonnées de requête.

    La copie conserve le type du modèle, notamment l'évaluation par classes
    de la variante expérimentale d'inclinaison."""
    descriptor = describe_course(course)
    if choice == "auto":
        model = bank.for_course(course)
        label = "Sélection automatique"
    elif choice == "global":
        model = bank.global_model
        label = "Modèle global · toutes les références"
    elif choice == "inclination":
        model = bank.inclination_model()
        label = "Test · modèle par classes d’inclinaison"
    else:
        parts = choice.split(":")
        if len(parts) != 2:
            raise ValueError("Modèle inconnu.")
        profile, category = parts
        profile = PROFILE_FAMILIES.get(profile, profile)
        if profile not in PROFILE_LABELS or category not in {row[0] for row in DISTANCE_CLASSES}:
            raise ValueError("Modèle inconnu.")
        model = bank.select_candidate(profile, category, descriptor["distance"], descriptor)
        label = "Choix manuel · " + model.metadata["profileLabel"] + " · " + model.metadata["distanceLabel"]
    # Selection metadata belongs to this request, including global-model requests.
    selected = copy(model)
    selected.metadata = dict(model.metadata, selection=choice, selectionLabel=label)
    return selected


def manual_model(course, mode, total_seconds=None, pace_seconds=None):
    """Une durée ou une allure imposée définit une chronologie à vitesse constante."""
    total_distance = sum(segment[0][-1] for segment in course)
    if mode == "total":
        if total_seconds is None:
            raise ValueError("Saisissez la durée totale prévue.")
        value = float(total_seconds)
        pace = value / total_distance
        label = "Durée totale saisie"
    elif mode == "pace":
        if pace_seconds is None:
            raise ValueError("Saisissez l'allure en minutes et secondes par kilomètre.")
        value = float(pace_seconds)
        pace = value / 1000
        label = "Allure saisie en min/km"
    else:
        raise ValueError("Mode de calcul inconnu.")
    if not isfinite(value) or value <= 0:
        raise ValueError("Saisissez une durée ou une allure strictement positive.")
    return PaceModel([(-50, pace), (50, pace)], [], dict(scope="manual", selection=mode,
                     selectionLabel=label, status=label, localWeight=0))


def estimate_pauses(total, model, references):
    """Estimer la part de pauses déjà incluse dans la durée totale prédite.

    La médiane des ratios de pauses est pondérée par la couverture des
    enregistrements, puis combinée au profil lorsque le modèle le prévoit.
    Les pauses sont une décomposition du total appris, pas un ajout au total."""
    observations = []
    for i, reference in enumerate(references):
        actual = reference["actual"]
        pause = reference["pauses"]
        coverage = max(0, 1 - pause["unobserved"] / actual)
        if coverage > 0:
            observations.append((i, min(1, max(0, pause["duration"] / actual)), coverage))
    if not observations:
        return dict(duration=None, fraction=None, referenceCount=0, unknownFraction=1,
                    status="Estimation indisponible · enregistrements insuffisants")
    global_fraction = weighted_median([(fraction, coverage) for _, fraction, coverage in observations])
    weights = dict(zip(model.metadata.get("indices", []), model.metadata.get("referenceWeights", [])))
    local = [(fraction, coverage * weights[i]) for i, fraction, coverage in observations if weights.get(i, 0) > 0]
    blend = model.metadata.get("localWeight", 0) if model.metadata.get("scope") == "segmented" and local else 0
    fraction = global_fraction
    if blend:
        fraction = (1 - blend) * global_fraction + blend * weighted_median(local)
    unknown = weighted_median([(1 - coverage, 1) for _, _, coverage in observations])
    return dict(duration=total * fraction, fraction=fraction,
                referenceCount=len(local) if blend else len(observations), localWeight=blend,
                unknownFraction=unknown,
                status="Pauses observées du profil et modèle global" if blend else "Pauses observées · toutes les références")
