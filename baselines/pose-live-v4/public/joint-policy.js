// Causal per-joint quality gate. Raw model outputs are never edited.
export const BONES=[[0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],[11,12],[11,13],[13,15],[15,17],[15,19],[15,21],[17,19],[12,14],[14,16],[16,18],[16,20],[16,22],[18,20],[11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[29,31],[27,31],[24,26],[26,28],[28,30],[30,32],[28,32]];
export const KEY_JOINTS=[11,12,13,14,15,16,23,24,25,26,27,28];
export const DEFAULTS={enter:.65,exit:.5,lost:.35,recoverSamples:2,predictionMs:150,maxSpeed:6,maxNormalizedSpeed:3,maxRepairMs:350};
const finite=p=>p&&[p.x,p.y,p.z].every(Number.isFinite);
const dist=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);
const copy=p=>({x:p.x,y:p.y,z:p.z});
export class JointTracker{
 constructor(options={}){this.options={...DEFAULTS,...options};this.reset();}
 reset(){this.context=null;this.lastPTS=null;this.history=Array.from({length:33},()=>[]);this.previous=Array(33).fill('lost');this.streak=Array(33).fill(0);this.boneLengths=new Map();}
 observe(record,{missing=[]}={}){
  const context=`${record.clip}:${record.epoch}`;if(context!==this.context||record.source_pts_ms<=this.lastPTS){this.reset();this.context=context;}
  const o=this.options,pts=record.source_pts_ms,states=[],reasons=[],world=[],landmarks=[];
  for(let i=0;i<33;i++){
   const p=record.world_landmarks?.[i],q=record.landmarks?.[i];const confidence=Math.min(q?.visibility??0,q?.presence??0);let reason=null;
   if(missing.includes(i))reason='synthetic_missing_mask';else if(!finite(p)||!finite(q))reason='no_finite_observation';else if(confidence<o.lost)reason='confidence_lost';
   const h=this.history[i],last=h.at(-1),dt=last?(pts-last.pts)/1000:0;
   if(!reason&&last&&dt>0&&dt<.5&&dist(p,last.world)>o.maxSpeed*dt+.10)reason='implausible_joint_jump';
   if(!reason&&finite(p))for(const [a,b]of BONES){if(a!==i&&b!==i)continue;const j=a===i?b:a,r=record.world_landmarks?.[j],rq=record.landmarks?.[j],base=this.boneLengths.get(`${a}:${b}`);if(!finite(r)||Math.min(rq?.visibility??0,rq?.presence??0)<o.exit)continue;const length=dist(p,r);if((base&&base>.04&&(length>base*2.2+.05||length<base*.35))||length>1.3){reason='implausible_bone_length';break;}}
   const was=this.previous[i]==='measured';this.streak[i]=!reason&&confidence>=o.enter?this.streak[i]+1:0;
   const measured=!reason&&((was&&confidence>=o.exit)||this.streak[i]>=o.recoverSamples);
   const state=measured?'measured':reason&&['synthetic_missing_mask','no_finite_observation','confidence_lost'].includes(reason)?'lost':'uncertain';
   states.push(state);reasons.push(reason||(!measured?'confidence_or_recovery_hysteresis':null));
   world.push(measured?copy(p):null);landmarks.push(measured?copy(q):null);
   if(measured){h.push({pts,world:copy(p),landmark:copy(q),frame_id:record.frame_id});if(h.length>2)h.shift();}
  }
  for(const [a,b]of BONES)if(states[a]==='measured'&&states[b]==='measured'){const key=`${a}:${b}`,length=dist(world[a],world[b]);this.boneLengths.set(key,this.boneLengths.has(key)?this.boneLengths.get(key)*.9+length*.1:length);}
  this.previous=states;this.lastPTS=pts;
  return {frame_id:record.frame_id,epoch:record.epoch,clip:record.clip,source_pts_ms:pts,states,reasons,world,landmarks,measured_count:states.filter(s=>s==='measured').length,uncertain_count:states.filter(s=>s==='uncertain').length,lost_count:states.filter(s=>s==='lost').length,valid:KEY_JOINTS.every(i=>states[i]==='measured')};
 }
 predict(targetPTS){
  const horizon=this.options.predictionMs,world=[],landmarks=[],states=[],basis=[];
  for(let i=0;i<33;i++){
   const h=this.history[i],last=h.at(-1),prior=h.at(-2),age=last?targetPTS-last.pts:Infinity;
   if(!last||!prior||age<0||age>horizon||last.pts<=prior.pts||last.pts-prior.pts>500){world.push(null);landmarks.push(null);states.push('lost');basis.push(null);continue;}
   const dt=(last.pts-prior.pts)/1000,seconds=age/1000;
   function project(field,cap){const v={x:(last[field].x-prior[field].x)/dt,y:(last[field].y-prior[field].y)/dt,z:(last[field].z-prior[field].z)/dt};const speed=Math.hypot(v.x,v.y,v.z),scale=Math.min(1,cap/(speed||1));return{x:last[field].x+v.x*seconds*scale,y:last[field].y+v.y*seconds*scale,z:last[field].z+v.z*seconds*scale};}
   world.push(project('world',this.options.maxSpeed));landmarks.push(project('landmark',this.options.maxNormalizedSpeed));states.push('predicted');basis.push({last_source_pts_ms:last.pts,previous_source_pts_ms:prior.pts,horizon_ms:age,last_frame_id:last.frame_id});
  }return{source_pts_ms:targetPTS,world,landmarks,states,basis};
 }
}
export function repairReplay(records,{maxGapMs=DEFAULTS.maxRepairMs}={}){
 // Only copies are modified; a future valid bracket is required for every repaired joint.
 const out=records.map(r=>structuredClone(r));
 for(let i=0;i<33;i++)for(let k=0;k<out.length;k++){
  if(records[k].states[i]==='measured')continue;let a=k-1,b=k+1;
  while(a>=0&&records[a].states[i]!=='measured')a--;while(b<records.length&&records[b].states[i]!=='measured')b++;
  if(a<0||b>=records.length)continue;const p=records[a],q=records[b],r=records[k];const sameContext=[p,q].every(x=>x.epoch===r.epoch&&x.clip===r.clip);const gap=q.source_pts_ms-p.source_pts_ms;
  if(!sameContext||gap<=0||gap>maxGapMs||r.source_pts_ms<=p.source_pts_ms||r.source_pts_ms>=q.source_pts_ms)continue;
  // Every intermediate record must share context; never bridge reset/clip boundaries.
  if(records.slice(a,b+1).some(x=>x.epoch!==r.epoch||x.clip!==r.clip))continue;
  const t=(r.source_pts_ms-p.source_pts_ms)/gap;for(const field of ['world','landmarks'])out[k][field][i]={x:p[field][i].x*(1-t)+q[field][i].x*t,y:p[field][i].y*(1-t)+q[field][i].y*t,z:p[field][i].z*(1-t)+q[field][i].z*t};
  out[k].states[i]='repaired';(out[k].repairs??=[]).push({joint:i,left_frame_id:p.frame_id,right_frame_id:q.frame_id,bracket_ms:gap});
 }
 return out;
}
