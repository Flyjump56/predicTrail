"""Optimisation sans rééchantillonnage des imports GPX manuels."""
from io import BytesIO
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from .gpx import read_gpx, elapsed
from .settings import MAX_UPLOAD

MAX_SOURCE = 100 * 1024 * 1024


def convert_gpx(data, mode="compact"):
    """Garder chaque point, segment, altitude et horaire dans leur ordre initial."""
    if mode not in ("compact", "simulation", "original"):
        raise ValueError("Mode de conversion GPX inconnu.")
    if not data or len(data) > MAX_SOURCE:
        raise ValueError("Le GPX source est limité à 100 Mio.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Les déclarations DTD et entités ne sont pas acceptées.")
    root = ET.fromstring(data)
    if root.tag.split("}")[-1] != "gpx":
        raise ValueError("Le document doit être un fichier GPX.")
    points = root.findall(".//{*}trkpt") or root.findall(".//{*}rtept")
    # Préfixes déterministes courts, sans modifier le registre global partagé.
    removed = 0
    for node in root.iter():
        if node.text is not None and not node.text.strip():
            node.text = None
        if node.tail is not None and not node.tail.strip():
            node.tail = None
        if mode == "simulation":
            for child in list(node):
                if child.tag.split("}")[-1] == "extensions":
                    node.remove(child)
                    removed += 1
    candidate = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    # Une conversion XML peut agrandir un document déjà compact : garder la source.
    result = candidate if mode != "original" and len(candidate) < len(data) else data
    if result is data:
        removed = 0
    read_gpx(BytesIO(result))
    recorded_error = None
    recorded_start = None
    try:
        course = read_gpx(BytesIO(result), timed=True)
        recorded_start = datetime.fromtimestamp(course[0][1][0][3], timezone.utc).isoformat()
        if elapsed(course) <= 0:
            raise ValueError("La durée enregistrée doit être positive.")
    except (ValueError, KeyError, OverflowError) as error:
        recorded_error = str(error)
    return result, dict(originalBytes=len(data), convertedBytes=len(result),
        savedBytes=len(data)-len(result), gainPercent=round(100*(1-len(result)/len(data)), 1),
        pointCount=len(points), removedExtensions=removed, mode=mode,
        optimized=result is not data, importable=len(result) <= MAX_UPLOAD,
        recordedCompatible=recorded_error is None, recordedError=recorded_error, recordedStart=recorded_start,
        optimizable=len(candidate) < len(data))
