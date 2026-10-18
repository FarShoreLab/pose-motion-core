import vm from 'node:vm';import fs from 'node:fs';import assert from 'node:assert/strict';
const timestamps=[],sent=[];let clock=10;
class OffscreenCanvas{getContext(){return{VERSION:1,RENDERER:2,getParameter:()=> 'test-gl'};}}
const ctx={OffscreenCanvas,performance:{timeOrigin:1000,now:()=>clock++},importScripts:()=>{},postMessage:(d,transfer)=>sent.push({d,transfer}),Vision:{FilesetResolver:{forVisionTasks:async()=>({})},PoseLandmarker:{createFromOptions:async()=>({detectForVideo:(bitmap,ts)=>{timestamps.push(ts);return {landmarks:[Array.from({length:33},()=>({x:.5,y:.5,z:0,visibility:.9,presence:.9}))],worldLandmarks:[Array.from({length:33},()=>({x:0,y:0,z:0}))]};}})}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(new URL('../public/pose-worker.js',import.meta.url),'utf8'),ctx);
await ctx.onmessage({data:{type:'init',origin:1000}});
for(const [epoch,pts]of [[1,0],[1,100],[2,0],[2,100],[3,0]]){const bitmap={close:()=>{throw new Error('unexpected close')}};await ctx.onmessage({data:{type:'frame',epoch,source_pts_ms:pts,source_fps:25,bitmap}});const r=sent.at(-1);assert.equal(r.d.bitmap,bitmap);assert.equal(r.transfer[0],bitmap);assert.equal(r.d.valid,true);assert(r.d.processing_end_ms>=r.d.processing_start_ms);}
assert(timestamps.every((v,i)=>i===0||v>timestamps[i-1]));assert.deepEqual(timestamps,[0,100,140,240,280]);assert.equal(sent.filter(r=>r.d.type==='result')[2].d.model_reused_across_context,true);console.log('PASS worker single-bitmap return, raw validity, shared clock and loop-monotonic timestamps');
