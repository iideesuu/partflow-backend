#!/usr/bin/env python3
"""M3 HTTP latency baseline. URL and concurrency are environment supplied."""
import os,time,statistics,urllib.request,concurrent.futures,json
url=os.environ.get('PERF_BASE_URL','http://127.0.0.1:8000/health/ready/')
count=int(os.environ.get('PERF_REQUESTS','100')); workers=int(os.environ.get('PERF_CONCURRENCY','10'))
def one(_):
 t=time.perf_counter()
 try:
  with urllib.request.urlopen(url,timeout=10) as r: r.read(); status=r.status
 except Exception: status=0
 return (time.perf_counter()-t)*1000,status
with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex: samples=list(ex.map(one,range(count)))
lat=sorted(x[0] for x in samples); pct=lambda p: lat[min(len(lat)-1,int(len(lat)*p)-1)]
print(json.dumps({'url':url,'requests':count,'concurrency':workers,'success':sum(s==200 for _,s in samples),'p95_ms':pct(.95),'p99_ms':pct(.99),'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2))
