"""Archives vérifiées, données complètes, restauration et erreurs sans mutation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
import zipfile
from unittest.mock import patch
from test_v11 import gpx_bytes
from bzhaventure.storage import Store
from bzhaventure.backup import Backups,validate_state


class BackupTests(unittest.TestCase):
    def prepare(self,root):
        refs=root/'references';refs.mkdir();(refs/'exemple.gpx').write_bytes(gpx_bytes())
        store=Store(root/'local'/'app.sqlite3')
        store.save_activity(dict(id='one',source='gpx',name='Exemple',kind='running',date='2026-05-01',distance=2000,reference=True),gpx_bytes())
        state=dict(runs=[dict(name='Test',data=dict(marks=[[0,0,48,2,10,'Départ']],duration=1000))],
                   settings={'analysis-adjustment':'-10','garmin-password':'secret'},waypoints=[dict(km=1,comment='Eau')])
        store.save_app_state(state)
        with store.connection() as db:
            db.execute('INSERT INTO reference_selection VALUES (?,?)',('file:'+str((refs/'exemple.gpx').resolve()),0))
            db.execute("INSERT INTO model_cache VALUES ('test',X'00','hash')")
        return store,refs,Backups(store,refs)

    def test_full_roundtrip_and_safety_snapshot(self):
        with TemporaryDirectory() as tmp:
            store,refs,manager=self.prepare(Path(tmp));original=store.get_app_state()
            backup=manager.create();manifest=manager.inspect(manager.path(backup['token']))
            self.assertEqual(manifest['format'],'predictrail-backup');self.assertEqual(len(manifest['files']),2)
            store.delete_activities();store.save_app_state({'runs':[]});(refs/'exemple.gpx').write_text('modifié')
            result=manager.restore(backup['token'])
            self.assertTrue(manager.path(result['safetyBackup']['token']).is_file())
            self.assertEqual(store.get_app_state(),original);self.assertEqual((refs/'exemple.gpx').read_bytes(),gpx_bytes())
            self.assertEqual(len(store.list_activities()),1)
            with store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM model_cache').fetchone()[0],1)
            self.assertNotIn('garmin-password',original['settings'])

    def test_corrupted_archive_leaves_original_intact(self):
        with TemporaryDirectory() as tmp:
            store,refs,manager=self.prepare(Path(tmp));backup=manager.create();path=manager.path(backup['token'])
            with zipfile.ZipFile(path) as source:contents={name:source.read(name) for name in source.namelist()}
            contents['references/exemple.gpx']=b'invalide'
            with zipfile.ZipFile(path,'w') as archive:
                for name,data in contents.items():archive.writestr(name,data)
            before=store.get_app_state()
            with self.assertRaises(ValueError):manager.restore(backup['token'])
            self.assertEqual(before,store.get_app_state());self.assertEqual((refs/'exemple.gpx').read_bytes(),gpx_bytes())

    def test_traversal_and_bad_tokens_rejected(self):
        with TemporaryDirectory() as tmp:
            _,_,manager=self.prepare(Path(tmp));path=Path(tmp)/'bad.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('../outside.gpx','test');archive.writestr('manifest.json',json.dumps(dict(format='predictrail-backup',schema=1,files={'database.sqlite3':{},'../outside.gpx':{}})))
            with self.assertRaises(ValueError):manager.inspect(path)
            with self.assertRaises(ValueError):manager.path('../bad')

    def test_selection_paths_remapped_on_another_folder(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);store,refs,manager=self.prepare(root);backup=manager.create()
            other=root/'other';other.mkdir();target=Store(other/'local'/'app.sqlite3');dest=Backups(target,other/'references')
            import shutil
            shutil.copy2(manager.path(backup['token']),dest.path(backup['token']))
            dest.restore(backup['token'])
            with target.connection() as db:key=db.execute('SELECT key FROM reference_selection').fetchone()[0]
            self.assertEqual(key,'file:'+str((other/'references'/'exemple.gpx').resolve()))

    def test_invalid_state(self):
        with self.assertRaises(ValueError):validate_state({'runs':[{}]})

    def test_filesystem_error_rolls_back_database_and_references(self):
        import os
        with TemporaryDirectory() as tmp:
            store,refs,manager=self.prepare(Path(tmp));backup=manager.create()
            store.save_app_state({'runs':[]});before=store.get_app_state();real_replace=os.replace
            def fail(source,destination):
                if Path(source).name=='references' and Path(destination)==refs:raise OSError('test remplacement impossible')
                return real_replace(source,destination)
            with patch('bzhaventure.backup.os.replace',side_effect=fail):
                with self.assertRaises(OSError):manager.restore(backup['token'])
            self.assertEqual(store.get_app_state(),before)
            self.assertEqual((refs/'exemple.gpx').read_bytes(),gpx_bytes())
