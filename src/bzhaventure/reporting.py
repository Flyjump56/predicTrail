"""Rapport HTML autonome produit par l'interface en ligne de commande."""
from html import escape
import json


def duration(seconds):
    hours, remainder = divmod(round(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def write_map(output, name, segments, marks, references):
    track = [[point[:2] for point in points] for _, points, _ in segments]
    pins = []
    rows = []
    for meters, seconds, lat, lon, elevation, label in marks:
        km = f"{meters / 1000:.2f}"
        time = duration(seconds)
        pins.append([lat, lon, f"{escape(label)} · {km} km<br>{time} écoulées · {elevation:.0f} m"])
        rows.append(f"<tr><td>{escape(label)}</td><td>{km}</td><td>{time}</td><td>{elevation:.0f}</td></tr>")
    meters, seconds, *_ = marks[-1]
    output.write_text(f"""<!doctype html>
<html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prévision ultra-trail</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body {{font:16px system-ui; margin:24px auto; max-width:1100px; padding:0 16px; color:#182d32}}
#map {{height:55vh; min-height:280px; background:#edf4f3}}
table {{border-collapse:collapse; width:100%; margin:18px 0}}
th,td {{padding:8px; border-bottom:1px solid #d6e3e2; text-align:left}}
</style>
<h1>{escape(name)}</h1>
<p><strong>{meters / 1000:.2f} km · {duration(seconds)} estimées</strong>
 · Modèle ajusté sur {references} courses chronométrées</p>
<div id="map">La carte nécessite une connexion Internet.</div>
<table><caption>Temps de passage cumulés depuis le départ</caption>
<thead><tr><th>Repère</th><th>Distance (km)</th><th>Temps estimé</th><th>Altitude (m)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
if (window.L) {{
  document.getElementById("map").textContent = "";
  const map = L.map("map");
  const line = L.polyline({json.dumps(track)}, {{color:"#087e74", weight:4}}).addTo(map);
  map.fitBounds(line.getBounds(), {{padding:[24,24], maxZoom:16}});
  L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
    maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    referrerPolicy:"strict-origin-when-cross-origin"
  }}).addTo(map);
  for (const [lat, lon, text] of {json.dumps(pins)}) {{
    L.circleMarker([lat, lon], {{radius:6, color:"#fff", fillColor:"#ba4727", fillOpacity:1}})
      .addTo(map).bindTooltip(text);
  }}
}}
</script></html>""", encoding="utf-8")
