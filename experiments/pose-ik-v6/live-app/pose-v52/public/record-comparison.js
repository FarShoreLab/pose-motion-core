// Optional recording of the actual currently displayed canvases; no offline render.
// Captured duplicate/held frames and live latency are retained at wall-clock speed.
const captureParams=new URLSearchParams(location.search);
if(captureParams.get('capture')==='1'){
 const out=document.createElement('canvas');out.width=1440;out.height=800;const cx=out.getContext('2d');
 const status=document.createElement('div');status.id='recordingStatus';status.textContent='录制待机：当前现场画布，1×墙钟';document.body.appendChild(status);
 let rec=null,chunks=[],started=0,stopped=false,last=0;
 const paint=(now)=>{requestAnimationFrame(paint);if(now-last<1000/30)return;last=now;const demo=window.poseDemo;if(!demo)return;
  if(demo.running&&!rec){const stream=out.captureStream(30);const mime=MediaRecorder.isTypeSupported('video/webm;codecs=vp9')?'video/webm;codecs=vp9':'video/webm';rec=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:3500000});rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};rec.onstop=()=>{const b=new Blob(chunks,{type:mime});const a=document.createElement('a');a.id='captureDownload';a.textContent='下载本次现场对比录屏';a.href=URL.createObjectURL(b);a.download=(captureParams.get('name')||'live-ik')+'.webm';document.body.appendChild(a);status.textContent='录屏已完成（现场墙钟速度） '+(b.size/1024/1024).toFixed(1)+' MB';};rec.start(1000);started=now;status.textContent='正在录制现场三画面，1×墙钟速度';demo.log.metadata.live_recording={method:'canvas captureStream(30) MediaRecorder; actual displayed canvases, no postprocessed replay',dimensions:[1440,800],bitrate:3500000,recording_overhead_included:true};}
  cx.fillStyle='#0b1521';cx.fillRect(0,0,1440,800);cx.fillStyle='#f6f7fa';cx.font='bold 24px sans-serif';cx.fillText('OpenSim IK / EXPERIMENTAL LIVE COMPARISON',24,35);cx.font='16px sans-serif';cx.fillStyle='#d5a5ff';cx.fillText('1x live display capture | Fixed bones + clamped joint ranges | NOT verified motion truth',24,65);
  const ids=['matched','#view3d canvas','#preview3d canvas'];const heads=['Same-frame video + observed 2D','Raw v5.2 3D (original observations)','Constrained fit (NOT new observations)'];
  for(let i=0;i<3;i++){const x=i*480;cx.fillStyle='#1b2c3e';cx.fillRect(x+8,88,464,625);cx.fillStyle='#ffffff';cx.font='17px sans-serif';cx.fillText(heads[i],x+18,116);const canvas=i===0?document.getElementById(ids[i]):document.querySelector(ids[i]);if(canvas&&canvas.width&&canvas.height){const scale=Math.min(454/canvas.width,575/canvas.height);const w=canvas.width*scale,h=canvas.height*scale;cx.drawImage(canvas,x+240-w/2,135+(575-h)/2,w,h);}}
  cx.font='16px sans-serif';cx.fillStyle='#dfebf3';cx.fillText((document.getElementById('frameLabel')?.textContent||'')+' | '+(document.getElementById('predictState')?.textContent||''),20,743);cx.fillStyle='#bccddb';cx.fillText('Blue = fitted; coral dashed = inferred, never measured. Recording wall time '+((now-started)/1000).toFixed(1)+'s',20,775);
  if(rec&&!stopped&&(demo.finished||demo.failed)){stopped=true;rec.stop();}
 };requestAnimationFrame(paint);
}
