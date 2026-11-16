#!/usr/bin/env python3
"""Private, local-only Long View server. No frontend build or cloud service."""
import argparse,base64,concurrent.futures,datetime,gzip,hashlib,io,json,os,re,sys,threading,time,urllib.error,urllib.parse,urllib.request,webbrowser,zipfile
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from zoneinfo import ZoneInfo
import model

ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get("LONG_VIEW_DATA_DIR",ROOT/"data"))
for directory in [DATA,DATA/"streams",DATA/"analysis"]:directory.mkdir(parents=True,exist_ok=True)
LOCK=threading.RLock()
KEY=os.environ.get("INTERVALS_API_KEY") or os.environ.get("INTERVALS_ICU_API_KEY")
JOB={"running":False,"done":0,"total":0,"message":"Local cache ready","errors":[]}
CACHE={}

def read(path,default):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return default
def write(path,data):
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(data,separators=(",",":"),allow_nan=False));temp.replace(path)
def settings():return {**model.DEFAULTS,**read(DATA/"settings.json",{})}
def local_timezone():return ZoneInfo(os.environ.get("LONG_VIEW_TIMEZONE") or read(DATA/"preferences.json",{}).get("timezone","UTC"))
def catalog():return read(DATA/"catalog.json",[])
def recording_path(i):return DATA/"streams"/(i+".json")
def safe_id(i):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}",i):raise ValueError("Invalid ride identifier.")
    return i
def signature():return hashlib.sha256((model.VERSION+json.dumps(settings(),sort_keys=True)).encode()).hexdigest()[:12]
def load_analysis(ride):
    i=safe_id(ride["id"])
    recording=recording_path(i)
    if not recording.exists():return None
    stamp=recording.stat()
    revision=hashlib.sha256((str(stamp.st_mtime_ns)+str(stamp.st_size)+json.dumps(ride,sort_keys=True)).encode()).hexdigest()[:12]
    key=i+signature()+revision
    if key in CACHE:return CACHE[key]
    path=DATA/"analysis"/(key+".json")
    if path.exists():a=read(path,None)
    elif recording_path(i).exists():
        a=model.analyze(ride,read(recording_path(i),{}),settings());write(path,a)
    else:return None
    CACHE[key]=a;return a
def summarize():
    rows=[];notes=read(DATA/"notes.json",{})
    for r in catalog():
        x=dict(r);x["cached"]=recording_path(safe_id(r["id"])).exists();x["note"]=notes.get(r["id"],{})
        if x["cached"]:
            a=load_analysis(r);x["metrics"]=a["metrics"];x["reference_ftp"]=a["reference_ftp"]
        rows.append(x)
    return rows
def bootstrap():
    rows=summarize()
    return {"rides":rows,"settings":settings(),"job":dict(JOB),"connected":bool(KEY),
        "coverage":{"activities":len(rows),"long120":sum(r.get("duration_minutes",0)>=120 for r in rows),
            "modeled120":sum(r.get("duration_minutes",0)>=120 and r["cached"] for r in rows),
            "long90":sum(r.get("duration_minutes",0)>=90 for r in rows),
            "modeled90":sum(r.get("duration_minutes",0)>=90 and r["cached"] for r in rows)},
        "latest":max((r["start_local"] for r in rows),default=None),
        "data_rule":"All elapsed recording gaps are stops and receive recovery automatically.",
        "environment_rule":"One combined history. Indoor/outdoor FTP changes fatigue and hard-effort costs; recorded watts are never rescaled.",
        "analysis_version":model.VERSION}

def api(path):
    if not KEY:raise ValueError("Enter your Intervals API key locally to download new recordings.")
    request=urllib.request.Request("https://intervals.icu/api/v1"+path,headers={
        "Authorization":"Basic "+base64.b64encode(("API_KEY:"+KEY).encode()).decode(),"Accept":"application/json","User-Agent":"LongViewLocal/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code==429 and attempt<2:time.sleep(min(int(e.headers.get("Retry-After","5")),30));continue
            if e.code in [401,403]:raise ValueError("Intervals did not accept that API key or athlete ID.")
            raise ValueError("Intervals returned HTTP "+str(e.code)+". Retry the download.")
    raise ValueError("Intervals is temporarily rate limiting requests.")

def normalize(r):
    if "duration_minutes" in r:return r
    return {"id":str(r["id"]),"start_local":r.get("start_date_local",r.get("start_date","")),
        "type":r.get("type","Ride"),"name":r.get("name","Ride"),
        "duration_minutes":(r.get("moving_time") or 0)/60,"elapsed_minutes":(r.get("elapsed_time") or 0)/60,
        "distance_m":r.get("distance"),"source":r.get("source"),"device":r.get("device_name"),
        "np_watts":r.get("icu_weighted_avg_watts"),"avg_watts":r.get("icu_average_watts",r.get("average_watts")),
        "avg_hr":r.get("average_heartrate"),"recorded_ftp":r.get("icu_ftp"),"load":r.get("icu_training_load")}

def download_recording(i):
    values=api("/activity/"+urllib.parse.quote(i,safe="")+"/streams.json?types=time,watts,heartrate,cadence,velocity_smooth")
    streams={v["type"]:v.get("data",[]) for v in values}
    times=streams.get("time",[]);power=streams.get("watts",streams.get("raw_watts",[]))
    if not times or not power:raise ValueError("No usable power recording is available for this ride.")
    rows=[]
    for j,t in enumerate(times):
        rows.append([t,*[streams.get(k,[])[j] if j<len(streams.get(k,[])) else None for k in ["watts","heartrate","cadence","velocity_smooth"]]])
        rows[-1][1]=power[j] if j<len(power) else None
    return {"schema":"LONG_VIEW_STREAM_V1","id":i,"columns":["elapsed_s","power_w","heart_rate","cadence","speed_mps"],"source":"Direct Intervals API original recording","rows":rows}

def job_sync(athlete):
    try:
        JOB.update(message="Reading your complete ride history",done=0,total=0,errors=[])
        today=datetime.datetime.now(local_timezone()).date().isoformat()
        raw=api("/athlete/"+urllib.parse.quote(athlete,safe="")+"/activities?oldest=2000-01-01&newest="+today)
        kinds={"Ride","VirtualRide","MountainBikeRide","GravelRide","TrackRide","Cyclocross"}
        new=[normalize(r) for r in raw if r.get("type") in kinds]
        with LOCK:
            old={r["id"]:r for r in catalog()};old.update({r["id"]:r for r in new})
            all_rows=sorted(old.values(),key=lambda r:r["start_local"]);write(DATA/"catalog.json",all_rows)
        queue=[r for r in all_rows if r.get("duration_minutes",0)>=90 and not recording_path(r["id"]).exists() and r.get("source")!="STRAVA"]
        JOB["total"]=len(queue)
        for n,r in enumerate(queue):
            JOB["message"]="Downloading "+r["start_local"][:10]+" · "+r["name"]
            try:
                write(recording_path(safe_id(r["id"])),download_recording(r["id"]));load_analysis(r)
            except Exception as e:JOB["errors"].append({"id":r["id"],"date":r["start_local"][:10],"message":str(e)})
            JOB["done"]=n+1
        JOB["message"]="Download complete" if not JOB["errors"] else "Download finished; some recordings need attention"
    except Exception as e:JOB["message"]=str(e);JOB["errors"].append({"message":str(e)})
    finally:JOB["running"]=False

def import_fit(filename,payload):
    from garmin_fit_sdk import Decoder,Stream
    # The SDK supports bytes through Stream.from_byte_array.
    messages,errors=Decoder(Stream.from_byte_array(bytearray(payload))).read()
    if errors:raise ValueError("This FIT file could not be decoded cleanly.")
    sessions=messages.get("session_mesgs",[])
    session=next((s for s in sessions if s.get("sport")=="cycling"),None)
    records=messages.get("record_mesgs",[])
    if not session or not records:raise ValueError("This file has no completed cycling recording.")
    start=session.get("start_time",records[0]["timestamp"]);end=session.get("timestamp",records[-1]["timestamp"])
    records=[r for r in records if start<=r["timestamp"]<=end]
    if not records:raise ValueError("No cycling power samples were found.")
    local=start.astimezone(local_timezone()).replace(tzinfo=None).isoformat()
    existing=next((r for r in catalog() if abs((datetime.datetime.fromisoformat(r["start_local"])-datetime.datetime.fromisoformat(local)).total_seconds())<120),None)
    i=existing["id"] if existing else "fit_"+hashlib.sha256(payload).hexdigest()[:16]
    indoor=session.get("sub_sport") in ["virtual_activity","indoor_cycling"]
    meta=existing or {"id":i,"start_local":local,"type":"VirtualRide" if indoor else "Ride","name":Path(filename).stem,
        "duration_minutes":session.get("total_timer_time",0)/60,"elapsed_minutes":session.get("total_elapsed_time",0)/60,
        "distance_m":session.get("total_distance"),"source":"LOCAL_FIT"}
    rows=[[int((r["timestamp"]-start).total_seconds()),r.get("power"),r.get("heart_rate"),r.get("cadence"),r.get("speed")] for r in records]
    write(recording_path(i),{"schema":"LONG_VIEW_STREAM_V1","id":i,"source":"Imported original FIT","rows":rows})
    with LOCK:
        c={r["id"]:r for r in catalog()};c[i]=meta;write(DATA/"catalog.json",sorted(c.values(),key=lambda x:x["start_local"]))
        for k in list(CACHE):
            if k.startswith(i):del CACHE[k]
        for p in (DATA/"analysis").glob(i+"*.json"):p.unlink()
    load_analysis(meta);return i

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,data,status=200):
        body=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(body)
    def allowed(self):
        host=self.headers.get("Host","").split(":")[0]
        origin=self.headers.get("Origin")
        return host in ["127.0.0.1","localhost","[::1]"] and (not origin or origin in ["http://"+self.headers.get("Host","")])
    def do_GET(self):
        if not self.allowed():return self.reply({"error":"Local requests only."},403)
        path=urllib.parse.urlparse(self.path).path
        try:
            if path=="/api/state":return self.reply(bootstrap())
            if path=="/api/job":return self.reply(dict(JOB))
            if path.startswith("/api/ride/"):
                i=safe_id(path.rsplit("/",1)[1]);r=next((r for r in catalog() if r["id"]==i),None)
                if not r:return self.reply({"error":"Ride not found."},404)
                return self.reply({"ride":r,"analysis":load_analysis(r)})
            if path=="/api/health":return self.reply({"ok":True,"version":model.VERSION})
            file=ROOT/"static"/("index.html" if path=="/" else path.lstrip("/"))
            if not file.resolve().is_relative_to((ROOT/"static").resolve()) or not file.is_file():return self.reply({"error":"Not found."},404)
            body=file.read_bytes();self.send_response(200);self.send_header("Content-Type",{".html":"text/html; charset=utf-8",".css":"text/css",".js":"text/javascript",".svg":"image/svg+xml"}.get(file.suffix,"application/octet-stream"))
            self.send_header("Content-Length",str(len(body)));self.send_header("Cache-Control","no-cache");self.end_headers();self.wfile.write(body)
        except (ValueError,KeyError) as e:self.reply({"error":str(e)},400)
        except Exception:self.reply({"error":"Unable to load the local data. Check the app terminal."},500)
    def do_POST(self):
        global KEY
        if not self.allowed():return self.reply({"error":"Local requests only."},403)
        path=urllib.parse.urlparse(self.path).path
        try:
            size=int(self.headers.get("Content-Length",0))
            if size>200*1024*1024:raise ValueError("Please import files in batches smaller than 200 MB.")
            body=self.rfile.read(size)
            if path=="/api/import":
                if self.headers.get("Content-Type","").split(";")[0]!="application/octet-stream":raise ValueError("Expected a FIT or ZIP file.")
                name=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("name",["ride.fit"])[0];ids=[]
                if name.lower().endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(body)) as z:
                        for f in z.infolist():
                            if f.filename.lower().endswith(".fit"):
                                if f.file_size>30*1024*1024:raise ValueError("A FIT file is too large.")
                                ids.append(import_fit(f.filename,z.read(f)))
                else:ids.append(import_fit(name,body))
                return self.reply({"imported":len(ids),"ids":ids})
            if self.headers.get("Content-Type","").split(";")[0]!="application/json":raise ValueError("Expected JSON.")
            data=json.loads(body or b"{}")
            if path=="/api/connect":
                if data.get("key"):KEY=data["key"].strip()
                if not KEY:raise ValueError("Enter an Intervals API key.")
                athlete=str(data.get("athlete") or "0").strip()
                api("/athlete/"+urllib.parse.quote(athlete,safe=""))
                if JOB["running"]:return self.reply({"error":"A download is already running."},409)
                JOB.update(running=True,message="Starting download",done=0,total=0,errors=[])
                threading.Thread(target=job_sync,args=(athlete,),daemon=True).start();return self.reply({"started":True})
            if path=="/api/settings":
                updated=settings()
                for k in model.DEFAULTS:
                    if k in data:
                        value=float(data[k]);bounds=(50,500) if k.endswith("ftp") else ((1,6) if k=="exponent" else (30,1000))
                        if not bounds[0]<=value<=bounds[1]:raise ValueError("Model setting is outside the supported range.")
                        updated[k]=value
                write(DATA/"settings.json",updated);return self.reply({"saved":True})
            if path=="/api/note":
                i=safe_id(data["id"]);notes=read(DATA/"notes.json",{});notes[i]={"rpe":data.get("rpe"),"intent":data.get("intent","unspecified")}
                write(DATA/"notes.json",notes);return self.reply({"saved":True})
            self.reply({"error":"Not found."},404)
        except (ValueError,KeyError,zipfile.BadZipFile,ImportError) as e:self.reply({"error":str(e)},400)
        except Exception:self.reply({"error":"The operation could not finish. No external training records were changed."},500)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--port",type=int,default=8765);parser.add_argument("--open",action="store_true");parser.add_argument("--warm",action="store_true");args=parser.parse_args()
    if args.warm:
        count=0
        for r in catalog():
            if recording_path(r["id"]).exists():load_analysis(r);count+=1
        print("Modeled",count,"locally cached rides.",flush=True);return
    server=ThreadingHTTPServer(("127.0.0.1",args.port),Handler)
    print("Long View: http://127.0.0.1:"+str(args.port),flush=True)
    if args.open:threading.Timer(.5,lambda:webbrowser.open("http://127.0.0.1:"+str(args.port))).start()
    server.serve_forever()
if __name__=="__main__":main()
