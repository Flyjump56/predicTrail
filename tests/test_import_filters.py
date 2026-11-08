"""Filtres morphologiques cohérents entre import, affichage et suppression locale."""
from datetime import datetime,timedelta,timezone
from math import cos,pi
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_core import synthetic_course
from test_v11 import FakeGarmin
from bzhaventure.garmin import GarminConnection
from bzhaventure.gpx import read_gpx
from bzhaventure.storage import Store,validate_filters


def activity_gpx(profile,length,day):
    course=synthetic_course(profile,length)
    start=datetime(2026,5,day,tzinfo=timezone.utc)
    nodes=[]
    for index,(position,point) in enumerate(zip(course[0][0],course[0][1])):
        lon=2+position/(111195*cos(48*pi/180))
        stamp=(start+timedelta(seconds=index*60)).isoformat()
        nodes.append(f'<trkpt lat="48" lon="{lon}"><ele>{point[2]}</ele><time>{stamp}</time></trkpt>')
    return ('<gpx><trk><trkseg>'+''.join(nodes)+'</trkseg></trk></gpx>').encode()


def save(store,key,profile,length,day):
    data=activity_gpx(profile,length,day)
    store.save_activity(dict(id=key,source='gpx',name=key,kind='running',date=f'2026-05-{day:02d}',
        distance=length,reference=True),data)
    return data


class ImportFiltersTests(unittest.TestCase):
    def test_reject_unknown_profile_or_distance_class(self):
        for filters in ({'profile':'unknown'},{'distanceClass':'unknown'}):
            with self.assertRaises(ValueError): validate_filters(filters)
        self.assertEqual(validate_filters({})['profile'],'all')

    def test_existing_imports_are_classified_cached_and_updated(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite3')
            save(store,'one','flat',5000,1)
            row=store.list_activities()[0]
            self.assertEqual((row['profile'],row['distanceClass']),('flat','very_short'))
            reopened=Store(store.path)
            with patch('bzhaventure.gpx.read_gpx',side_effect=AssertionError('Analyse répétée')):
                self.assertEqual(reopened.list_activities()[0]['profile'],'flat')
            save(store,'one','mountain',30000,2)
            row=store.list_activities()[0]
            self.assertEqual((row['profile'],row['distanceClass']),('mountain','short'))
            store.profile_version='new-classifier'
            with patch('bzhaventure.gpx.read_gpx',wraps=read_gpx) as parser:
                store.list_activities()
            self.assertEqual(parser.call_count,1)

    def test_filtered_list_and_deletion_use_same_combined_criteria(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite3')
            save(store,'flat','flat',5000,1)
            save(store,'mountain','mountain',30000,2)
            save(store,'coast','sawtooth',60000,3)
            filters=validate_filters(dict(kind='running',profile='mountain',distanceClass='short',
                minKm=25,maxKm=35,minDate='2026-05-02',maxDate='2026-05-02'))
            self.assertEqual([r['id'] for r in store.list_activities(filters)],['mountain'])
            self.assertEqual(store.delete_activities(filters),1)
            self.assertEqual({r['id'] for r in store.list_activities()},{'flat','coast'})
            with store.connection() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM activity_profiles WHERE id=?',('mountain',)).fetchone()[0],0)

    def test_unclassifiable_import_is_preserved_and_not_matched_by_specific_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite3')
            store.save_activity(dict(id='bad',source='gpx',name='bad',kind='running',date='2026-05-01',
                distance=10000,reference=False),b'<gpx/>')
            self.assertIsNotNone(store.list_activities()[0]['classificationError'])
            self.assertEqual(store.delete_activities(validate_filters({'profile':'flat'})),0)
            self.assertEqual(len(store.list_activities()),1)

    def test_garmin_checks_profile_after_download_and_does_not_store_rejected_files(self):
        class Client(FakeGarmin):
            def get_activities_by_date(self,*args,**kwargs):
                return [dict(activityId=i,activityName=str(i),activityType={'typeKey':'running'},
                    startTimeLocal=f'2026-05-{i:02d} 00:00:00',distance=length)
                    for i,length in ((1,5000),(2,30000),(3,60000))]
            def download_activity(self,activity_id,dl_fmt):
                self.downloads.append(activity_id)
                profile,length={1:('flat',5000),2:('mountain',30000),3:('sawtooth',60000)}[int(activity_id)]
                return activity_gpx(profile,length,int(activity_id))
        connection=GarminConnection(factory=Client)
        connection.connect('test@example.com','test-only');connection.complete_mfa('123456')
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'db.sqlite3')
            filters=validate_filters({'profile':'mountain','distanceClass':'short'})
            report=connection.import_activities(store,filters,True,lambda *args:None)
            self.assertEqual((report['imported'],report['filtered']),(1,2))
            self.assertEqual(len(connection.client.downloads),3)
            row=store.list_activities()[0]
            self.assertEqual((row['profile'],row['distanceClass']),('mountain','short'))
            report=connection.import_activities(store,filters,True,lambda *args:None)
            self.assertEqual((report['existing'],report['filtered']),(1,2))
            self.assertEqual(len(connection.client.downloads),5)
