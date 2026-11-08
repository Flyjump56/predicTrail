"""Apprentissage des courbes d'allure et validation des modèles de groupe."""
from bisect import bisect_left, bisect_right
from collections import defaultdict
from math import exp, log, sqrt
from statistics import median, stdev

from .gpx import blocks, describe_course, elapsed, interpolate, resample_course
from .settings import DISTANCE_CLASSES, INCLINATION_BANDS, PROFILE_LABELS, SAMPLING


def inclination_band(grade):
    """Associer la pente à l'une des onze classes, avec un plat de −3 à +3 % inclus."""
    if grade < -3:
        return bisect_right([-40, -25, -15, -8], grade)
    if grade > 3:
        return 6 + bisect_left([8, 15, 25, 40], grade)
    return 5


def fit_baseline(courses):
    """Reproduire le modèle historique par classes de pente de cinq points."""
    bins = defaultdict(list)
    for course in courses:
        for length, grade, seconds in blocks(course):
            pace = seconds / length
            if 0.1 <= pace <= 6:
                bins[round(grade / 5) * 5].append(pace)
    curve = sorted((grade, median(values)) for grade, values in bins.items() if len(values) >= 10)
    if not curve:
        raise ValueError("Trop peu de passages chronométrés exploitables.")
    grades, paces = zip(*curve)
    values = [(pace,) for pace in paces]

    def pace_at(grade):
        return interpolate(grades, values, min(grades[-1], max(grades[0], grade)))[0]

    # Recalage sur le temps écoulé des courses, pauses comprises.
    scale = median(elapsed(course) / sum(length * pace_at(grade)
                                        for length, grade, _ in blocks(course))
                   for course in courses)
    observations = [dict(grade=grade, speed=3.6 / pace, count=len(bins[grade])) for grade, pace in curve]
    return PaceModel([(grade, pace * scale) for grade, pace in curve], observations, {})


def weighted_median(values):
    """Calculer une médiane pondérée pour limiter l'influence des valeurs extrêmes."""
    ordered = sorted(values)
    halfway = sum(weight for _, weight in ordered) / 2
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= halfway:
            return value
    raise ValueError("Aucune observation pondérée disponible.")


class PaceModel:
    """Courbe d'allure en secondes par mètre, interpolée selon la pente."""
    def __init__(self, curve, observations, metadata):
        self.curve = curve
        self.observations = observations
        self.metadata = metadata
        self.grades = [grade for grade, _ in curve]
        self.values = [(pace,) for _, pace in curve]

    def __call__(self, grade):
        bounded = max(self.grades[0], min(self.grades[-1], grade))
        return interpolate(self.grades, self.values, bounded)[0]


class InclinationModel(PaceModel):
    """Variante expérimentale avec une allure constante dans chaque classe de pente."""
    def __call__(self, grade):
        return self.curve[inclination_band(grade)][1]


def fit_inclination(courses, fallback=None):
    """Experimental independent ascent/descent bands, regularized by coverage."""
    if fallback is None:
        fallback = fit_baseline([resample_course(course, 100) for course in courses])
    groups = [[] for _ in INCLINATION_BANDS]
    for index, course in enumerate(courses):
        total = sum(segment[0][-1] for segment in course)
        for length, grade, seconds in blocks(course):
            pace = seconds / length
            if length >= 10 and 0.1 <= pace <= 6:
                groups[inclination_band(grade)].append((pace, length / total, length, index))
    curve, observations, summaries = [], [], []
    for (label, center), entries in zip(INCLINATION_BANDS, groups):
        covered = sum(length for _, _, length, _ in entries)
        learned = len(entries) >= 10 and covered >= 300
        pace = fallback(center)
        observed = None
        if learned:
            observed = weighted_median([(value, weight) for value, weight, _, _ in entries])
            blend = covered / (covered + 3000)
            pace = (1 - blend) * pace + blend * observed
            observations.append(dict(grade=center, speed=3.6 / observed, count=len(entries)))
        curve.append((center, pace))
        summaries.append(dict(label=label, grade=center, distance=covered, count=len(entries),
                              courseCount=len({index for _, _, _, index in entries}), learned=learned))
    provisional = InclinationModel(curve, observations, {})
    ratios = [(elapsed(course) / sum(length * provisional(grade) for length, grade, _ in blocks(course)), 1)
              for course in courses]
    scale = weighted_median(ratios)
    curve = [(grade, pace * scale) for grade, pace in curve]
    for summary, (_, pace) in zip(summaries, curve):
        summary["speed"] = 3.6 / pace
    return InclinationModel(curve, observations, dict(scope="inclination", count=len(courses),
                            exactCount=len(courses), localWeight=1, bands=summaries,
                            status="Expérimental · classes d’inclinaison distinctes en montée et descente"))


def learn_curve(courses, weights):
    """Apprendre une courbe pondérée par la distance représentée par chaque portion.

    Le recalage final utilise les durées écoulées, pauses comprises. Une
    densité d'enregistrement plus forte ne donne pas davantage de poids
    à une même longueur de parcours."""
    bins = defaultdict(list)
    for course, weight in zip(courses, weights):
        total = sum(segment[0][-1] for segment in course)
        for length, grade, seconds in blocks(course):
            pace = seconds / length
            if length >= 10 and 0.1 <= pace <= 6:
                bins[round(grade / 5) * 5].append((pace, weight * length / total, length))
    observations = []
    for grade, entries in sorted(bins.items()):
        if len(entries) >= 10 and sum(length for _, _, length in entries) >= 300:
            pace = weighted_median([(pace, weight) for pace, weight, _ in entries])
            observations.append(dict(grade=grade, speed=3.6 / pace, count=len(entries)))
    if not observations:
        return None
    curve = [(entry["grade"], 3.6 / entry["speed"]) for entry in observations]
    provisional = PaceModel(curve, observations, {})
    ratios = []
    for course, weight in zip(courses, weights):
        estimated = sum(length * provisional(grade) for length, grade, _ in blocks(course))
        ratios.append((elapsed(course) / estimated, weight))
    scale = weighted_median(ratios)
    return PaceModel([(grade, pace * scale) for grade, pace in curve], observations, {})


def relief_similarity(reference, target):
    """Proximité continue du relief, complémentaire au groupe et à la distance.

    La composition des ascensions compte même à densité de D+ identique.
    Une similarité faible réduit aussi le poids du groupe face au repli global.
    """
    density = abs(log((reference["ascentDensity"]+1)/(target["ascentDensity"]+1)))
    frequency = abs(log((reference["climbsPer10Km"]+1)/(target["climbsPer10Km"]+1)))
    composition = sum(abs(reference["climbShares"][kind]-target["climbShares"][kind])
                      for kind in ("small", "intermediate", "large"))
    length = abs(log((reference["medianClimbLength"]+100)/(target["medianClimbLength"]+100)))
    amplitude = abs(log((reference["medianClimbGain"]+25)/(target["medianClimbGain"]+25)))
    return max(.05, exp(-.6*density - .25*frequency - 1.2*composition - .25*length - .25*amplitude))


class SegmentedModel:
    """Distance/profile models shrunk toward a common curve for small groups."""
    def __init__(self, courses, validate=True, evaluation_cache=None):
        self.courses = courses
        self.descriptors = [describe_course(course) for course in courses]
        self.global_model = learn_curve(courses, [1] * len(courses))
        if self.global_model is None:
            raise ValueError("Trop peu de passages chronométrés exploitables.")
        self.global_model.metadata = dict(scope="global", count=len(courses), exactCount=len(courses),
                                          localWeight=1, status="Toutes les références")
        self.baseline_model = fit_baseline([resample_course(course, 100) for course in courses])
        self.validate = validate
        self.validation = {}
        self.evaluation_cache = evaluation_cache if evaluation_cache is not None else {}
        self._inclination_model = None

    def __getstate__(self):
        """Conserver le modèle déployé sans les banques temporaires de validation."""
        state = dict(self.__dict__)
        state["evaluation_cache"] = {}
        return state

    def inclination_model(self):
        if self._inclination_model is None:
            self._inclination_model = fit_inclination(self.courses, self.baseline_model)
        return self._inclination_model

    def __call__(self, grade):
        return self.global_model(grade)

    def select(self, profile, distance_class, target_distance, target_descriptor=None):
        """Retenir le candidat ou le repli selon la validation du profil."""
        candidate = self.select_candidate(profile, distance_class, target_distance, target_descriptor)
        if not self.validate or not candidate.metadata["count"]:
            return candidate
        assessment = self.validate_profile(profile)
        candidate.metadata.update(assessment)
        if assessment["useSegmented"]:
            return candidate
        metadata = dict(candidate.metadata, localWeight=0,
                        status="Validation du profil · modèle global à 100 m retenu")
        result = PaceModel(self.baseline_model.curve, self.baseline_model.observations, metadata)
        result.candidate_curve = candidate.curve
        return result

    def validate_profile(self, profile):
        """Comparer les candidats par validation interne sur les seules références.

        La marge d'une erreur standard favorise un choix conservateur lorsque
        les différences entre modèles varient fortement d'une course à l'autre."""
        if profile in self.validation:
            return self.validation[profile]
        selected = [i for i, d in enumerate(self.descriptors) if d["profile"] == profile]
        if len(selected) < 3:
            assessment = dict(useSegmented=True, validationCount=len(selected),
                              candidateError=None, fallbackError=None)
        else:
            candidate_errors, fallback_errors = [], []
            for i in selected:
                others = self.courses[:i] + self.courses[i + 1:]
                key = tuple(id(course) for course in others)
                if key not in self.evaluation_cache:
                    self.evaluation_cache[key] = SegmentedModel(others, validate=False)
                fitted = self.evaluation_cache[key]
                candidate = fitted.for_course(self.courses[i])
                actual = elapsed(self.courses[i])
                predicted = sum(length * candidate(grade) for length, grade, _ in blocks(self.courses[i]))
                fallback = sum(length * fitted.baseline_model(grade)
                               for length, grade, _ in blocks(self.courses[i]))
                candidate_errors.append(abs(predicted / actual - 1) * 100)
                fallback_errors.append(abs(fallback / actual - 1) * 100)
            candidate_error = sum(candidate_errors) / len(candidate_errors)
            fallback_error = sum(fallback_errors) / len(fallback_errors)
            differences = [candidate - fallback for candidate, fallback in zip(candidate_errors, fallback_errors)]
            margin = stdev(differences) / sqrt(len(differences))
            assessment = dict(useSegmented=candidate_error + margin < fallback_error,
                              validationCount=len(selected), candidateError=candidate_error,
                              fallbackError=fallback_error, validationMargin=margin)
        self.validation[profile] = assessment
        return assessment

    def select_candidate(self, profile, distance_class, target_distance, target_descriptor=None):
        """Construire le candidat du groupe, régularisé par la courbe globale."""
        selected = [i for i, descriptor in enumerate(self.descriptors) if descriptor["profile"] == profile]
        exact = [i for i in selected if self.descriptors[i]["distanceClass"] == distance_class]
        metadata = dict(scope="segmented", profile=profile, profileLabel=PROFILE_LABELS[profile],
                        distanceClass=distance_class,
                        distanceLabel=next(label for key, label, _ in DISTANCE_CLASSES if key == distance_class),
                        count=len(selected), exactCount=len(exact), localWeight=0,
                        sampling=SAMPLING[profile][next(i for i, row in enumerate(DISTANCE_CLASSES) if row[0] == distance_class)],
                        indices=selected)
        if target_descriptor and target_descriptor["profile"] == profile:
            metadata["sampling"] = target_descriptor["sampling"]
        if not selected:
            metadata["status"] = "Aucune référence de ce profil · modèle global"
            return PaceModel(self.global_model.curve, [], metadata)
        if target_descriptor is None:
            representative = min(exact or selected, key=lambda i: abs(log(self.descriptors[i]["distance"]/target_distance)))
            target_descriptor = self.descriptors[representative]
        similarities = [relief_similarity(self.descriptors[i], target_descriptor) for i in selected]
        weights = [exp(-abs(log(self.descriptors[i]["distance"] / target_distance)) / 0.7) *
                   (1.5 if i in exact else 1) * similarity for i, similarity in zip(selected, similarities)]
        metadata.update(morphologyWeighted=True, morphologySimilarities=similarities,
                        targetAscentDensity=target_descriptor["ascentDensity"],
                        targetClimbShares=target_descriptor["climbShares"],
                        targetClimbsPer10Km=target_descriptor["climbsPer10Km"],
                        targetMedianClimbGain=target_descriptor["medianClimbGain"],
                        targetMedianClimbLength=target_descriptor["medianClimbLength"])
        metadata["referenceWeights"] = weights
        local = learn_curve([self.courses[i] for i in selected], weights)
        if local is None:
            metadata["status"] = "Observations insuffisantes · modèle global"
            return PaceModel(self.global_model.curve, [], metadata)
        support = sum(weights)
        blend = min(support / (support + 2), 0.45 if len(exact) == 1 else 0.35 if not exact else 0.8)
        grades = sorted(set(self.global_model.grades + local.grades))
        curve = [(grade, (1 - blend) * self.global_model(grade) + blend * local(grade)) for grade in grades]
        # Estimate the distance effect within the same relief profile, with a
        # regularized slope and median intercept to limit individual race effects.
        provisional = PaceModel(curve, local.observations, metadata)
        residuals = []
        for index, weight in zip(selected, weights):
            estimated = sum(length * provisional(grade) for length, grade, _ in blocks(self.courses[index]))
            residuals.append((log(self.descriptors[index]["distance"]),
                              log(elapsed(self.courses[index]) / estimated), weight))
        weight_sum = sum(weight for _, _, weight in residuals)
        center = sum(x * weight for x, _, weight in residuals) / weight_sum
        mean_y = sum(y * weight for _, y, weight in residuals) / weight_sum
        variance = sum(weight * (x - center) ** 2 for x, _, weight in residuals) / weight_sum
        covariance = sum(weight * (x - center) * (y - mean_y) for x, y, weight in residuals) / weight_sum
        slope = max(-1, min(1, covariance / (variance + 0.2)))
        intercept = weighted_median([(y - slope * (x - center), weight) for x, y, weight in residuals])
        correction = exp(blend * (intercept + slope * (log(target_distance) - center)))
        curve = [(grade, pace * correction) for grade, pace in curve]
        metadata.update(localWeight=blend, status="Modèle de groupe régularisé" if len(exact) >= 2 else
                        "Groupe peu représenté · appui renforcé sur le modèle global",
                        distanceExponent=slope, distanceCorrection=correction)
        return PaceModel(curve, local.observations, metadata)

    def for_course(self, course):
        descriptor = describe_course(course)
        return self.select(descriptor["profile"], descriptor["distanceClass"], descriptor["distance"], descriptor)


def fit(courses, evaluation_cache=None):
    """Construire la banque de modèles à partir des seules courses fournies."""
    return SegmentedModel(courses, evaluation_cache=evaluation_cache)
