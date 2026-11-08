"""Contrôle HTTP réservé à l’instance de démonstration (aucune donnée réelle)."""
from io import BytesIO
import json,time,urllib.request,zipfile
url='http://127.0.0.1:8767'
def get(path):return json.load(urllib.request.urlopen(url+path,timeout=60))
def post(path,data,content='application/json'):
    if content=='application/json':data=json.dumps(data).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(url+path,data=data,headers={'Content-Type':content}),timeout=120))
report=get('/api/reference-map')
assert report['courses'] and all(c['name'].startswith('Demonstration-fictive-') for c in report['courses']), 'Instance fictive obligatoire'
state=get('/api/state')['state'] or dict(runs=[],settings={})
backup=post('/api/backup/create',dict(state=state))
archive=urllib.request.urlopen(url+backup['url'],timeout=60).read()
with zipfile.ZipFile(BytesIO(archive)) as source:
    assert 'database.sqlite3' in source.namelist();assert 'manifest.json' in source.namelist()
preview=post('/api/backup/inspect',archive,'application/zip')
post('/api/backup/restore',dict(token=preview['token']))
for _ in range(120):
    op=get('/api/operation')
    if op['status'] in ('ready','error'):break
    time.sleep(.25)
assert op['status']=='ready',op
assert get('/api/state')['state']==state
assert len(get('/api/backup/list')['backups'])>=2
status=get('/api/garmin/status');assert status.get('available'),status
print(json.dumps(dict(backupBytes=len(archive),files=preview['files'],restored=True,scenarios=len(state['runs']),garminAvailable=True)))
