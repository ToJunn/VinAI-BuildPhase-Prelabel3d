import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { base } from './api';
import { Box, colors, labels } from './types';

export function Viewer({ token, boxes, selected, onSelect }: { token: string; boxes: Box[]; selected: string | null; onSelect: (id: string) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<{ camera: THREE.PerspectiveCamera; controls: OrbitControls } | null>(null);
  const [error, setError] = useState('');
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [points, setPoints] = useState<Float32Array | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setPoints(null); setCount(0); setError(''); setLoading(true);
    fetch(`${base}/api/frames/${token}/points`, { signal: controller.signal }).then(async r => {
      if (!r.ok) throw new Error((await r.json()).detail || 'Cannot load LiDAR');
      const values = new Float32Array(await r.arrayBuffer());
      if (!controller.signal.aborted) { setPoints(values); setCount(values.length / 3); setLoading(false); }
    }).catch(e => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false); } });
    return () => controller.abort();
  }, [token]);
  useEffect(() => {
    if (!host.current) return;
    const element = host.current;
    const scene = new THREE.Scene(); scene.background = new THREE.Color('#0c141d');
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true }); } catch { setError('WebGL unavailable'); return; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); element.appendChild(renderer.domElement);
    const camera = new THREE.PerspectiveCamera(55, 1, .1, 500); camera.up.set(0,0,1); camera.position.set(28,-38,28);
    const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
    view.current = { camera, controls };
    const grid = new THREE.GridHelper(120, 24, '#263e50', '#1b2a38'); grid.rotation.x = Math.PI / 2; grid.position.z = -2; scene.add(grid);
    scene.add(new THREE.AxesHelper(5));
    if (points) {
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(points, 3));
      const rgb = new Float32Array(points.length);
      for (let i=0; i<points.length; i+=3) {
        const h = THREE.MathUtils.clamp((points[i+2]+2)/6, 0, 1);
        const color = new THREE.Color().setHSL(.53-.34*h, .55, .42+.18*h);
        rgb[i]=color.r; rgb[i+1]=color.g; rgb[i+2]=color.b;
      }
      geo.setAttribute('color', new THREE.BufferAttribute(rgb,3));
      scene.add(new THREE.Points(geo, new THREE.PointsMaterial({size:.065, vertexColors:true})));
    }
    const targets: THREE.Mesh[] = [];
    boxes.forEach(box => {
      const color = colors[labels.indexOf(box.label)] || '#ffffff';
      const geo = new THREE.BoxGeometry(...box.size_lwh);
      const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({color, transparent:true, opacity: box.id===selected ? .26 : .07, depthWrite:false}));
      mesh.position.set(...box.center); mesh.rotation.z = box.yaw_rad; mesh.userData.id = box.id;
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({color:box.id===selected?'#ffffff':color}));
      mesh.add(edges); scene.add(mesh); targets.push(mesh);
      // Heading is model +X; not inferred from a symmetric box.
      const arrow = new THREE.ArrowHelper(new THREE.Vector3(Math.cos(box.yaw_rad), Math.sin(box.yaw_rad),0), new THREE.Vector3(...box.center), box.size_lwh[0]/2, color, .4, .25);
      scene.add(arrow);
    });
    const ray = new THREE.Raycaster(); const pointer = new THREE.Vector2();
    let down = { x:0,y:0 };
    const pointerDown = (e: PointerEvent) => { down = {x:e.clientX,y:e.clientY}; };
    const click = (e: PointerEvent) => {
      if (Math.hypot(e.clientX-down.x,e.clientY-down.y)>5) return;
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.set((e.clientX-bounds.left)/bounds.width*2-1, -(e.clientY-bounds.top)/bounds.height*2+1);
      ray.setFromCamera(pointer,camera); const hit = ray.intersectObjects(targets,false)[0];
      if (hit) onSelect(hit.object.userData.id);
    };
    renderer.domElement.addEventListener('pointerdown',pointerDown); renderer.domElement.addEventListener('pointerup',click);
    const resize = new ResizeObserver(() => { const w=element.clientWidth,h=element.clientHeight; renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix(); }); resize.observe(element);
    let frameId=0; const render = () => { controls.update(); renderer.render(scene,camera); frameId=requestAnimationFrame(render); }; render();
    return () => {
      cancelAnimationFrame(frameId); resize.disconnect(); controls.dispose(); view.current=null;
      scene.traverse(obj => { const drawable=obj as THREE.Mesh; drawable.geometry?.dispose(); if(drawable.material) { const mats=Array.isArray(drawable.material)?drawable.material:[drawable.material]; mats.forEach(m=>m.dispose()); } });
      renderer.dispose(); renderer.forceContextLoss(); renderer.domElement.remove();
    };
  }, [points, boxes, selected, onSelect]);
  const reset = (top: boolean) => { const v=view.current; if(v) {v.camera.position.set(...(top?[0,0,70]:[28,-38,28]) as [number,number,number]);v.controls.target.set(0,0,0);v.controls.update();} };
  return <div className="viewer"><div ref={host} className="canvas"/><div className="viewer-toolbar"><span>LiDAR TOP <b>{count.toLocaleString()} points</b></span><button onClick={()=>reset(true)}>Top view</button><button onClick={()=>reset(false)}>Reset view</button></div><div className="axis-note">X right · Y forward · Z up / meters</div>{(loading || error)&&<div className="viewer-message">{error || 'Loading real LiDAR…'}</div>}</div>;
}
