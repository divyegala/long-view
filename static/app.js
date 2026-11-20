'use strict';
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const EFFORT_DURATIONS=[180,300,480,600,900,1200,1800,2700,3600];
function savedEffort(){try{const d=Number(localStorage.getItem('long-view-effort'));return EFFORT_DURATIONS.includes(d)?d:1200;}catch{return 1200;}}
function savedAfterHour(){try{const h=Number(localStorage.getItem('long-view-after-hour'));return Number.isInteger(h)&&h>=1&&h<=168?h:1;}catch{return 1;}}
const S={data:null,models:new Map(),page:'progress',metric:'sustained',effort:savedEffort(),afterHour:savedAfterHour(),selected:null,mode:'best',loadView:'time',powerView:'all',period:90,cutoff:120};
const METRICS={short:{title:'Repeated 3-min power',icon:'↗',caption:'Mean of your strongest three 3-min blocks',unit:'W'},
 sustained:{get title(){return S.effort/60+'-min power';},icon:'⏱',get caption(){return 'Best '+S.effort/60+'-min effort';},unit:'W'},
 repeatability:{title:'Repeatability',icon:'≋',caption:'Minutes above threshold per moving hour',unit:'min/h'},
 late:{get title(){return 'Late '+S.effort/60+'-min power';},icon:'↝',get caption(){return 'Best '+S.effort/60+'-min effort starting after '+S.afterHour+'h elapsed';},unit:'W'}};
function metricValue(a,key){if(!a)return null;if(key==='sustained'||key==='late'){const c=a.curves.find(x=>x.seconds===S.effort);return key==='late'?c?.after_hours[String(S.afterHour)]??null:c?.best??null;}return a.metrics[key];}
function setEffort(value){const d=Number(value);if(!EFFORT_DURATIONS.includes(d))return;S.effort=d;try{localStorage.setItem('long-view-effort',String(d));}catch{}syncEffort();render();}
function syncEffort(){$$('#effort-duration, #late-duration').forEach(el=>{el.innerHTML=EFFORT_DURATIONS.map(d=>'<option value="'+d+'">'+d/60+' min</option>').join('');el.value=String(S.effort);});}
function syncAfterHour(){const max=Math.max(1,S.afterHour,...Array.from(S.models.values(),a=>Math.floor(a.elapsed_seconds/3600)));$('#after-hour').innerHTML=Array.from({length:max},(_,i)=>'<option value="'+(i+1)+'">After '+(i+1)+'h</option>').join('');$('#after-hour').value=String(S.afterHour);}
const NS='http://www.w3.org/2000/svg';
function esc(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function ok(x){return typeof x==='number'&&Number.isFinite(x);}
function median(xs){xs=xs.filter(ok).sort((a,b)=>a-b);return xs.length?(xs[Math.floor((xs.length-1)/2)]+xs[Math.ceil((xs.length-1)/2)])/2:null;}
function robust(xs){return median(xs.filter(ok).sort((a,b)=>b-a).slice(0,3));}
function pct(v,b){return ok(v)&&ok(b)&&b!==0?100*(v/b-1):null;}
function signed(x,suffix='%'){return ok(x)?(x>0?'+':'')+Math.round(x)+suffix:'—';}
function fmtDate(s,year=false){return new Date(s).toLocaleDateString('en-US',{month:'short',day:'numeric',...(year?{year:'numeric'}:{})});}
function minutes(n){const h=Math.floor(n/60),m=Math.round(n%60);return h?h+'h'+(m?' '+m+'m':''):m+' min';}
function dur(s){return s<60?s+'s':s<3600?s/60+'m':s/3600+'h';}
function dateNumber(s){return new Date(s).getTime();}
function eligible(){return S.data.rides.filter(r=>r.duration_minutes>=S.cutoff).sort((a,b)=>a.start_local.localeCompare(b.start_local));}
function modeled(){return eligible().filter(r=>r.cached&&S.models.has(r.id));}
function selected(){return S.data.rides.find(r=>r.id===S.selected);}
function analysis(){return S.models.get(S.selected);}
function cohort(ride){const t=dateNumber(ride.start_local),span=S.period==='all'?Infinity:S.period*864e5;return modeled().filter(r=>dateNumber(r.start_local)<t&&t-dateNumber(r.start_local)<=span);}
function compare(v,values){const xs=values.filter(ok),b=median(xs);return {delta:pct(v,b),baseline:b,n:xs.length,percentile:ok(v)&&xs.length?100*(xs.filter(x=>x<v).length+.5*xs.filter(x=>x===v).length)/xs.length:null};}
async function api(path,data,opts){const r=await fetch(path,data===undefined?opts:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d;}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4000);}
function empty(container,text){container.innerHTML='<div class="chart-empty">'+esc(text)+'</div>';}

function svgNode(tag,attrs={},text){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;}
function chartFrame(container,height){
 container.innerHTML='';const w=Math.max(260,Math.floor(container.clientWidth)),h=height||container.clientHeight||260;
 const svg=svgNode('svg',{width:w,height:h,viewBox:'0 0 '+w+' '+h,role:'img'});container.appendChild(svg);return {svg,w,h};
}
function lineChart(container,series,options={}){
 const usable=series.flatMap(s=>s.data.filter(p=>ok(p.x)&&ok(p.y)));
 if(!usable.length)return empty(container,options.empty||'No comparable data at this workload yet.');
 const {svg,w,h}=chartFrame(container),m={left:48,right:18,top:16,bottom:45};
 const xs=usable.map(p=>p.x),ys=usable.map(p=>p.y),xmin=options.xmin??Math.min(...xs),xmax=options.xmax??Math.max(...xs);
 let ymin=options.ymin??Math.min(...ys),ymax=options.ymax??Math.max(...ys);
 if(options.reference!==undefined){ymin=Math.min(ymin,options.reference);ymax=Math.max(ymax,options.reference);}
 const span=Math.max(ymax-ymin,10);ymin=options.ymin??Math.max(0,ymin-span*.16);ymax=options.ymax??ymax+span*.2;
 if(ymax===ymin)ymax+=10;
 const X=x=>m.left+(x-xmin)/Math.max(xmax-xmin,1)*(w-m.left-m.right),Y=y=>h-m.bottom-(y-ymin)/(ymax-ymin)*(h-m.top-m.bottom);
 for(let i=0;i<=4;i++){const y=ymin+(ymax-ymin)*i/4;svg.appendChild(svgNode('line',{x1:m.left,x2:w-m.right,y1:Y(y),y2:Y(y),stroke:'#e9edf4'}));svg.appendChild(svgNode('text',{x:m.left-10,y:Y(y)+4,'text-anchor':'end'},options.yformat?options.yformat(y):Math.round(y)));}
 const tickCount=w<480?3:5,ticks=options.xticks||Array.from({length:tickCount},(_,i)=>xmin+(xmax-xmin)*i/(tickCount-1));
 ticks.forEach((x,i)=>svg.appendChild(svgNode('text',{x:X(x),y:h-18,'text-anchor':i===0?'start':i===ticks.length-1?'end':'middle'},options.xformat?options.xformat(x):Math.round(x))));
 if(options.reference!==undefined)svg.appendChild(svgNode('line',{x1:m.left,x2:w-m.right,y1:Y(options.reference),y2:Y(options.reference),stroke:'#95a5bf','stroke-dasharray':'5 5'}));
 for(const stop of options.stops||[]){svg.appendChild(svgNode('rect',{x:X(stop.start/60),y:m.top,width:Math.max(1,X(stop.end/60)-X(stop.start/60)),height:h-m.top-m.bottom,fill:'#dce3ee',opacity:.7}));}
 const tooltip=document.createElement('div');tooltip.className='tooltip';tooltip.hidden=true;container.appendChild(tooltip);
 series.forEach(s=>{
  let path='',active=false;s.data.forEach(p=>{if(!ok(p.y)||!ok(p.x)){active=false;return;}path+=(active?'L':'M')+X(p.x)+','+Y(p.y)+' ';active=true;});
  if(s.line!==false)svg.appendChild(svgNode('path',{d:path,fill:'none',stroke:s.color||'#2859cf','stroke-width':s.width||2.5,'stroke-linejoin':'round',...(s.dash?{'stroke-dasharray':'5 4'}:{})}));
  if(s.points!==false)s.data.filter(p=>ok(p.y)).forEach(p=>{
   const dot=svgNode('circle',{cx:X(p.x),cy:Y(p.y),r:s.onClick?4:3.5,fill:s.color||'#2859cf',stroke:'#fff','stroke-width':1.5});
   dot.appendChild(svgNode('title',{},p.tip||s.label+': '+Math.round(p.y)));
   dot.addEventListener('pointerenter',()=>{tooltip.textContent=p.tip||s.label+': '+Math.round(p.y);tooltip.hidden=false;tooltip.style.left=Math.max(0,Math.min(w-220,X(p.x)-80))+'px';tooltip.style.top=Math.max(0,Y(p.y)-50)+'px';});
   dot.addEventListener('pointerleave',()=>tooltip.hidden=true);
   if(s.onClick){dot.style.cursor='pointer';dot.addEventListener('click',()=>s.onClick(p));}
   svg.appendChild(dot);
  });
 });
}

function metricCard(key,value,caption,selectable=true,emptyText='More evidence'){
 const cfg=METRICS[key],emptyValue=!ok(value),classes=emptyValue?'empty':value>=0?'positive':'negative';
 return '<button class="metric '+(selectable&&S.metric===key?'selected':'')+'" '+(selectable?'data-metric="'+key+'"':'type="button"')+'><span class="metric-label">'+cfg.title+'<span class="metric-icon">'+cfg.icon+'</span></span><div class="metric-value '+classes+'">'+(emptyValue?esc(emptyText):signed(value))+'</div><div class="metric-caption">'+esc(caption)+'</div></button>';
}
function bindMetricCards(){ $$('#progress-metrics [data-metric]').forEach(el=>el.onclick=()=>{S.metric=el.dataset.metric;renderProgress();}); }
function renderProgress(){
 const all=modeled();if(!all.length){empty($('#trend-chart'),'Import power recordings to start comparing rides.');return;}
 const latest=all.at(-1),end=dateNumber(latest.start_local),days=S.period==='all'?90:S.period,span=days*864e5;
 let current=all.filter(r=>end-dateNumber(r.start_local)<span),prior=all.filter(r=>end-dateNumber(r.start_local)>=span&&end-dateNumber(r.start_local)<2*span);
 if(S.period==='all'){const half=Math.floor(all.length/2);prior=all.slice(0,half);current=all.slice(half);}
 const get=(r,k)=>metricValue(S.models.get(r.id),k);let up=0,assessed=0;
 $('#progress-metrics').innerHTML=Object.keys(METRICS).map(k=>{
  const a=current.map(r=>get(r,k)).filter(ok),b=prior.map(r=>get(r,k)).filter(ok),delta=a.length>=3&&b.length>=3?pct(robust(a),robust(b)):null;
  if(ok(delta)){assessed++;if(delta>2)up++;}
  return metricCard(k,delta,METRICS[k].caption+' · '+(ok(delta)?'Strongest 3 rides · '+a.length+' current / '+b.length+' prior':a.length+' current / '+b.length+' prior rides with this measure'));
 }).join('');bindMetricCards();
 $('#progress-headline').textContent=assessed?up+' of '+assessed+' performance markers higher.':'A clear view starts with enough comparable rides.';
 $('#progress-description').textContent=(S.period==='all'?'Latest half of your history vs the earlier half.':'Latest '+days+' days vs the preceding '+days+' days.')+' Combined indoor and outdoor history; context matters.';
 $('#period-label').textContent=current.length+' recent rides · '+prior.length+' comparison rides';
 const cfg=METRICS[S.metric],baseline=robust(prior.map(r=>get(r,S.metric)));
 $('#trend-title').textContent=cfg.title+' over time';
 $('#trend-description').textContent=cfg.caption+'. Points are individual rides; the line tracks the recent strongest-three median. Reference period = 100.';
 if(!ok(baseline)||baseline<=0)empty($('#trend-chart'),'There are not enough comparison-period efforts for this measure.');
 else{
  const points=all.map(r=>({x:dateNumber(r.start_local),y:ok(get(r,S.metric))?100*get(r,S.metric)/baseline:null,id:r.id,tip:fmtDate(r.start_local,true)+' · '+Math.round(get(r,S.metric)/baseline*100)+'% of reference'+(r.note?.intent==='endurance'?' · endurance ride':'')}));
  const envelope=all.map(r=>{const t=dateNumber(r.start_local),xs=all.filter(x=>dateNumber(x.start_local)<=t&&t-dateNumber(x.start_local)<span).map(x=>get(x,S.metric)).filter(ok);return {x:t,y:xs.length>=3?100*robust(xs)/baseline:null};});
  lineChart($('#trend-chart'),[{label:'Individual ride',line:false,color:'#a8b5cb',data:points,onClick:p=>openRide(p.id)},{label:'Recent strongest-three median',color:'#2859cf',points:false,width:3,data:envelope}],{reference:100,xformat:x=>fmtDate(new Date(x).toISOString()),yformat:y=>Math.round(y)+'%'});
 }
 $('#latest-context').textContent=fmtDate(latest.start_local,true)+' · '+(latest.type==='VirtualRide'?'Indoor':'Outdoor');
 $('#latest-summary').innerHTML='<div class="latest-name">'+esc(latest.name)+'</div><p class="helper">Compare the shape of this ride with the work you’ve done before.</p><div class="latest-stats"><div><strong>'+minutes(latest.duration_minutes)+'</strong><span>Moving time</span></div><div><strong>'+cohort(latest).length+'</strong><span>Prior comparison rides</span></div></div>';
 $('#latest-button').onclick=()=>openRide(latest.id);
}

function curveValue(a,d,mode=S.mode,band){
 const c=a?.curves.find(x=>x.seconds===d);if(!c)return null;
 return mode==='late'?c.after_hours[String(S.afterHour)]??null:mode==='loaded'?c.fatigue_levels[band]??null:c[mode];
}
function profileRows(a,base,ds,band){
 return ds.map(d=>{const value=curveValue(a,d,S.mode,band),v=base.map(r=>curveValue(S.models.get(r.id),d,S.mode,band)).filter(ok);return {d,band,value,...compare(value,v)};});
}
function drawProfile(container,rows,limit){
 const valid=rows.filter(r=>ok(r.delta));
 if(!valid.length)return empty(container,'No complete efforts with a comparison baseline here yet.');
 const height=Math.max(420,rows.length*35+47);container.style.height=height+'px';
 const {svg,w,h}=chartFrame(container,height),m={left:45,right:w<430?77:120,top:22,bottom:25};
 const X=v=>m.left+(v+limit)/(2*limit)*(w-m.left-m.right),rowH=(h-m.top-m.bottom)/rows.length;
 [-limit,0,limit].forEach(v=>{svg.appendChild(svgNode('line',{x1:X(v),x2:X(v),y1:m.top-7,y2:h-m.bottom,stroke:v===0?'#96a8c6':'#edf0f5','stroke-dasharray':v===0?'4 4':'0'}));svg.appendChild(svgNode('text',{x:X(v),y:13,'text-anchor':'middle'},v===0?'Prior median':signed(v)));});
 rows.forEach((r,i)=>{
  const y=m.top+i*rowH+rowH/2;
  if(r.d===S.effort)svg.appendChild(svgNode('rect',{x:-6,y:y-rowH/2+2,width:w+6,height:rowH-4,rx:5,fill:'#2859cf',opacity:.07,'data-selected-effort':r.d}));
  svg.appendChild(svgNode('text',{x:0,y:y+4,style:'font-size:12px;fill:#35445c'},dur(r.d)));
  if(!ok(r.delta)){svg.appendChild(svgNode('text',{x:w-m.right+9,y:y+4,'text-anchor':'start'},!ok(r.value)?'No effort':'No baseline'));return;}
  const color=r.delta>=0?'#2859cf':'#c17a56';
  svg.appendChild(svgNode('rect',{x:Math.min(X(0),X(r.delta)),y:y-7,width:Math.max(2,Math.abs(X(r.delta)-X(0))),height:14,rx:3,fill:color}));
  const label=svgNode('text',{x:w-m.right+12,y:y+4,style:'font-size:13px;fill:'+color+';font-weight:600'},signed(r.delta));
  label.appendChild(svgNode('title',{},Math.round(r.value)+' W vs '+Math.round(r.baseline)+' W median · '+r.n+' prior rides'+(r.band?' · '+r.band+' starting load':'')));svg.appendChild(label);
  if(w>=430)svg.appendChild(svgNode('text',{x:w-4,y:y+4,'text-anchor':'end'},'n='+r.n));
 });
}
function renderProfile(a,base){
 const container=$('#profile-chart'),ds=[30,60,...EFFORT_DURATIONS,7200],loaded=S.mode==='loaded';
 const bands=[['low','Low load','Starting burden below 1'],['moderate','Moderate load','Starting burden 1 to below 2'],['high','High load','Starting burden 2 or higher']];
 const groups=loaded?bands.map(([band,title,description])=>({band,title,description,rows:profileRows(a,base,ds,band)})):[{rows:profileRows(a,base,ds)}];
 const rows=groups.flatMap(g=>g.rows),valid=rows.filter(r=>ok(r.delta));
 const limit=Math.ceil(Math.max(15,...valid.map(r=>Math.abs(r.delta)))/10)*10;
 container.classList.toggle('load-profile',loaded);container.innerHTML='';container.style.height=loaded?'auto':Math.max(420,ds.length*35+47)+'px';
 if(loaded){
  groups.forEach(g=>{const panel=document.createElement('div');panel.className='load-panel';panel.dataset.loadBand=g.band;panel.innerHTML='<h3>'+g.title+'</h3><p>'+g.description+'</p>';const chart=document.createElement('div');chart.className='load-panel-chart';panel.appendChild(chart);container.appendChild(panel);drawProfile(chart,g.rows,limit);});
 }else drawProfile(container,rows,limit);
 $('#profile-helper').textContent=loaded?'All three starting-load bands are shown. Each bar compares this ride’s best effort with prior rides in the same band, on a shared scale. Bands describe modeled burden at the effort’s start, not throughout the effort. Higher-load starts are included. Nonlinear intensity cost and recovery during stops affect burden; these bands are experimental, not measured physiological fatigue.':S.mode==='best'?'Best observed power, compared with the median of prior rides at each duration. Lower values can reflect an easier ride or fewer opportunities to ride hard.':S.mode==='repeated'?'Mean of the strongest three non-overlapping blocks at each duration. These are distinct blocks, not necessarily intentional repetitions. A duration needs three available blocks.':'Best complete effort starting at '+S.afterHour+':00 elapsed or later. For example, a 45-minute effort after 2h needs at least 2h45 of recording. Hour cutoffs include stops; stops also permit modeled recovery. This is a cumulative cutoff, not just the following hour.';
 $('#detail-table').innerHTML='<div class="table-wrap"><table><thead><tr><th>Duration</th>'+(loaded?'<th>Starting load</th>':'')+'<th>This ride</th><th>Prior median</th><th>Difference</th><th>Prior rides</th></tr></thead><tbody>'+rows.map(r=>'<tr'+(r.d===S.effort?' class="selected-effort"':'')+'><td>'+dur(r.d)+'</td>'+(loaded?'<td>'+r.band+'</td>':'')+'<td>'+(ok(r.value)?Math.round(r.value)+' W':'—')+'</td><td>'+(ok(r.baseline)?Math.round(r.baseline)+' W':'—')+'</td><td>'+signed(r.delta)+'</td><td>'+r.n+'</td></tr>').join('')+'</tbody></table></div>';
}
function renderDurability(a,base){
 const d=S.effort,c=a.curves.find(x=>x.seconds===d);
 $('#durability-description').textContent='Your best complete '+d/60+'-min effort starting after each elapsed-hour cutoff.';
 if(!c)return empty($('#durability-chart'),'This ride has no complete effort that long.');
 if(S.loadView==='fatigue'){
  $('#durability-description').textContent='Your best '+d/60+'-min power across all three starting-load bands.';
  const labels=['low','moderate','high'],names=['Low','Moderate','High'];
  const val=(r,k)=>{const c=r.curves.find(x=>x.seconds===d);return c&&ok(c.fatigue_levels[k])&&c.best>0?100*c.fatigue_levels[k]/c.best:null;};
  lineChart($('#durability-chart'),[{label:'Comparison rides',color:'#a8b5cb',dash:true,data:labels.map((k,i)=>({x:i,y:median(base.map(r=>val(S.models.get(r.id),k)))}))},{label:'This ride',color:'#2859cf',width:3,data:labels.map((k,i)=>({x:i,y:val(a,k),tip:names[i]+' starting load · '+(ok(val(a,k))?Math.round(val(a,k))+'% of ride best':'Not observed')}))}],{xmin:0,xmax:2,xticks:[0,1,2],xformat:x=>names[Math.round(x)]||'',yformat:y=>Math.round(y)+'%',ymin:0,ymax:110,reference:100});
  $('#durability-helper').textContent='Experimental pre-effort workload bands: low <1, moderate 1–2, high ≥2. The index combines accumulated and recent hard work; stops reduce it. All bands are included. Power is indexed to the ride’s best at this duration.';
  return;
 }
 const levels=Array.from(new Set([...(a.elapsed_hours||[]),...base.flatMap(r=>S.models.get(r.id).elapsed_hours||[])])).sort((a,b)=>a-b);
 const max=Math.max(1,...levels),step=Math.max(1,Math.ceil(max/4)),ticks=levels.filter(k=>k%step===0||k===max);
 function retain(a,k){const c=a.curves.find(x=>x.seconds===d);return c&&ok(c.after_hours[String(k)])&&c.best>0?100*c.after_hours[String(k)]/c.best:null;}
 lineChart($('#durability-chart'),[
  {label:'Comparison rides',color:'#a8b5cb',dash:true,data:levels.map(k=>{const values=base.map(r=>retain(S.models.get(r.id),k)).filter(ok);return {x:k,y:median(values),tip:'After '+k+'h · prior median · '+values.length+' rides'};})},
  {label:'This ride',color:'#2859cf',width:3,data:levels.map(k=>({x:k,y:retain(a,k),tip:(k?'After '+k+'h':'Overall best')+' · '+(ok(retain(a,k))?Math.round(retain(a,k))+'% of this ride’s best':'No complete effort recorded')}))}
 ],{yformat:y=>Math.round(y)+'%',xformat:x=>x===0?'Overall':'After '+x+'h',xticks:ticks,reference:100,ymin:0,ymax:110,xmin:0,xmax:max});
 $('#durability-helper').textContent='Each point uses the best full '+d/60+'-minute effort beginning at that elapsed hour or later, divided by that ride’s overall best at the same duration. A missing point means no complete effort fits. Stops stay on the elapsed clock and permit recovery. Hour markers match time into a ride, not physiological fatigue.';
}
function interpolatePowerTime(a,watts){const e=a.power_time;for(let i=1;i<e.length;i++)if(e[i].watts>=watts){const lo=e[i-1],hi=e[i];return lo.minutes_per_hour+(hi.minutes_per_hour-lo.minutes_per_hour)*(watts-lo.watts)/(hi.watts-lo.watts);}return e.at(-1)?.minutes_per_hour??null;}
function renderPowerTime(a,base){
 if(S.powerView==='all'){
  const levels=[100,120,140,160,180,200,220,250,300];
  lineChart($('#power-time-chart'),[{label:'Comparison rides',color:'#a8b5cb',dash:true,data:levels.map(w=>({x:w,y:median(base.map(r=>interpolatePowerTime(S.models.get(r.id),w)))}))},{label:'This ride',color:'#2859cf',width:3,data:levels.map(w=>({x:w,y:interpolatePowerTime(a,w),tip:w+' W or more · '+interpolatePowerTime(a,w).toFixed(1)+' min per moving hour'}))}],{ymin:0,xmin:100,xmax:300,xformat:x=>Math.round(x)+' W',yformat:y=>Math.round(y)+'m/h'});
  return;
 }
 const levels=[0,10,20,30,40,50],value=(a,p)=>interpolatePowerTime(a,a.reference_ftp*(1+p/100));
 lineChart($('#power-time-chart'),[
  {label:'Comparison rides',color:'#a8b5cb',dash:true,data:levels.map(p=>({x:p,y:median(base.map(r=>value(S.models.get(r.id),p)))}))},
  {label:'This ride',color:'#2859cf',width:3,data:levels.map(p=>({x:p,y:value(a,p),tip:(p?'Threshold +'+p+'%':'Threshold')+' · '+value(a,p).toFixed(1)+' min per moving hour'}))}
 ],{ymin:0,xmin:0,xmax:50,xformat:x=>x===0?'At FTP':'+'+Math.round(x)+'%',yformat:y=>Math.round(y)+'m/h'});
}
function renderTimeline(a){
 const mode=$('#timeline-mode').value,units={power:'W',slow:'reference-min',fast:'kJ'},labels={power:'Power',slow:'Slow workload index',fast:'Fast residual workload'};
 lineChart($('#timeline-chart'),[{label:labels[mode],color:'#2859cf',points:false,data:a.timeline.map(p=>({x:p.minute,y:p[mode]}))}],{stops:a.stops,xformat:x=>Math.round(x)+'m',yformat:y=>Math.round(y)+(mode==='power'?' W':''),ymin:0,...(mode==='power'?{reference:a.reference_ftp}:{})});
 $('#timeline-description').textContent=minutes(a.elapsed_seconds/60)+' elapsed · '+minutes(a.stop_seconds/60)+' in recording stops · '+(a.indoor?'Indoor':'Outdoor')+' intensity reference '+a.reference_ftp+' W';
 $('#timeline-helper').textContent=mode==='power'?'Shaded periods are stops. They remain on the elapsed clock at zero power and permit recovery automatically. The line shows 30-second average recorded power.':labels[mode]+' ('+units[mode]+'). This is an experimental within-ride workload proxy, not measured physiological fatigue. Every stop permits recovery; the fast and slow states recover at different rates.';
}
function renderLapComparison(note){
 const rows=Array.isArray(note?.lap_hr_comparison)?note.lap_hr_comparison:[];
 const keys=Array.from(new Set(rows.flatMap(r=>Object.keys(r).filter(k=>/^block_\d+_hr$/.test(k))))).sort((a,b)=>Number(a.split('_')[1])-Number(b.split('_')[1]));
 const panel=$('#lap-hr-panel'),table=$('#lap-hr-table');panel.hidden=!rows.length||!keys.length;table.innerHTML='';if(panel.hidden)return;
 const cell=value=>ok(value)?value.toFixed(1):'—';
 let footer='';const blocks=note?.dual_power_summary?.blocks;
 if(Array.isArray(blocks)){
  const found=keys.map(k=>blocks.find(b=>b.block===Number(k.split('_')[1])));
  footer='<tfoot><tr><th>Block mean HR</th>'+found.map(b=>'<td>'+cell(b?.hr_bpm)+'</td>').join('')+'</tr><tr><th>Pedal power (W)</th>'+found.map(b=>'<td>'+cell(b?.pedal_w)+'</td>').join('')+'</tr></tfoot>';
 }
 table.innerHTML='<table><thead><tr><th>Prescribed step</th>'+keys.map(k=>'<th>Block '+Number(k.split('_')[1])+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr><td><strong>'+esc(r.minutes)+' min · '+esc(r.target_w)+' W</strong><br><small>'+esc(r.target_cadence_rpm)+' rpm</small></td>'+keys.map(k=>'<td>'+cell(r[k])+'</td>').join('')+'</tr>').join('')+'</tbody>'+footer+'</table>';
}
function renderRide(){
 const ride=selected();if(!ride)return;const a=analysis(),base=cohort(ride);
 $('#ride-select').innerHTML=eligible().slice().reverse().map(r=>'<option value="'+esc(r.id)+'" '+(r.id===ride.id?'selected':'')+'>'+esc(fmtDate(r.start_local,true)+' · '+r.name)+'</option>').join('');
 $('#ride-source').textContent=(ride.type==='VirtualRide'?'Indoor':'Outdoor')+' · '+minutes(ride.duration_minutes);
 $('#ride-headline').textContent=ride.name;$('#ride-description').textContent=fmtDate(ride.start_local,true)+' · Compared with '+base.length+' earlier modeled rides'+(S.period==='all'?'':' in the preceding '+S.period+' days')+'.';
 $('#not-modeled').hidden=!!a;$('#ride-content').hidden=!a;
 if(!a){$('#not-modeled').textContent='This ride is in your history, but its original power recording has not been downloaded yet. Use Data & downloads to add it.';return;}
 const easy=ride.note?.intent==='endurance'&&(!ok(ride.note?.rpe)||ride.note.rpe<=5);
 $('#ride-context').hidden=!easy;
 $('#ride-context').textContent='Endurance context'+(ok(ride.note?.rpe)?' · RPE '+ride.note.rpe+'/10':'')+'. This ride demonstrates controlled work, not your maximal power. Lower peaks are shown in the detailed charts but are not treated as failed capacity tests.';
 $('#ride-observation').hidden=!ride.note?.observation;
 $('#ride-observation').textContent=ride.note?.observation||'';
 $('#ride-metrics').innerHTML=Object.keys(METRICS).map(k=>{const value=metricValue(a,k),c=compare(value,base.map(r=>metricValue(S.models.get(r.id),k)));const enough=c.n>=3,untested=easy&&ok(c.delta)&&c.delta<0;return metricCard(k,enough&&!untested?c.delta:null,METRICS[k].caption+' · '+(untested?'Endurance ride · capacity not tested':enough?'vs prior median · '+c.n+' comparison rides':c.n+' prior rides'),false,untested?'Not tested':!ok(value)?'Not observed':'More evidence');}).join('');
 renderLapComparison(ride.note);renderProfile(a,base);renderDurability(a,base);renderPowerTime(a,base);renderTimeline(a);
}
function renderLibrary(){
 const search=$('#search').value.toLowerCase(),rides=eligible().slice().reverse().filter(r=>(r.start_local+' '+r.name).toLowerCase().includes(search));
 $('#library-description').textContent=eligible().length+' rides meet the '+S.cutoff+'-minute definition. Original recordings are cached locally and reused.';
 $('#library-rows').innerHTML=rides.map(r=>'<tr data-id="'+esc(r.id)+'"><td><strong>'+esc(fmtDate(r.start_local,true))+'</strong><div class="ride-name">'+esc(r.name)+'</div></td><td>'+minutes(r.duration_minutes)+'</td><td>'+(r.type==='VirtualRide'?'Indoor':'Outdoor')+'</td><td><span class="status '+(r.cached?'':'pending')+'">'+(r.cached?'Modeled locally':'Recording needed')+'</span></td><td class="arrow">↗</td></tr>').join('');
 $$('#library-rows tr').forEach(row=>row.onclick=()=>openRide(row.dataset.id));
}
function render(){
 if(!S.data)return;
 syncAfterHour();
 $$('.page').forEach(p=>p.hidden=p.id!==S.page+'-page');$$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===S.page));
 const titles={progress:['THE BIG PICTURE','Am I getting better?'],ride:['YOUR PERFORMANCE, IN CONTEXT','Explore a ride'],library:['YOUR PERSONAL RECORD','Ride library']};
 $('#page-eyebrow').textContent=titles[S.page][0];$('#page-title').textContent=titles[S.page][1];$('#nav-count').textContent=eligible().length;
 const cached=eligible().filter(r=>r.cached).length;$('#coverage').textContent=cached+' / '+eligible().length+' long rides modeled locally';
 if(S.page==='progress')renderProgress();if(S.page==='ride')renderRide();if(S.page==='library')renderLibrary();
}
function openRide(id){S.selected=id;S.page='ride';render();window.scrollTo({top:0,behavior:'smooth'});}
async function load(){
 $('#load-error').hidden=true;
 try{
  S.data=await api('/api/state');
  await Promise.all(S.data.rides.filter(r=>r.cached&&r.duration_minutes>=90).map(async r=>{const x=await api('/api/ride/'+encodeURIComponent(r.id));if(x.analysis)S.models.set(r.id,x.analysis);}));
  const rides=eligible();if(!rides.some(r=>r.id===S.selected))S.selected=rides.at(-1)?.id;
  render();
 }catch(e){$('#load-error').hidden=false;$('#load-error').textContent=e.message;}
}
function settingsDialog(){
 const d=S.data,c=d.coverage;$('#data-status').textContent=c.modeled120+' of '+c.long120+' rides at 120+ minutes modeled. '+c.modeled90+' of '+c.long90+' rides at 90+ minutes modeled. History begins '+fmtDate(d.rides[0]?.start_local||d.latest,true)+'.';
 $('#indoor-ftp').value=d.settings.indoor_ftp;$('#outdoor-ftp').value=d.settings.outdoor_ftp;
 $('#aerobic-reference').value=d.settings.aerobic_reference_w;$('#exponent').value=d.settings.exponent;$('#slow-tau').value=d.settings.slow_tau_minutes;$('#fast-tau').value=d.settings.fast_tau_seconds;
 $('#settings-dialog').showModal();
}
$$('.nav-item').forEach(b=>b.onclick=()=>{S.page=b.dataset.page;render();});
$('#cutoff').onchange=()=>{S.cutoff=Number($('#cutoff').value);if(!eligible().some(r=>r.id===S.selected))S.selected=eligible().at(-1)?.id;render();};
$('#period').onchange=()=>{S.period=$('#period').value==='all'?'all':Number($('#period').value);render();};
$('#ride-select').onchange=()=>openRide($('#ride-select').value);
$('#after-hour').onchange=()=>{S.afterHour=Number($('#after-hour').value);try{localStorage.setItem('long-view-after-hour',String(S.afterHour));}catch{}render();};
$('#search').oninput=renderLibrary;
$$('#curve-mode button').forEach(b=>b.onclick=()=>{S.mode=b.dataset.mode;$$('#curve-mode button').forEach(x=>x.classList.toggle('selected',x===b));renderRide();});
$('#effort-duration').onchange=e=>setEffort(e.target.value);$('#late-duration').onchange=e=>setEffort(e.target.value);$('#timeline-mode').onchange=renderRide;
$$('#load-view button').forEach(b=>b.onclick=()=>{S.loadView=b.dataset.view;$$('#load-view button').forEach(x=>x.classList.toggle('selected',x===b));renderRide();});
$$('#power-time-view button').forEach(b=>b.onclick=()=>{S.powerView=b.dataset.view;$$('#power-time-view button').forEach(x=>x.classList.toggle('selected',x===b));renderRide();});
$('#data-button').onclick=settingsDialog;$('#sync-button').onclick=settingsDialog;
$('#connect-form').onsubmit=async e=>{
 e.preventDefault();const status=$('#job-status');status.hidden=false;status.textContent='Checking the connection…';
 try{await api('/api/connect',{key:$('#api-key').value,athlete:$('#athlete-id').value});$('#api-key').value='';
  const timer=setInterval(async()=>{try{const j=await api('/api/job');status.textContent=j.message+(j.total?' · '+j.done+'/'+j.total:'');if(!j.running){clearInterval(timer);await load();if(j.errors.length)status.textContent+=' · '+j.errors.length+' recordings need attention.';}}catch(err){clearInterval(timer);status.textContent=err.message;}},1500);
 }catch(err){status.textContent=err.message;}
};
$('#file-import').onchange=async e=>{
 const status=$('#import-status');let total=0;
 for(const f of e.target.files){status.textContent='Importing '+f.name+'…';try{const r=await fetch('/api/import?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});const d=await r.json();if(!r.ok)throw Error(d.error);total+=d.imported;}catch(err){status.textContent=err.message;return;}}
 status.textContent=total+' recordings imported.';S.models.clear();await load();
};
$('#model-form').onsubmit=async e=>{
 e.preventDefault();$('#model-status').textContent='Recalculating the locally cached rides…';
 try{await api('/api/settings',{indoor_ftp:Number($('#indoor-ftp').value),outdoor_ftp:Number($('#outdoor-ftp').value),aerobic_reference_w:Number($('#aerobic-reference').value),exponent:Number($('#exponent').value),slow_tau_minutes:Number($('#slow-tau').value),fast_tau_seconds:Number($('#fast-tau').value)});S.models.clear();await load();$('#model-status').textContent='Local model updated. Your Intervals settings were not changed.';}catch(err){$('#model-status').textContent=err.message;}
};
$('#ride-notes-button').onclick=()=>{const r=selected();$('#ride-intent').value=r.note?.intent||'unspecified';$('#ride-rpe').value=r.note?.rpe??'';$('#notes-dialog').showModal();};
$('#close-notes').onclick=()=>$('#notes-dialog').close();
$('#notes-form').onsubmit=async e=>{e.preventDefault();const v=$('#ride-rpe').value;await api('/api/note',{id:S.selected,intent:$('#ride-intent').value,rpe:v===''?null:Number(v)});$('#notes-dialog').close();await load();toast('Effort context saved locally.');};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,140);});
syncEffort();load();
