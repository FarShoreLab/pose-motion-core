import assert from 'node:assert/strict';
import fs from 'node:fs';
import {SeamlessSource} from '../public/seamless-source.js';
for(const key of ['commons-overhead25','commons-jumping2997','commons-pirouettes25']){
 const manifest=JSON.parse(fs.readFileSync(new URL('../assets/videos/seamless/'+key+'.json',import.meta.url)));
 const source=new SeamlessSource({},()=>{});source.manifest=manifest;
 let n=0;for(let lap=0;lap<1000;lap++)for(const pts of manifest.frame_pts_ms){const u=lap*manifest.duration_seconds+pts/1000+manifest.fragment_pts_offset_seconds;const got=source.map(u);assert.equal(got.loop,lap);assert(Math.abs(got.localPTS-pts)<1e-6);assert(Math.abs(got.unwrappedPTS-(u-manifest.fragment_pts_offset_seconds)*1000)<1e-6);n++;}
 assert.equal(source.map(manifest.duration_seconds+manifest.fragment_pts_offset_seconds).loop,1);
 assert.equal(source.map(manifest.duration_seconds+manifest.fragment_pts_offset_seconds).localPTS,0);
 console.log('PASS source mapping',key,n,'exact frame/lap identities across1000loops');
}
// A newer eligible completed capture replaces old pending before dispatch.
const {LatestFrameQueue}=await import('../public/frame-queue.js');const q=new LatestFrameQueue();const closed=[];
const f=(id,release)=>({row:{frame_id:id,scheduled_release_ms:release},bitmap:{close:()=>closed.push(id)}});
q.offer(f(1,10),10);q.offer(f(2,20),30);assert.equal(q.takeDue(30).row.frame_id,2);assert.deepEqual(closed,[1]);
q.offer(f(3,40),50);q.offer(f(4,80),50);assert.equal(q.takeDue(50).row.frame_id,3);assert.deepEqual(closed,[1,4]);
console.log('PASS latest eligible offer-before-pump and future protection');

const bounded=new LatestFrameQueue({maxPending:2});bounded.offer(f(10,100),60);bounded.offer(f(11,133),80);assert.equal(bounded.size,2);assert.equal(bounded.takeDue(99),null);assert.equal(bounded.takeDue(100).row.frame_id,10);assert.equal(bounded.takeDue(133).row.frame_id,11);assert.equal(bounded.size,0);console.log("PASS two pending snapshots preserve early callbacks, no early dispatch");
