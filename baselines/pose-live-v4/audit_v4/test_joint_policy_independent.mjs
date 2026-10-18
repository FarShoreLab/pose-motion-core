import test from 'node:test';
import assert from 'node:assert/strict';
import {JointTracker, repairReplay, DEFAULTS} from '../public/joint-policy.js';
function raw(t, n, options={}) {
 const points=Array.from({length:33},(_,i)=>({x:i*.007+(options.shift||0),y:i*.001,z:0,visibility:.99,presence:.99}));
 return {clip:options.clip||'test',epoch:options.epoch||1,frame_id:n,source_pts_ms:t,world_landmarks:structuredClone(points),landmarks:structuredClone(points)};
}
function trackerReady(){const t=new JointTracker();t.observe(raw(0,1));t.observe(raw(50,2));t.observe(raw(100,3));return t;}
function freezeDeep(x){Object.freeze(x);for(const a of Object.values(x))if(a&&typeof a==='object'&&!Object.isFrozen(a))freezeDeep(a);return x;}
test('raw world, normalized coordinates and confidences remain byte-equivalent',()=>{
 const t=trackerReady(), r=raw(150,4);r.landmarks[13].visibility=.2;const before=JSON.stringify(r);freezeDeep(r);t.observe(r);t.predict(175);assert.equal(JSON.stringify(r),before);
});
test('loss stays local, unsupported joint and incident bone endpoints have null positions',()=>{
 const t=trackerReady(),r=raw(150,4);r.landmarks[13].visibility=.2;const p=t.observe(r);assert.equal(p.states[13],'lost');assert.equal(p.world[13],null);assert.equal(p.landmarks[13],null);assert.equal(p.states[14],'measured');assert.equal(p.valid,false);
});
test('missing confidence does not default to perfect',()=>{
 const t=trackerReady(),r=raw(150,4);delete r.landmarks[15].visibility;delete r.landmarks[15].presence;const p=t.observe(r);assert.equal(p.states[15],'lost');assert.equal(p.world[15],null);
});
test('nonfinite point is absent, even if confidence says good',()=>{
 const t=trackerReady(),r=raw(150,4);r.world_landmarks[15].z=NaN;assert.equal(t.observe(r).states[15],'lost');
});
test('two strong samples are required after confidence loss',()=>{
 const t=trackerReady(),r=raw(150,4);r.landmarks[15].presence=.1;t.observe(r);assert.notEqual(t.observe(raw(200,5)).states[15],'measured');assert.equal(t.observe(raw(250,6)).states[15],'measured');
});
test('synthetic missing mask is explicitly logged and leaves raw values intact',()=>{
 const t=trackerReady(),r=raw(150,4),p=t.observe(r,{missing:[13]});assert.equal(p.states[13],'lost');assert.equal(p.reasons[13],'synthetic_missing_mask');assert.equal(r.landmarks[13].visibility,.99);
});
test('live extrapolation never uses a future sample and expires beyond exact horizon',()=>{
 const t=trackerReady();let p=t.predict(250);assert.equal(p.states[15],'predicted');assert.equal(p.basis[15].horizon_ms,150);assert.equal(p.basis[15].last_source_pts_ms,100);p=t.predict(250.001);assert.equal(p.states[15],'lost');assert.equal(p.world[15],null);assert.equal(t.predict(99).states[15],'lost');
});
test('one observation is insufficient for velocity prediction',()=>{
 const t=new JointTracker({recoverSamples:1});t.observe(raw(100,1));assert.equal(t.predict(150).states[15],'lost');
});
test('epoch, clip, and backwards-time resets all clear prediction history',()=>{
 for(const options of [{epoch:2},{clip:'second'}]){const t=trackerReady();t.observe(raw(150,4,options));assert.equal(t.predict(175).states[15],'lost');}
 const t=trackerReady();t.observe(raw(20,4));assert.equal(t.predict(30).states[15],'lost');
});
test('long gaps cannot produce a new predicted trajectory',()=>{
 const t=trackerReady();t.observe(raw(750,4));assert.equal(t.predict(800).states[15],'lost');
});
test('prediction speed is bounded and all shown estimates are labeled predicted',()=>{
 const t=new JointTracker({recoverSamples:1,maxSpeed:.1,maxNormalizedSpeed:.1});t.observe(raw(0,1));t.observe(raw(100,2,{shift:.02}));const p=t.predict(200);assert(p.states.every(s=>s==='predicted'));const actual=p.world[15].x-raw(100,2,{shift:.02}).world_landmarks[15].x;assert(actual<=.010000001);
});
function replayFixture(times=[0,100,200]) {
 const t=new JointTracker({recoverSamples:1});return times.map((time,i)=>t.observe(raw(time,i+1),i===1?{missing:[15]}:{}));
}
test('short bracketed replay repair is purple-state data with both endpoint IDs',()=>{
 const records=replayFixture();const before=JSON.stringify(records);freezeDeep(records);const out=repairReplay(records);assert.equal(out[1].states[15],'repaired');assert.equal(out[1].repairs[0].left_frame_id,1);assert.equal(out[1].repairs[0].right_frame_id,3);assert.equal(JSON.stringify(records),before);assert.equal(records[1].world[15],null);
});
test('leading/trailing, long gaps and cross-epoch gaps remain missing in replay',()=>{
 let r=replayFixture();assert.notEqual(repairReplay(r.slice(0,2))[1].states[15],'repaired');assert.notEqual(repairReplay(r.slice(1))[0].states[15],'repaired');r=replayFixture([0,200,400]);assert.notEqual(repairReplay(r)[1].states[15],'repaired');r=replayFixture();r[2].epoch=2;assert.notEqual(repairReplay(r)[1].states[15],'repaired');
});
test('repair exact maxGap boundary is admitted, any larger bracket is not',()=>{
 assert.equal(repairReplay(replayFixture([0,100,350]))[1].states[15],'repaired');assert.notEqual(repairReplay(replayFixture([0,100,350.001]))[1].states[15],'repaired');
});
console.log('Independent policy tests: confidence means model confidence, not ground-truth occlusion; no visual/runtime verification implied.');
