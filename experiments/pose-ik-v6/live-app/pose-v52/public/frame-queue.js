// Bounded released/future frame snapshots, separate from one inference in flight.
// Default1 preserves v5.1; v5.2 explicitly selects2 and records occupancy.
export class LatestFrameQueue{
 constructor({maxPending=1}={}){if(![1,2].includes(maxPending))throw Error('maxPending must be1 or2');this.maxPending=maxPending;this.frames=[];}
 get frame(){return this.frames[0]??null;}
 get size(){return this.frames.length;}
 close(frame,reason){frame.row.action='skip';frame.row.skip_reason=reason;frame.bitmap.close();}
 offer(frame,now=Infinity){
  if(this.maxPending===1){
   if(this.frame&&frame.row.scheduled_release_ms>now){this.close(frame,'pending_nearest_release_protected');return false;}
   if(this.frame)this.discard('superseded_pending_latest');this.frames=[frame];frame.row.action='queued';return true;
  }
  const candidates=[...this.frames,frame].sort((a,b)=>a.row.scheduled_release_ms-b.row.scheduled_release_ms);
  let keep=candidates;
  if(candidates.length>this.maxPending){
   const due=candidates.filter(f=>f.row.scheduled_release_ms<=now),future=candidates.filter(f=>f.row.scheduled_release_ms>now);
   // Keep latest due+nearest future; all-future keeps nearest2 to prevent starvation.
   keep=due.length&&future.length?[due.at(-1),future[0]]:due.length?due.slice(-2):future.slice(0,2);
   for(const f of candidates)if(!keep.includes(f))this.close(f,f.row.scheduled_release_ms>now?'pending_future_capacity':'superseded_pending_latest');
  }
  this.frames=keep;if(keep.includes(frame)){frame.row.action='queued';return true;}return false;
 }
 discard(reason){for(const f of this.frames)this.close(f,reason);this.frames=[];}
 takeDue(now){
  const due=this.frames.filter(f=>f.row.scheduled_release_ms<=now);if(!due.length)return null;
  this.frames=this.frames.filter(f=>f.row.scheduled_release_ms>now);
  for(const f of due.slice(0,-1))this.close(f,'superseded_due_at_dispatch');return due.at(-1);
 }
}
