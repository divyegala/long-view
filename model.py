"""Long View: independent descriptive analysis of original ride recordings."""
import math
import numpy as np

VERSION = "long-view-1.1.0"
EFFORT_DURATIONS = [180,300,480,600,900,1200,1800,2700,3600]
DURATIONS = sorted(set([30,60,120,2400,5400,7200,10800] + EFFORT_DURATIONS))
DEFAULTS = {"indoor_ftp":185,"outdoor_ftp":203,"aerobic_reference_w":140,"exponent":3,"slow_tau_minutes":240,"fast_tau_seconds":120}

def finite(value):
    return value is not None and isinstance(value,(int,float)) and math.isfinite(value)

def best_blocks(starts, powers, duration, count=3):
    chosen=[]
    for j in np.argsort(-powers,kind="stable"):
        t=int(starts[j])
        if all(t+duration<=a["start"] or t>=a["start"]+duration for a in chosen):
            chosen.append({"start":t,"duration":duration,"watts":round(float(powers[j]),2)})
            if len(chosen)==count: break
    return chosen

def fatigue(power, reference, settings):
    slow=np.zeros(len(power)+1);fast=np.zeros(len(power)+1)
    tau=settings["slow_tau_minutes"];decay=math.exp(-1/(60*tau))
    for i,p in enumerate(power):
        if not np.isfinite(p):
            slow[i+1]=slow[i];fast[i+1]=fast[i];continue
        r=max(0,p)/reference
        # Shared absolute aerobic cost; environments diverge near threshold.
        # This reflects the athlete's report that 140 W feels alike indoors
        # and outdoors. It is a proposed descriptive load function, not a fit.
        aerobic=(max(0,p)/settings["aerobic_reference_w"])**2
        threshold_cost=(max(0,r-.8)/.2)**settings["exponent"]
        slow[i+1]=slow[i]*decay+(aerobic+threshold_cost)*tau*(1-decay)
        if p>reference:fast[i+1]=fast[i]+(p-reference)/1000
        else:fast[i+1]=fast[i]*math.exp(-1/(settings["fast_tau_seconds"]*(1+4*r*r)))
    return slow,fast

def analyze(meta, recording, options=None):
    settings={**DEFAULTS,**(options or {})}
    indoor=meta.get("type") in ["VirtualRide"] or meta.get("trainer",False)
    reference=float(settings["indoor_ftp" if indoor else "outdoor_ftp"])
    rows=sorted({int(x[0]):x for x in recording["rows"]}.values(),key=lambda x:x[0])
    if not rows:raise ValueError("The recording contains no samples.")
    n=int(rows[-1][0])+1
    if n>7*86400:raise ValueError("Recording duration is invalid.")
    power=np.zeros(n);observed=np.zeros(n,dtype=bool);hr=np.full(n,np.nan)
    for row in rows:
        t=int(row[0]);observed[t]=True
        power[t]=max(0,float(row[1])) if finite(row[1]) else np.nan
        if len(row)>2 and finite(row[2]) and row[2]>0:hr[t]=row[2]
    # Time gaps are stops for this athlete, and remain on the elapsed clock.
    # They contribute zero power and recover the fatigue states automatically.
    stops=~observed
    transition=np.diff(np.r_[False,stops,False].astype(int))
    gaps=[{"start":int(a),"end":int(b),"seconds":int(b-a)} for a,b in zip(np.flatnonzero(transition==1),np.flatnonzero(transition==-1))]
    slow,fast=fatigue(power,reference,settings)
    burden=slow/30+fast/5
    sums=np.r_[0,np.cumsum(np.nan_to_num(power,nan=0))]
    missing=np.r_[0,np.cumsum(~np.isfinite(power))]
    work=sums/1000
    hours=list(range(n//3600+1))
    curves=[];chosen={}
    for d in DURATIONS:
        if d>n:continue
        starts=np.flatnonzero((missing[d:]-missing[:-d])==0)
        if not len(starts):continue
        values=(sums[starts+d]-sums[starts])/d
        top=best_blocks(starts,values,d)
        best=top[0];j=int(np.argmax(values));t=int(starts[j])
        after={}
        for hour in hours:
            mask=starts>=hour*3600
            after[str(hour)]=round(float(values[mask].max()),2) if np.any(mask) else None
        fatigue_levels={}
        for lo,hi,label in [(0,1,"low"),(1,2,"moderate"),(2,float("inf"),"high")]:
            mask=(burden[starts]>=lo)&(burden[starts]<hi)
            fatigue_levels[label]=round(float(values[mask].max()),2) if np.any(mask) else None
        chosen[str(d)]=[{**b,"prior_work_kj":round(float(work[b["start"]]),1),
            "slow":round(float(slow[b["start"]]),2),"fast":round(float(fast[b["start"]]),2)} for b in top]
        curves.append({"seconds":d,"best":best["watts"],
            "repeated":round(float(np.mean([b["watts"] for b in top])),2) if len(top)==3 else None,
            "repeat_count":len(top),"after_hours":after,"fatigue_levels":fatigue_levels,
            "prior_work_kj":round(float(work[t]),1),"start":t})
    lookup={x["seconds"]:x for x in curves}
    active_hours=max(float(meta.get("duration_minutes") or np.sum(power>0)/60)/60,1/60)
    hard_seconds=int(np.sum(power>reference))
    power_time=[{"watts":p,"minutes_per_hour":round(float(np.sum(power>=p))/60/active_hours,2)} for p in range(80,351,10)]
    detail=[]
    for a in range(0,n,30):
        b=min(a+30,n);p=power[a:b];h=hr[a:b]
        detail.append({"minute":round(a/60,2),"power":round(float(np.nanmean(p)),1) if np.isfinite(p).any() else None,
            "hr":round(float(np.nanmean(h)),1) if np.isfinite(h).any() else None,
            "work":round(float(work[a]),1),"slow":round(float(slow[a]),2),"fast":round(float(fast[a]),2)})
    return {"version":VERSION,"id":meta["id"],"reference_ftp":reference,"indoor":indoor,"settings":settings,
        "curves":curves,"blocks":chosen,"elapsed_hours":hours,"power_time":power_time,"timeline":detail,"stops":gaps,
        "recorded_seconds":int(observed.sum()),"stop_seconds":int(stops.sum()),"elapsed_seconds":n,
        "missing_power_samples":int(np.sum(~np.isfinite(power))),"recorded_work_kj":round(float(work[-1]),2),
        "metrics":{"short":lookup.get(180,{}).get("repeated"),"sustained":lookup.get(1200,{}).get("best"),
            "repeatability":round(hard_seconds/60/active_hours,2),
            "late":lookup.get(1200,{}).get("after_hours",{}).get("1")},
        "model_note":"Descriptive experimental indices; not a physiological fatigue measurement. Watts are unchanged between environments."}

def distribution(values):
    xs=np.array([float(x) for x in values if finite(x)])
    if not len(xs):return None
    return {"median":float(np.median(xs)),"low":float(np.quantile(xs,.1)),"high":float(np.quantile(xs,.9)),"n":len(xs)}

def compare(value, values):
    baseline=distribution(values)
    if not baseline or not finite(value):return {"delta":None,"percentile":None,"baseline":baseline}
    xs=[float(x) for x in values if finite(x)]
    percentile=100*(sum(x<value for x in xs)+.5*sum(x==value for x in xs))/len(xs)
    delta=100*(value/baseline["median"]-1) if baseline["median"] else None
    return {"delta":delta,"percentile":percentile,"baseline":baseline}
