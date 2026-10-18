// v5: Preserve immutable model output; uncertainty is visible, never certified.
export {BONES,KEY_JOINTS,repairReplay} from './joint-policy-v4.js';
import {BONES,KEY_JOINTS} from './joint-policy-v4.js';
export const GROUPS={torso:{joints:[11,12,23,24],enter:.60,exit:.50},hinge:{joints:[13,14,25,26],enter:.65,exit:.50},distal:{joints:[15,16,27,28],enter:.70,exit:.55},detail:{joints:[0,1,2,3,4,5,6,7,8,9,10,17,18,19,20,21,22,29,30,31,32],enter:.70,exit:.55}};
export const DEFAULTS={recoverSamples:1,uncertainFloor:.35,predictionMs:150,maxSpeed:6,maxNormalizedSpeed:3,maxRepairMs:350,groups:GROUPS};
const finite=p=>p&&[p.x,p.y,p.z].every(Number.isFinite);
const copy=p=>({x:p.x,y:p.y,z:p.z});
const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);
export class JointTracker{
 constructor(options={}){this.options={...DEFAULTS,...options};this.reset();}
 reset(){this.context=null;this.lastPTS=null;this.previous=Array(33).fill('lost');this.history=Array.from({length:33},()=>[]);this.boneLengths=new Map();}
 observe(record,{missing=[]}={}){
  const context=`${record.clip}:${record.epoch}`;
  const contextReset=context!==this.context||record.source_pts_ms<=this.lastPTS;
  if(contextReset){this.reset();this.context=context;}
  const world=[],landmarks=[],states=[],reasons=[],confidence=[],transitions=[],groups=[],pts=record.source_pts_ms;
  for(let i=0;i<33;i++){
   const p=record.world_landmarks?.[i],q=record.landmarks?.[i],conf=Math.min(q?.visibility??0,q?.presence??0);confidence.push(conf);
   const group=Object.entries(GROUPS).find(([,v])=>v.joints.includes(i));groups.push(group[0]);const threshold=this.previous[i]==='measured'?group[1].exit:group[1].enter;
   let state='uncertain',reason='low_confidence_raw_observation';
   const safe=finite(p)&&finite(q)&&Math.max(Math.abs(p.x),Math.abs(p.y),Math.abs(p.z))<5&&q.x>-.5&&q.x<1.5&&q.y>-.5&&q.y<1.5;
   if(missing.includes(i)){state='lost';reason='synthetic_missing_mask';}
   else if(!safe){state='lost';reason='no_finite_or_bounded_observation';}
   else if(conf<this.options.uncertainFloor){state='lost';reason='below_uncertain_display_floor';}
   else if(conf>=threshold){state='measured';reason=null;}
   const h=this.history[i],last=h.at(-1),dt=last?(pts-last.pts)/1000:0;
   if(state==='measured'&&last&&dt>0&&dt<.5&&distance(p,last.world)>this.options.maxSpeed*dt+.10){state='uncertain';reason='implausible_joint_jump';}
   if(state==='measured')for(const [a,b]of BONES){if(a!==i&&b!==i)continue;const j=a===i?b:a,r=record.world_landmarks?.[j],rq=record.landmarks?.[j],baseline=this.boneLengths.get(`${a}:${b}`);if(!finite(r)||Math.min(rq?.visibility??0,rq?.presence??0)<.5)continue;const length=distance(p,r);if((baseline>.04&&(length>baseline*2.2+.05||length<baseline*.35))||length>1.3){state='uncertain';reason='implausible_bone_length';break;}}
   // A warm model may retain its previous ROI over a cut/loop. The first new-context
   // result is visible but uncertified; this is not a two-high-confidence recovery gate.
   if(contextReset&&record.model_reused_across_context&&state==='measured'){state='uncertain';reason='context_reacquisition';}
   world.push(state==='lost'?null:copy(p));landmarks.push(state==='lost'?null:copy(q));states.push(state);reasons.push(reason);
   if(state!==this.previous[i])transitions.push({joint:i,from:this.previous[i],to:state,reason,confidence:conf});
   if(state==='measured'){h.push({pts,world:copy(p),landmark:copy(q),frame_id:record.frame_id});if(h.length>2)h.shift();}
  }
  for(const[a,b]of BONES)if(states[a]==='measured'&&states[b]==='measured'){const key=`${a}:${b}`,n=distance(world[a],world[b]);this.boneLengths.set(key,this.boneLengths.has(key)?this.boneLengths.get(key)*.9+n*.1:n);}
  this.previous=states;this.lastPTS=pts;
  return{frame_id:record.frame_id,epoch:record.epoch,clip:record.clip,source_pts_ms:pts,world,landmarks,states,reasons,confidence,groups,transitions,measured_count:states.filter(s=>s==='measured').length,uncertain_count:states.filter(s=>s==='uncertain').length,lost_count:states.filter(s=>s==='lost').length,valid:KEY_JOINTS.every(i=>states[i]==='measured')};
 }
 predict(targetPTS){
  const world=[],landmarks=[],states=[],basis=[];
  for(let i=0;i<33;i++){
   const h=this.history[i],last=h.at(-1),prior=h.at(-2),age=last?targetPTS-last.pts:Infinity;
   if(!last||!prior||age<0||age>this.options.predictionMs||last.pts<=prior.pts||last.pts-prior.pts>500||this.previous[i]!=='measured'){world.push(null);landmarks.push(null);states.push('lost');basis.push(null);continue;}
   const dt=(last.pts-prior.pts)/1000,t=age/1000;
   const project=(field,cap)=>{const v={x:(last[field].x-prior[field].x)/dt,y:(last[field].y-prior[field].y)/dt,z:(last[field].z-prior[field].z)/dt},s=Math.min(1,cap/(Math.hypot(v.x,v.y,v.z)||1));return{x:last[field].x+v.x*t*s,y:last[field].y+v.y*t*s,z:last[field].z+v.z*t*s};};
   world.push(project('world',this.options.maxSpeed));landmarks.push(project('landmark',this.options.maxNormalizedSpeed));states.push('predicted');basis.push({last_source_pts_ms:last.pts,previous_source_pts_ms:prior.pts,horizon_ms:age,last_frame_id:last.frame_id});
  }return{source_pts_ms:targetPTS,world,landmarks,states,basis};
 }
}
