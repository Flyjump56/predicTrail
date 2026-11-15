"""Sauvegardes ZIP vérifiées, instantanés SQLite et restauration avec retour arrière."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import uuid
import zipfile
from . import __version__

MAX_ARCHIVE = 2 * 1024**3
MAX_EXPANDED = 4 * 1024**3
STATE_FIELDS = {"prediction-mode","prediction-model","manual-total","manual-pace","spacing","departure",
    "analysis-adjustment","analysis-split","analysis-split-percent","analysis-climb","color-mode","play-speed",
    "simulation-mode","simulation-model","simulation-total","simulation-pace","simulation-departure",
    "simulation-spacing","simulation-anchor","simulation-color","simulation-speed","import-kind","import-profile",
    "import-distance-class","import-min-km","import-max-km","import-min-date","import-max-date"}


def validate_state(state):
    if not isinstance(state,dict): raise ValueError("État utilisateur incorrect.")
    runs=state.get("runs",[]);settings=state.get("settings",{})
    if not isinstance(runs,list) or len(runs)>20 or not isinstance(settings,dict):
        raise ValueError("Scénarios ou réglages incorrects.")
    for run in runs:
        if not isinstance(run,dict) or not isinstance(run.get("data"),dict) or not run["data"].get("marks"):
            raise ValueError("Scénario incomplet dans la sauvegarde.")
    points=state.get("waypoints",[])
    if not isinstance(points,list) or len(points)>200:raise ValueError("Repères incorrects.")
    for point in points:
        if not isinstance(point,dict) or not isinstance(point.get("km"),(int,float)) or len(str(point.get("comment","")))>500:
            raise ValueError("Repère incorrect.")
    last=state.get("lastAnalysis")
    if last is not None and (not isinstance(last,dict) or len(str(last.get("sourceId","")))!=64 or any(c not in "0123456789abcdef" for c in str(last.get("sourceId","")))):
        raise ValueError("Dernier parcours incorrect.")
    clean=dict(runs=runs,waypoints=points,lastAnalysis=last,settings={k:str(v)[:200] for k,v in settings.items() if k in STATE_FIELDS},
               tourDisabled=bool(state.get("tourDisabled",False)))
    if len(json.dumps(clean,allow_nan=False).encode())>40*1024**2: raise ValueError("Scénarios trop volumineux (40 Mio maximum).")
    return clean


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024**2),b""):h.update(chunk)
    return h.hexdigest()


class Backups:
    def __init__(self,store,references):
        self.store=store;self.references=Path(references)
        self.directory=store.path.parent/"sauvegardes";self.directory.mkdir(parents=True,exist_ok=True)

    def path(self,token):
        if not isinstance(token,str) or len(token)!=32 or any(c not in "0123456789abcdef" for c in token):
            raise ValueError("Identifiant de sauvegarde incorrect.")
        return self.directory/(token+".zip")

    def create(self,label="manuelle"):
        token=uuid.uuid4().hex;target=self.path(token);partial=target.with_suffix(".partial")
        with TemporaryDirectory(dir=self.directory,prefix="snapshot-") as temporary:
            snapshot=Path(temporary)/"database.sqlite3"
            with self.store.connection() as source,closing(sqlite3.connect(snapshot)) as destination:
                source.backup(destination)
            files=[("database.sqlite3",snapshot)]
            for prefix,root in [("references",self.references),("parcours-importes",self.store.path.parent/"parcours-importes"),("parcours-projet",self.references.parent/"parcours")]:
                if root.exists():
                    for path in sorted(root.rglob("*.gpx")):
                        if path.is_symlink():raise ValueError("Une référence liée doit être copiée avant sauvegarde.")
                        files.append((prefix+"/"+path.relative_to(root).as_posix(),path))
            manifest=dict(format="predictrail-backup",schema=1,application="PrédicTrail",version=__version__,
                createdAt=datetime.now(timezone.utc).isoformat(),label=label,referenceRoot=str(self.references.resolve()),files={})
            try:
                with zipfile.ZipFile(partial,"w",zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
                    for name,path in files:
                        stat=path.stat();checksum=file_hash(path);archive.write(path,name)
                        if file_hash(path)!=checksum:raise ValueError("Un GPX a changé pendant la sauvegarde ; recommencez.")
                        manifest["files"][name]=dict(bytes=stat.st_size,sha256=checksum,mtimeNs=stat.st_mtime_ns)
                    archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
                os.replace(partial,target)
            finally:
                if partial.exists():partial.unlink()
        return dict(token=token,name="PredicTrail-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".zip",bytes=target.stat().st_size,createdAt=manifest["createdAt"])

    def list_backups(self):
        result=[]
        for path in sorted(self.directory.glob("*.zip"),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                self.path(path.stem)
                with zipfile.ZipFile(path) as archive:
                    info=archive.getinfo("manifest.json")
                    if info.file_size>4*1024**2:continue
                    manifest=json.loads(archive.read("manifest.json"))
                result.append(dict(token=path.stem,createdAt=manifest["createdAt"],label=manifest.get("label","importée"),bytes=path.stat().st_size))
            except (ValueError,KeyError,zipfile.BadZipFile,OSError):continue
        return result

    def inspect(self,path,extract_to=None):
        if Path(path).stat().st_size>MAX_ARCHIVE:raise ValueError("Archive limitée à 2 Gio.")
        with zipfile.ZipFile(path) as archive:
            infos=archive.infolist();names=[i.filename for i in infos]
            if len(infos)>10000 or len(names)!=len({n.casefold() for n in names}) or sum(i.file_size for i in infos)>MAX_EXPANDED:
                raise ValueError("Archive trop volumineuse ou entrées dupliquées.")
            if "manifest.json" not in names or archive.getinfo("manifest.json").file_size>4*1024**2:
                raise ValueError("Manifeste de sauvegarde absent ou trop volumineux.")
            manifest=json.loads(archive.read("manifest.json"))
            if manifest.get("format")!="predictrail-backup" or manifest.get("schema")!=1:
                raise ValueError("Format de sauvegarde inconnu.")
            files=manifest.get("files",{})
            if not isinstance(files,dict) or "database.sqlite3" not in files or set(names)!={"manifest.json",*files}:
                raise ValueError("Contenu différent du manifeste.")
            for name,metadata in files.items():
                parts=PurePosixPath(name).parts
                allowed=name=="database.sqlite3" or (len(parts)>1 and parts[0] in ("references","parcours-importes","parcours-projet") and name.endswith(".gpx"))
                if not allowed or ".." in parts or "\\" in name or ":" in name or name.startswith("/"):
                    raise ValueError("Chemin interdit dans la sauvegarde.")
                info=archive.getinfo(name)
                if info.file_size!=metadata.get("bytes") or ((info.external_attr>>16)&0o170000)==0o120000:
                    raise ValueError("Taille incorrecte ou lien interdit.")
                h=hashlib.sha256()
                output=None
                try:
                    if extract_to:
                        destination=Path(extract_to).joinpath(*parts);destination.parent.mkdir(parents=True,exist_ok=True);output=destination.open("wb")
                    with archive.open(name) as stream:
                        for chunk in iter(lambda:stream.read(1024**2),b""):
                            h.update(chunk)
                            if output:output.write(chunk)
                finally:
                    if output:output.close()
                if h.hexdigest()!=metadata.get("sha256"):raise ValueError("Sauvegarde endommagée : empreinte incorrecte.")
                if extract_to and name!="database.sqlite3":os.utime(destination,ns=(metadata["mtimeNs"],metadata["mtimeNs"]))
        return manifest

    def restore(self,token):
        archive=self.path(token)
        with TemporaryDirectory(dir=self.store.path.parent,prefix="restauration-") as temporary:
            stage=Path(temporary);manifest=self.inspect(archive,stage)
            incoming=stage/"database.sqlite3"
            with closing(sqlite3.connect(incoming)) as db:
                db.execute("PRAGMA trusted_schema=OFF")
                if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Base de sauvegarde endommagée.")
                expected={"activities","reference_selection","reference_cache","model_cache","activity_profiles","app_state","training_planning"}
                objects=db.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
                if any(kind in ("view","trigger") or (kind=="table" and name not in expected) for kind,name in objects):
                    raise ValueError("Structure SQLite inattendue.")
                for table in ("reference_selection","reference_cache"):
                    for (key,) in db.execute(f"SELECT key FROM {table}").fetchall():
                        if key.startswith("file:"):
                            try:relative=Path(key[5:]).relative_to(manifest["referenceRoot"])
                            except ValueError:continue
                            updated="file:"+str((self.references/relative).resolve())
                            if updated!=key:db.execute(f"UPDATE {table} SET key=? WHERE key=?",(updated,key))
                state=db.execute("SELECT payload FROM app_state WHERE id=1").fetchone()
                if state:validate_state(json.loads(state[0]))
                db.commit()
            safety=self.create("avant-restauration")
            replacements=[(self.store.path,incoming),(self.references,stage/"references"),
                          (self.store.path.parent/"parcours-importes",stage/"parcours-importes"),
                          (self.references.parent/"parcours",stage/"parcours-projet")]
            completed=[]
            try:
                for i,(destination,source) in enumerate(replacements):
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    if not source.exists():source.mkdir()
                    previous=stage/("precedent-"+str(i))
                    existed=destination.exists()
                    if existed:os.replace(destination,previous)
                    try:os.replace(source,destination)
                    except Exception:
                        if existed:os.replace(previous,destination)
                        raise
                    completed.append((destination,previous,existed))
            except Exception:
                for destination,previous,existed in reversed(completed):
                    discarded=stage/("annule-"+uuid.uuid4().hex);os.replace(destination,discarded)
                    if existed:os.replace(previous,destination)
                raise
        return dict(restored=True,safetyBackup=safety)
