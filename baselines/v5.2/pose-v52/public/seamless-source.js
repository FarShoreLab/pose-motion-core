// Compressed media may buffer ahead; pose inference still receives only rVFC frames.
// Continuous PTS avoids native HTMLVideoElement seek/redecode stalls at each loop.
export class SeamlessSource {
 constructor(video, report){this.video=video;this.report=report;this.disposed=false;this.next=0;this.operation=null;this.startReady=false;}
 async open(key){
  const r=await fetch('/assets/videos/seamless/'+key+'.json');if(!r.ok)throw Error('Missing seamless manifest');this.manifest=await r.json();
  if(!globalThis.MediaSource||!MediaSource.isTypeSupported(this.manifest.mime))throw Error('MSE codec unsupported: '+this.manifest.mime);
  const data=await fetch(this.manifest.src);if(!data.ok)throw Error('Missing seamless fragment');this.bytes=await data.arrayBuffer();
  if(this.disposed)return;this.ms=new MediaSource();this.url=URL.createObjectURL(this.ms);this.video.loop=false;this.video.src=this.url;
  await new Promise((resolve,reject)=>{this.cancelOpen=resolve;this.ms.addEventListener('sourceopen',resolve,{once:true});this.ms.addEventListener('error',reject,{once:true});});
  if(this.disposed)return;this.sb=this.ms.addSourceBuffer(this.manifest.mime);this.sb.mode='segments';
  this.playable=new Promise(resolve=>{this.cancelReady=resolve;this.markReady=()=>{if(this.initialAppendDone&&!this.video.seeking&&this.video.readyState>=2){this.startReady=true;for(const name of ['loadeddata','canplay','seeked'])this.video.removeEventListener(name,this.markReady);resolve();}};for(const name of ['loadeddata','canplay','seeked'])this.video.addEventListener(name,this.markReady);});
  this.sb.addEventListener('error',()=>{if(!this.disposed)this.report('seamless_error',{message:'SourceBuffer error'});});
  this.sb.addEventListener('updateend',()=>{if(this.disposed)return;if(this.operation?.type==='append'&&this.operation.loop===0){this.initialAppendDone=true;if(this.manifest.fragment_pts_offset_seconds>0){this.video.currentTime=this.manifest.fragment_pts_offset_seconds;this.report('seamless_start_origin',{media_origin_seconds:this.manifest.fragment_pts_offset_seconds,pose_inference_performed:false});}this.markReady();}this.report('seamless_update',{operation:this.operation,buffered:this.ranges(),next_loop:this.next,source_time_seconds:this.video.currentTime});this.operation=null;this.pump();});
  this.tick=()=>this.pump();this.video.addEventListener('timeupdate',this.tick);this.report('seamless_ready',{manifest:this.manifest,media_timeline_origin_ms:this.manifest.fragment_pts_offset_seconds*1000,max_ahead_seconds:this.manifest.duration_seconds*2.25,max_behind_seconds:this.manifest.duration_seconds*2});this.pump();await this.playable;
 }
 ranges(){const a=[];for(let i=0;i<(this.sb?.buffered.length??0);i++)a.push([this.sb.buffered.start(i),this.sb.buffered.end(i)]);return a;}
 pump(){
  if(this.disposed||!this.sb||this.sb.updating||this.ms.readyState!=='open')return;
  const period=this.manifest.duration_seconds,origin=this.manifest.fragment_pts_offset_seconds,t=Math.max(0,this.video.currentTime-origin);
  // Keep at most roughly 2.25 periods ahead and 2 behind, no ever-growing queue.
  const removeEnd=(Math.floor(t/period)-1)*period+origin;
  if(removeEnd>0&&this.sb.buffered.length&&this.sb.buffered.start(0)<removeEnd-.001){this.operation={type:'remove',end:removeEnd};this.sb.remove(0,removeEnd);return;}
  if(this.next*period-t>=period*1.25)return;
  const offset=this.next*period;
  this.sb.timestampOffset=offset;this.operation={type:'append',loop:this.next,timestamp_offset_seconds:offset};this.report('seamless_append',this.operation);this.next++;this.sb.appendBuffer(this.bytes);
 }
 map(mediaSeconds){const p=this.manifest.duration_seconds,t=Math.max(0,mediaSeconds-this.manifest.fragment_pts_offset_seconds);const loop=Math.floor((t+1e-7)/p);return{loop,localPTS:Math.max(0,(t-loop*p)*1000),unwrappedPTS:t*1000};}
 dispose(){this.disposed=true;this.cancelOpen?.();this.cancelReady?.();if(this.markReady)for(const name of ['loadeddata','canplay','seeked'])this.video.removeEventListener(name,this.markReady);this.bytes=null;if(this.tick)this.video.removeEventListener('timeupdate',this.tick);if(this.url)URL.revokeObjectURL(this.url);}
}
