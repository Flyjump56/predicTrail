"""Isoler les calculs longs pour arrêter réellement une validation bloquée."""
import multiprocessing
from time import monotonic

from .analysis import model_catalog, model_summary, validate_references
from .models import fit

STALL_SECONDS = 180
TOTAL_SECONDS = 1800


def build_models(names, courses, pauses, skipped, progress):
    courses, references = validate_references(names, courses, pauses, skipped, progress)
    progress("models", "Construction de la banque des modèles", .76)
    model = fit(courses)
    references["model"] = model_summary(courses, model.global_model)
    references["models"] = model_catalog(model, references["courses"], progress)
    progress("models", "Construction du modèle par inclinaison", .98)
    references["inclinationModel"] = model_summary(courses, model.inclination_model())
    return model, references


def validation_worker(connection, arguments):
    try:
        def progress(*values):
            connection.send(("progress", values))
        connection.send(("result", build_models(*arguments, progress)))
    except Exception as error:
        connection.send(("error", str(error)))
    finally:
        connection.close()


def supervised_build(arguments, progress, stall_seconds=STALL_SECONDS,
                     total_seconds=TOTAL_SECONDS, worker=validation_worker):
    """Publier la progression et tuer le processus privé si un délai est dépassé.

    Aucun accès SQLite dans ce processus : un arrêt ne publie pas de cache partiel.
    Le serveur HTTP et les modes manuels restent disponibles pendant le calcul.
    """
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(child, arguments), daemon=True)
    started = updated = monotonic()
    try:
        process.start()
        child.close()
        while True:
            if parent.poll(.2):
                try:
                    kind, payload = parent.recv()
                except EOFError:
                    raise ValueError("Le processus de validation s’est interrompu sans résultat.") from None
                updated = monotonic()
                if kind == "result":
                    return payload
                if kind == "error":
                    raise ValueError(payload)
                progress(*payload)
            now = monotonic()
            if now-updated > stall_seconds or now-started > total_seconds:
                raise ValueError("Validation interrompue par la surveillance : délai sans progression "
                                 "ou durée maximale dépassé. Réduisez les références sélectionnées puis relancez.")
            if not process.is_alive() and not parent.poll():
                raise ValueError("Le processus de validation s’est arrêté sans résultat.")
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            process.close()
        parent.close()
        child.close()
