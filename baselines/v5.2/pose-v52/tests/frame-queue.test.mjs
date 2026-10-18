import assert from 'node:assert/strict';import {LatestFrameQueue} from '../public/frame-queue.js';
let closes=0;const f=(id,t)=>({row:{frame_id:id,scheduled_release_ms:t},bitmap:{close:()=>closes++}}),q=new LatestFrameQueue(),a=f(1,200),b=f(2,400);
q.offer(a);assert.equal(q.size,1);assert.equal(q.takeDue(199.999),null);assert.equal(q.size,1);assert.equal(q.takeDue(200),a);assert.equal(q.size,0);
q.offer(b);const c=f(3,600);q.offer(c);assert.equal(b.row.skip_reason,'superseded_pending_latest');assert.equal(closes,1);assert.equal(q.size,1);q.discard('epoch_reset');assert.equal(c.row.skip_reason,'epoch_reset');assert.equal(closes,2);assert.equal(q.size,0);q.discard('again');assert.equal(closes,2);
// Future-frame waiting is pending state, not an active Worker request; a previous
// in-flight frame can complete independently before takeDue dispatches this one.
const d=f(4,800);q.offer(d);assert.equal(q.takeDue(700),null);assert.equal(q.takeDue(800),d);assert.equal(closes,2);
const protectedQueue=new LatestFrameQueue(),near=f(5,1000),future=f(6,1200);protectedQueue.offer(near,900);assert.equal(protectedQueue.offer(future,999),false);assert.equal(future.row.skip_reason,'pending_nearest_release_protected');assert.equal(protectedQueue.frame,near);assert.equal(protectedQueue.takeDue(1000),near);
const elapsed=f(7,1400),newer=f(8,1500);protectedQueue.offer(elapsed,1600);protectedQueue.offer(newer,1600);assert.equal(elapsed.row.skip_reason,'superseded_pending_latest');assert.equal(protectedQueue.takeDue(1600),newer);
console.log('PASS bounded latest queue, explicit replacement/reset, exact close count, no early dispatch');
