"""Répartition des durées, cohérence des exports et protection des temps réels."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from copy import deepcopy
from bzhaventure.strategy import apply_strategy


def baseline():
    return dict(distance=2000,duration=1000,model={"scope":"manual"},
        sections=[dict(start=[48,2,0],end=[48.01,2,100],distance=0,endDistance=1000,time=0,endTime=800,grade=10,speed=4.5),
                  dict(start=[48.01,2,100],end=[48.02,2,100],distance=1000,endDistance=2000,time=800,endTime=1000,grade=0,speed=18)],
        marks=[(0,0,48,2,0,"Départ"),(1000,800,48.01,2,100,"Passage"),(2000,1000,48.02,2,100,"Arrivée")],
        exportPoints=[[[48,2,0,0],[48.01,2,100,800],[48.02,2,100,1000]]],
        pauses={"duration":100},movingDuration=900,
        terrain=[{"name":"Montée","estimated":800},{"name":"Plat","estimated":200}])


class StrategyTests(unittest.TestCase):
    def test_neutral_and_signed_duration(self):
        source=baseline();before=deepcopy(source)
        self.assertEqual(apply_strategy(source,{})['duration'],1000)
        for percent,expected in [(-10,900),(10,1100)]:
            result=apply_strategy(source,{"adjustmentPercent":percent})
            self.assertAlmostEqual(result['duration'],expected)
            self.assertAlmostEqual(result['marks'][-1][1],expected)
            self.assertAlmostEqual(result['exportPoints'][0][-1][3],expected)
            self.assertAlmostEqual(result['pauses']['duration'],expected/10)
        self.assertEqual(source,before)

    def test_split_is_by_distance_and_preserves_total_despite_unequal_terrain(self):
        for split,first in [('positive',450),('negative',550)]:
            result=apply_strategy(baseline(),{"split":split,"splitPercent":10})
            self.assertAlmostEqual(result['duration'],1000)
            self.assertAlmostEqual(result['marks'][1][1],first)
            self.assertAlmostEqual(result['sections'][0]['endTime'],first)
            self.assertAlmostEqual(result['exportPoints'][0][1][3],first)

    def test_climb_only_and_combined_change(self):
        result=apply_strategy(baseline(),{"climbPercent":25})
        self.assertEqual(result['duration'],1200)
        self.assertAlmostEqual(result['sections'][1]['endTime']-result['sections'][1]['time'],200)
        combined=apply_strategy(baseline(),{"split":"negative","splitPercent":20,"climbPercent":-20,"adjustmentPercent":-10})
        self.assertAlmostEqual(combined['duration'],792)
        self.assertAlmostEqual(sum(x['estimated'] for x in combined['terrain']),792)
        self.assertAlmostEqual(combined['strategy']['actualChangePercent'],-20.8)

    def test_midpoint_inside_one_section_is_split_exactly(self):
        source=baseline();source['sections']=[dict(start=[48,2,0],end=[48.02,2,0],distance=0,endDistance=2000,time=0,endTime=1000,grade=0,speed=7.2)]
        result=apply_strategy(source,{"split":"positive","splitPercent":20})
        self.assertEqual(len(result['sections']),2)
        self.assertAlmostEqual(result['sections'][0]['endTime'],400)
        self.assertEqual(result['sections'][0]['endDistance'],1000)
        self.assertAlmostEqual(result['duration'],1000)

    def test_invalid_options_and_recorded_mode(self):
        for options in [{"adjustmentPercent":float('nan')},{"adjustmentPercent":True},{"climbPercent":101},{"splitPercent":-1},{"split":"unknown"},[]]:
            with self.assertRaises(ValueError):apply_strategy(baseline(),options)
        source=baseline();source['model']['scope']='recorded'
        with self.assertRaises(ValueError):apply_strategy(source,{})

    def test_manual_http_uses_strategy_for_entire_timeline(self):
        import base64,json
        from email.message import Message
        from io import BytesIO
        from test_v11 import gpx_bytes, runtime
        from bzhaventure.server import Dashboard
        h=Dashboard.__new__(Dashboard);h.path='/api/prediction';h.server=runtime(None)
        body=json.dumps(dict(gpx=base64.b64encode(gpx_bytes()).decode(),mode='total',totalSeconds=7200,
            interval=1,strategy={"adjustmentPercent":-10})).encode()
        h.rfile=BytesIO(body);h.headers=Message();h.headers['Content-Type']='application/json';h.headers['Content-Length']=str(len(body))
        responses=[];h.send_json=lambda payload,status=200:responses.append((payload,status))
        h.do_POST();result,status=responses[0]
        self.assertEqual(status,200,result)
        self.assertAlmostEqual(result['duration'],6480)
        self.assertAlmostEqual(result['marks'][-1][1],6480)
        self.assertAlmostEqual(result['exportPoints'][-1][-1][3],6480)
