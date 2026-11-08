"""Interface en ligne de commande pour prédire une trace ou valider les références."""
import argparse
from math import isfinite
from pathlib import Path
from statistics import median
import webbrowser
import xml.etree.ElementTree as ET

from .gpx import elapsed, read_gpx
from .models import fit
from .prediction import predict
from .reporting import duration, write_map
from .settings import REFERENCES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, nargs="?", help="GPX du parcours à prédire")
    parser.add_argument("--references", type=Path, default=REFERENCES)
    parser.add_argument("--pas-km", type=float, default=5)
    parser.add_argument("--sortie", type=Path)
    parser.add_argument("--validation", action="store_true", help="Tester chaque course à tour de rôle")
    parser.add_argument("--sans-navigateur", action="store_true")
    args = parser.parse_args()
    if not isfinite(args.pas_km) or args.pas_km < 0.1:
        parser.error("--pas-km doit être au moins égal à 0,1.")
    try:
        paths, courses = [], []
        for path in sorted(args.references.iterdir()):
            if path.suffix.lower() != ".gpx" or not path.is_file():
                continue
            try:
                course = read_gpx(path, timed=True)
                if elapsed(course) <= 0:
                    raise ValueError("Durée nulle.")
            except (ValueError, ET.ParseError, KeyError, OSError) as error:
                print(f"Référence écartée ({path.name}) : {error}")
                continue
            paths.append(path)
            courses.append(course)
        if not courses:
            raise ValueError("Aucune course de référence utilisable.")
        if args.validation:
            if len(courses) < 2:
                raise ValueError("Deux courses de référence au minimum pour la validation.")
            errors = []
            evaluation_cache = {}
            for i, (path, course) in enumerate(zip(paths, courses)):
                model = fit(courses[:i] + courses[i + 1:], evaluation_cache=evaluation_cache)
                estimated = predict(course, model, args.pas_km * 1000)[-1][1]
                actual = elapsed(course)
                error = (estimated / actual - 1) * 100
                errors.append(abs(error))
                print(f"{path.stem:24} GPX {duration(actual)}  estimé {duration(estimated)}  {error:+.1f} %")
            print(f"Erreur absolue médiane : {median(errors):.1f} %")
            if args.trace is None:
                return
        if args.trace is None:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            try:
                selected = filedialog.askopenfilename(title="Choisir le parcours GPX à prédire",
                                                      filetypes=[("Trace GPX", "*.gpx")])
            finally:
                root.destroy()
            if not selected:
                return
            args.trace = Path(selected)
        segments = read_gpx(args.trace)
        selected = [course for path, course in zip(paths, courses)
                    if path.resolve() != args.trace.resolve()]
        if not selected:
            raise ValueError("Aucune autre course de référence disponible pour cette trace.")
        marks = predict(segments, fit(selected), args.pas_km * 1000)
        output = args.sortie or Path(f"{args.trace.stem}-prediction.html")
        if output.suffix.lower() != ".html":
            raise ValueError("Le fichier de sortie doit avoir l'extension .html.")
        write_map(output, args.trace.stem, segments, marks, len(selected))
        print(f"{marks[-1][0] / 1000:.2f} km · {duration(marks[-1][1])} estimées")
        print(output.resolve())
        if not args.sans_navigateur:
            webbrowser.open(output.resolve().as_uri())
    except (ValueError, ET.ParseError, KeyError, OSError) as error:
        parser.exit(1, f"Erreur : {error}\n")
