import React, { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, base, post } from './api';
const Viewer = React.lazy(() => import('./Viewer').then(module => ({ default: module.Viewer })));
import { Box, Dataset, Export, Frame, Job, Model, Prediction, Scene, colors, labels } from './types';
import './style.css';

function App() {
  const [page,setPage]=useState('Dataset'); const [dataset,setDataset]=useState<Dataset|null>(null);
  const [scenes,setScenes]=useState<Scene[]>([]); const [scene,setScene]=useState(''); const [frames,setFrames]=useState<Frame[]>([]);
  const [index,setIndex]=useState(0); const [model,setModel]=useState<Model|null>(null); const [jobs,setJobs]=useState<Job[]>([]);
  const [jobId,setJobId]=useState(''); const [prediction,setPrediction]=useState<Prediction|null>(null);
  const [error,setError]=useState(''); const [pending,setPending]=useState(false); const [score,setScore]=useState(.3);
  const [inferenceScore,setInferenceScore]=useState(.3); const [start,setStart]=useState(0); const [end,setEnd]=useState(0);
  const [classes,setClasses]=useState<string[]>(labels); const [selected,setSelected]=useState<string|null>(null);
  const [camera,setCamera]=useState('CAM_FRONT'); const [imageError,setImageError]=useState(false);
  const [exportResult,setExportResult]=useState<Export|null>(null); const [cvat,setCvat]=useState('http://localhost:8080');
  const token=frames[index]?.sample_token; const currentJob=jobs.find(j=>j.id===jobId);
  const refresh = useCallback(async (signal?:AbortSignal) => {
    const results=await Promise.all([api<Dataset>('/api/dataset',{signal}),api<Model[]>('/api/models',{signal}),api<Job[]>('/api/jobs',{signal})]);
    setDataset(results[0]);setModel(results[1][0]);setJobs(results[2]);
  },[]);
  useEffect(()=>{
    const control=new AbortController();
    refresh(control.signal).then(()=>Promise.all([api<{items:Scene[]}>('/api/scenes',{signal:control.signal}),api<{cvat_url:string;default_score_threshold:number}>('/api/health',{signal:control.signal})])).then(([s,h])=>{setScenes(s.items);setScene(s.items[0]?.token||'');setCvat(h.cvat_url);setScore(h.default_score_threshold);setInferenceScore(h.default_score_threshold);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>control.abort();
  },[refresh]);
  useEffect(()=>{
    if(!scene)return; const control=new AbortController();setFrames([]);setPrediction(null);setIndex(0);setSelected(null);
    api<Frame[]>(`/api/scenes/${scene}/frames`,{signal:control.signal}).then(f=>{setFrames(f);setStart(0);setEnd(f.length-1);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return()=>control.abort();
  },[scene]);
  useEffect(()=>{
    let stopped=false; const control=new AbortController();let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{await refresh(control.signal);}catch(e){if(!stopped)setError((e as Error).message);}finally{if(!stopped)timer=setTimeout(poll,1500);}};
    timer=setTimeout(poll,1500);return()=>{stopped=true;clearTimeout(timer);control.abort();};
  },[refresh]);
  useEffect(()=>{
    setPrediction(null);setSelected(null);setImageError(false);
    if(!token||!currentJob||!currentJob.request.sample_tokens.includes(token))return;
    const control=new AbortController();
    api<Prediction>(`/api/jobs/${jobId}/predictions/${token}`,{signal:control.signal}).then(setPrediction).catch(e=>{if(e.name!=='AbortError'&&!e.message.includes('No such file')&&!e.message.includes('cannot find')&&currentJob.status==='completed')setError(e.message);});
    return()=>control.abort();
  },[token,jobId,currentJob?.status,currentJob?.processed]);
  useEffect(()=>{
    if(!exportResult||['completed','failed'].includes(exportResult.status))return;
    let stopped=false;const control=new AbortController();let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const e=await api<Export>(`/api/exports/${exportResult.id}`,{signal:control.signal});if(!stopped)setExportResult(e);}catch(e){if(!stopped)setError((e as Error).message);}finally{if(!stopped)timer=setTimeout(poll,1000);}};
    timer=setTimeout(poll,1000);return()=>{stopped=true;clearTimeout(timer);control.abort();};
  },[exportResult?.id,exportResult?.status]);
  const boxes=useMemo(()=>prediction?.boxes.filter(b=>b.score>=score&&classes.includes(b.label))||[],[prediction,score,classes]);
  const onSelect=useCallback((id:string)=>setSelected(id),[]);
  const activeBox=boxes.find(b=>b.id===selected);
  const selection=frames.slice(start,end+1).map(f=>f.sample_token);
  const exportSelectionValid=!!currentJob&&selection.length>0&&selection.every(t=>currentJob.request.sample_tokens.includes(t))&&classes.length>0;
  async function action(fn:()=>Promise<void>){setPending(true);setError('');try{await fn();}catch(e){setError((e as Error).message);}finally{setPending(false);}}
  function run(){void action(async()=>{const j=await post<Job>('/api/jobs',{scene_token:scene,sample_tokens:selection,threshold:inferenceScore,model:model?.id});setJobId(j.id);await refresh();});}
  function exportCvat(){void action(async()=>{setExportResult(await post<Export>('/api/exports',{job_id:jobId,sample_tokens:selection,threshold:score,classes}));});}
  const chosenScene=scenes.find(s=>s.token===scene);
  return <div className="app"><aside className="sidebar"><div className="brand"><span className="brand-icon">▧</span>nuScenes<small>PRELABEL STUDIO</small></div><div className="nav-label">WORKSPACE</div>{['Dataset','Workspace','Jobs'].map((p,i)=><button key={p} className={`nav ${page===p?'active':''}`} onClick={()=>setPage(p)}><span>{['◫','⬡','≡'][i]}</span>{p}{p==='Jobs'&&<b>{jobs.length}</b>}</button>)}<div className="sidebar-foot"><i className={dataset?.available?'online':'offline'}/> Local dataset<small>v1.0-mini · LiDAR 3D</small></div></aside>
  <main><header><div><span className="eyebrow">LOCAL ANNOTATION PIPELINE</span><h1>{page==='Workspace'?(chosenScene?.name||'Workspace'):page}</h1></div><div className="header-right"><span className="badge">{dataset?.available?'Dataset connected':'Dataset unavailable'}</span><span className={`badge ${model?.available?'':'warn'}`}>{model?.available?'Model configured':'Model setup required'}</span><a href={cvat} target="_blank" rel="noreferrer">Open CVAT ↗</a></div></header>
  {error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')}>×</button></div>}
  {page==='Dataset'&&<section className="dataset-page"><div className="hero"><span className="eyebrow">YOUR DATA, IN THREE DIMENSIONS</span><h2>From LiDAR to labels.</h2><p>Browse real nuScenes frames, run pretrained detection, and prepare cuboids for CVAT.</p><div className="stats"><div><strong>{dataset?.scene_count??'—'}</strong><span>Scenes</span></div><div><strong>{scenes.reduce((a,s)=>a+s.nbr_samples,0)||'—'}</strong><span>Keyframes</span></div><div><strong>6</strong><span>Camera channels</span></div></div></div><div className="dataset-meta"><span>{dataset?.version||'Connecting…'}</span><code>{dataset?.root}</code>{dataset?.error&&<p className="error">{dataset.error}</p>}</div><div className="section-title"><h3>Available scenes</h3><span>Choose a scene to open the workspace</span></div><div className="scene-grid">{scenes.map(s=><button className="scene-card" key={s.token} onClick={()=>{setScene(s.token);setPage('Workspace');}}><div><span className="scene-symbol">⬡</span><span>{s.nbr_samples} frames</span></div><h3>{s.name}</h3><p>{s.description}</p><footer>Open workspace <span>↗</span></footer></button>)}</div>{!scenes.length&&<p>No scenes available. Check the backend and dataset root.</p>}</section>}
  {page==='Workspace'&&<section className="workspace"><div className="workspace-top"><select value={scene} onChange={e=>setScene(e.target.value)}>{scenes.map(s=><option key={s.token} value={s.token}>{s.name}</option>)}</select><select value={jobId} onChange={e=>setJobId(e.target.value)}><option value="">Choose prediction job</option>{jobs.filter(j=>j.request.scene_token===scene).map(j=><option key={j.id} value={j.id}>{j.id.slice(0,8)} · {j.status}</option>)}</select><span className="spacer"/><button title="Choose a finished job, frames belonging to that job, and at least one class" disabled={pending||!exportSelectionValid||currentJob?.status==='running'||currentJob?.status==='queued'} onClick={exportCvat}>↓ Export CVAT</button><button className="primary" disabled={pending||!model?.available||!selection.length} onClick={run}>▷ Run Prelabel</button></div>
  <div className="workspace-grid"><div className="viewer-column">{token?<Suspense fallback={<div className="empty">Loading 3D viewer…</div>}><Viewer token={token} boxes={boxes} selected={selected} onSelect={onSelect}/></Suspense>:<div className="empty">Loading scene frames…</div>}<div className="timeline"><button disabled={index===0} onClick={()=>setIndex(i=>i-1)}>←</button><span>Frame <b>{index+1}</b> / {frames.length}</span><input aria-label="Frame timeline" type="range" min="0" max={Math.max(0,frames.length-1)} value={index} onChange={e=>setIndex(+e.target.value)}/><button disabled={index>=frames.length-1} onClick={()=>setIndex(i=>i+1)}>→</button><code>{frames[index]?.timestamp_us}</code></div><div className="viewer-caption">Orbit: drag · Pan: right drag · Zoom: scroll <span>{prediction?`${boxes.length} visible cuboids`:'No prediction for this frame'}</span></div></div>
  <aside className="inspector"><div className="panel"><div className="panel-title">Camera preview<select value={camera} onChange={e=>{setCamera(e.target.value);setImageError(false);}}>{['CAM_FRONT','CAM_FRONT_LEFT','CAM_FRONT_RIGHT','CAM_BACK','CAM_BACK_LEFT','CAM_BACK_RIGHT'].map(c=><option key={c}>{c}</option>)}</select></div>{token&&!imageError?<img key={`${token}/${camera}`} src={`${base}/api/frames/${token}/camera/${camera}`} onError={()=>setImageError(true)} alt={camera}/>:<div className="empty">Camera image unavailable</div>}</div>
  <div className="panel"><div className="panel-title">Inference settings</div><p className="model-name">{model?.name||'Loading model…'}</p>{!model?.available&&<div className="setup-note">{model?.errors.map(e=><p key={e}>{e}</p>)}</div>}<div className="form-row"><label>First frame<input type="number" min="0" max={end} value={start} onChange={e=>setStart(Math.max(0,Math.min(end,+e.target.value)))}/></label><label>Last frame<input type="number" min={start} max={frames.length-1} value={end} onChange={e=>setEnd(Math.max(start,Math.min(frames.length-1,+e.target.value)))}/></label></div><label>Inference score floor <b>{inferenceScore.toFixed(2)}</b><input type="range" min="0" max="1" step=".01" value={inferenceScore} onChange={e=>setInferenceScore(+e.target.value)}/></label><small>Range uses scene indices starting at 0. Inference settings apply to the next job.</small></div>
  <div className="panel"><div className="panel-title">View & export filters</div><label>Score threshold <b>{score.toFixed(2)}</b><input type="range" min="0" max="1" step=".01" value={score} onChange={e=>setScore(+e.target.value)}/></label><div className="class-filters">{labels.map((l,i)=><button key={l} className={classes.includes(l)?'enabled':''} onClick={()=>setClasses(c=>c.includes(l)?c.filter(x=>x!==l):[...c,l])}><i style={{background:colors[i]}}/>{l.replaceAll('_',' ')}</button>)}</div>{currentJob&&score<currentJob.request.threshold&&<small>Boxes below the job's inference floor were not saved.</small>}</div>
  <div className="panel"><div className="panel-title">Cuboids <span>{boxes.length}</span></div>{!prediction?<div className="empty">No model prediction yet.<br/>Configure the model and run prelabel.</div>:boxes.length===0?<div className="empty">No boxes match your filters.</div>:<div className="box-list">{boxes.map(b=><button key={b.id} className={selected===b.id?'selected':''} onClick={()=>setSelected(b.id)}><i style={{background:colors[labels.indexOf(b.label)]}}/>{b.label}<span>{(b.score*100).toFixed(0)}%</span></button>)}</div>}{activeBox&&<dl><dt>Center / m</dt><dd>{activeBox.center.map(v=>v.toFixed(2)).join(' / ')}</dd><dt>L × W × H / m</dt><dd>{activeBox.size_lwh.map(v=>v.toFixed(2)).join(' × ')}</dd><dt>Yaw / rad</dt><dd>{activeBox.yaw_rad.toFixed(3)}</dd></dl>}</div></aside></div>
  {currentJob&&<div className="job-strip"><span className={`status ${currentJob.status}`}>{currentJob.status}</span><progress max={currentJob.total} value={currentJob.processed}/><span>{currentJob.processed}/{currentJob.total} · {currentJob.elapsed.toFixed(1)}s</span><span>{currentJob.message}</span>{currentJob.error&&<p className="error">{currentJob.error}</p>}</div>}
  {exportResult&&<div className="export-strip">Export: {exportResult.status} · {exportResult.processed}/{exportResult.total}{exportResult.error&&<span className="error">{exportResult.error}</span>}{exportResult.download_url&&<a href={base+exportResult.download_url}>Download bundle ↓</a>}<small>Unzip bundle: upload data.zip, then import annotations.zip as Datumaro 3D 1.0. Live CVAT import is not yet verified.</small></div>}</section>}
  {page==='Jobs'&&<section className="jobs-page"><div className="section-title"><h3>Inference history</h3><span>{jobs.length} jobs</span></div>{!jobs.length&&<div className="empty large">No jobs yet. Open a scene and run prelabel after configuring the model.</div>}{jobs.map(j=><article className="job-card" key={j.id}><div><code>{j.id.slice(0,12)}</code><span className={`status ${j.status}`}>{j.status}</span><span>{j.processed}/{j.total} frames · {j.elapsed.toFixed(1)}s</span></div><progress max={j.total} value={j.processed}/><p>{j.message}</p>{j.error&&<pre className="error">{j.error}</pre>}{j.parent_job_id&&<small>Retry of {j.parent_job_id}</small>}<footer><button onClick={()=>{setScene(j.request.scene_token);setJobId(j.id);setPage('Workspace');}}>View workspace</button>{['queued','running'].includes(j.status)?<button disabled={pending} onClick={()=>void action(async()=>{await post(`/api/jobs/${j.id}/cancel`);await refresh();})}>Cancel</button>:<button disabled={pending||!model?.available} onClick={()=>void action(async()=>{const next=await post<Job>(`/api/jobs/${j.id}/retry`);setJobId(next.id);await refresh();})}>Retry as new job</button>}</footer></article>)}</section>}
  </main></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
