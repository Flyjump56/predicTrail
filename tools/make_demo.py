"""Exemples synthétiques clairement identifiés, sans activité personnelle."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import math
import xml.etree.ElementTree as ET

def make_demo(target):
    target=Path(target);target.mkdir(parents=True,exist_ok=True)
    for n in (1,2,3):
        root=ET.Element("gpx",version="1.1",creator="PrédicTrail - démonstration fictive",xmlns="http://www.topografix.com/GPX/1/1")
        metadata=ET.SubElement(root,"metadata");ET.SubElement(metadata,"desc").text="Données générées pour démonstration. Aucun enregistrement sportif réel."
        track=ET.SubElement(root,"trk");ET.SubElement(track,"name").text=f"Démonstration fictive {n}"
        segment=ET.SubElement(track,"trkseg");start=datetime(2026,1,n,7,tzinfo=timezone.utc)
        for i in range(601):
            point=ET.SubElement(segment,"trkpt",lat=str(48+n*.01+i*.0002),lon=str(-4+i*.00008))
            ET.SubElement(point,"ele").text=str(round(40+n*10+15*math.sin(i/30),2))
            ET.SubElement(point,"time").text=(start+timedelta(seconds=i*(8+n))).isoformat().replace("+00:00","Z")
        ET.ElementTree(root).write(target/f"Demonstration-fictive-{n}.gpx",encoding="utf-8",xml_declaration=True)

if __name__=="__main__":
    import sys
    make_demo(sys.argv[1] if len(sys.argv)>1 else "build/demo")
