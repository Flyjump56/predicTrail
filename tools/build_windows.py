"""Construire un paquet autonome sans références, historique ou données privées."""
from pathlib import Path
import subprocess,sys,shutil,json,hashlib,zipfile
from make_demo import make_demo
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/"src"))
from bzhaventure import __version__
make_demo(root/"build"/"demo")
command=[sys.executable,"-m","PyInstaller","--noconfirm","--onedir","--console","--name","PredicTrail",
    "--paths",str(root/"src"),"--distpath",str(root/"dist"),"--workpath",str(root/"build"/"pyinstaller"),
    "--specpath",str(root/"build"),"--collect-all","garminconnect","--collect-all","garth",
    "--collect-all","pydantic","--collect-all","pydantic_core","--copy-metadata","garminconnect",
    "--add-data",str(root/"src"/"bzhaventure"/"web")+";bzhaventure/web",
    "--add-data",str(root/"assets"/"logo-bzhaventure.png")+";assets",
    "--add-data",str(root/"assets"/"thème.jpg")+";assets",
    "--add-data",str(root/"build"/"demo")+";demo"]
# Les fonctions de version de cache lisent les modules sources.
for source in sorted((root/"src"/"bzhaventure").glob("*.py")):
    command += ["--add-data",str(source)+";bzhaventure"]
command += [str(root/"tools"/"windows_entry.py")]
subprocess.run(command,cwd=root,check=True)
package=root/"dist"/"PredicTrail"
# Les mêmes trois guides sont livrés avec les sources et le paquet autonome.
shutil.copytree(root/"docs",package/"docs",dirs_exist_ok=True)
(package/"LIRE-MOI.md").write_text("""# PrédicTrail — par BZHAventure

Décompresser entièrement le ZIP, puis ouvrir PredicTrail.exe.
Conserver le dossier _internal et la fenêtre de lancement ouverte.
Python et les dépendances Garmin sont inclus ; les exemples sont fictifs.
Les données personnelles se trouvent dans %LOCALAPPDATA%/PredicTrail.

- [Architecture, déploiement et démarrage](docs/ARCHITECTURE.md)
- [Fonctionnel, sauvegarde et restauration](docs/FONCTIONNEL.md)
- [Modèle](docs/MODELE.md)

Avant une mise à jour, créer une sauvegarde complète depuis l’application
et conserver son ZIP sur un autre support.
""",encoding="utf-8")
shutil.copy2(root/"requirements-windows.lock",package/"DEPENDANCES.txt")
archive=root/"dist"/f"PredicTrail-{__version__}-Windows-x64.zip"
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as output:
    for path in sorted(package.rglob("*")):
        if path.is_file():output.write(path,path.relative_to(package.parent))
checksum=hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix(".sha256").write_text(checksum+"  "+archive.name+"\n",encoding="ascii")
print(json.dumps(dict(archive=str(archive),sha256=checksum,bytes=archive.stat().st_size)))
