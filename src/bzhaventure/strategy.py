"""Scénarios d’allure : transformation des chronologies sans réapprentissage."""
from bisect import bisect_left
from copy import deepcopy
from math import isfinite


def validate_strategy(options):
    if not isinstance(options, dict):
        raise ValueError("Stratégie de simulation incorrecte.")
    result = {}
    for key, low, high in [("adjustmentPercent",-50,100),("splitPercent",0,40),("climbPercent",-50,100)]:
        value = options.get(key, 0)
        if isinstance(value, bool) or not isinstance(value,(float,int)) or not isfinite(value) or not low <= value <= high:
            label = {"adjustmentPercent":"Évolution de la durée", "splitPercent":"Intensité du split", "climbPercent":"Évolution du temps en montée"}[key]
            raise ValueError(f"{label} : valeur attendue entre {low} et {high} %.")
        result[key] = float(value)
    result["split"] = options.get("split", "even")
    if result["split"] not in ("even","positive","negative"):
        raise ValueError("Split de simulation inconnu.")
    return result


def apply_strategy(data, options):
    """Recalculer sections, repères et export sur une seule chronologie cohérente.

    Les splits allouent une part de la durée à chaque moitié de distance. Les
    variations locales du modèle restent proportionnelles au sein d’une moitié.
    L’ajustement des montées puis le pourcentage global sont appliqués ensuite.
    """
    config = validate_strategy(options)
    if data.get("model",{}).get("scope") == "recorded":
        raise ValueError("Les stratégies ne modifient pas les temps enregistrés. Choisissez une méthode de simulation.")
    result = deepcopy(data)
    baseline = data["duration"]
    halfway = data["distance"]/2
    pieces = []
    for section in data["sections"]:
        cuts = [section["distance"],section["endDistance"]]
        if cuts[0] < halfway < cuts[1]: cuts.insert(1,halfway)
        for left,right in zip(cuts,cuts[1:]):
            fraction = lambda x: (x-section["distance"])/(section["endDistance"]-section["distance"])
            a,b = fraction(left),fraction(right)
            point = lambda f: [x+(y-x)*f for x,y in zip(section["start"],section["end"])]
            old_start = section["time"]+(section["endTime"]-section["time"])*a
            old_end = section["time"]+(section["endTime"]-section["time"])*b
            pieces.append(dict(section, start=point(a), end=point(b), distance=left,endDistance=right,
                               time=old_start,endTime=old_end,half=int(left>=halfway)))
    if not pieces or baseline <= 0: raise ValueError("Chronologie inexploitable pour la stratégie.")
    factors = [1.0,1.0]
    if config["split"] != "even" and config["splitPercent"]:
        intensity = config["splitPercent"]/100
        first = (1-intensity)/2 if config["split"]=="positive" else (1+intensity)/2
        durations = [sum(s["endTime"]-s["time"] for s in pieces if s["half"]==h) for h in (0,1)]
        factors = [baseline*share/duration for share,duration in zip((first,1-first),durations)]
    old_ends, mappings, current = [], [], 0.0
    for piece in pieces:
        old_start,old_end = piece["time"],piece["endTime"]
        factor = factors[piece.pop("half")]
        if piece["grade"] > 3: factor *= 1+config["climbPercent"]/100
        duration = (old_end-old_start)*factor*(1+config["adjustmentPercent"]/100)
        old_ends.append(old_end);mappings.append((old_start,old_end,current,current+duration))
        piece.update(time=current,endTime=current+duration,speed=3.6*(piece["endDistance"]-piece["distance"])/duration)
        current += duration
    def remap(seconds):
        i = min(len(mappings)-1,bisect_left(old_ends,seconds))
        a,b,c,d = mappings[i]
        return c+(d-c)*max(0,min(1,(seconds-a)/max(1e-12,b-a)))
    result["sections"],result["duration"] = pieces,current
    result["marks"] = [(m[0],remap(m[1]),*m[2:]) for m in data["marks"]]
    result["exportPoints"] = [[[p[0],p[1],p[2],remap(p[3])] for p in segment] for segment in data["exportPoints"]]
    if result.get("pauses",{}).get("duration") is not None:
        result["pauses"]["duration"] *= current/baseline
        result["movingDuration"] = current-result["pauses"]["duration"]
    for terrain in result.get("terrain",[]):
        terrain["estimated"] = sum(s["endTime"]-s["time"] for s in pieces
            if ("Montée" if s["grade"]>3 else "Descente" if s["grade"]< -3 else "Plat")==terrain["name"])
    label = {"even":"Allure régulière","positive":"Split positif","negative":"Split négatif"}[config["split"]]
    if config["split"]!="even": label += f" {config['splitPercent']:g} %"
    label += f" · durée {config['adjustmentPercent']:+g} % · montées {config['climbPercent']:+g} %"
    change = (current/baseline-1)*100
    if abs(change) < 1e-9: change = 0.0
    label += f" · variation finale {change:+.1f} %"
    result["strategy"] = dict(config,baselineDuration=baseline,actualChangePercent=change,label=label)
    return result
