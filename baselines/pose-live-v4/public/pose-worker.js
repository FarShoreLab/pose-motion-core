importScripts('/node_modules/@mediapipe/tasks-vision/vision_bundle.js');
let model=null,origin=0,epoch=-1,offset=0,ready=false,resetChain=Promise.resolve();
const now=()=>performance.timeOrigin+performance.now()-origin;
async function setup(data){origin=data.origin;epoch=data.epoch;ready=false;if(model)model.close();
const t=now();const files=await Vision.FilesetResolver.forVisionTasks('/node_modules/@mediapipe/tasks-vision/wasm');
model=await Vision.PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/assets/pose_landmarker_lite.task',delegate:'CPU'},runningMode:'VIDEO',numPoses:1,minPoseDetectionConfidence:0.5,minPosePresenceConfidence:0.5,minTrackingConfidence:0.5,outputSegmentationMasks:false});
ready=true;postMessage({type:'ready',epoch,initialization_ms:now()-t,worker_time_origin:performance.timeOrigin,main_time_origin:origin});}
onmessage=async({data:d})=>{try{if(d.type==='reset'){ready=false;resetChain=resetChain.catch(()=>{}).then(()=>setup(d));await resetChain;return;}if(d.type==='frame'){if(!ready||d.epoch!==epoch){d.bitmap.close();postMessage({type:'discard',epoch:d.epoch});return;}const start=now();let result=model.detectForVideo(d.bitmap,d.source_pts_ms);const end=now();const raw=result.worldLandmarks?.[0]||[];const lm=result.landmarks?.[0]||[];
const key=[11,12,13,14,15,16,23,24,25,26,27,28];const confidence=lm.length?key.reduce((s,i)=>s+(lm[i].visibility??0),0)/key.length:0;const presence=lm.length?key.reduce((s,i)=>s+(lm[i].presence??0),0)/key.length:0;const valid=raw.length===33&&confidence>=0.5&&presence>=0.5&&raw.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.z));
d.bitmap.close();delete d.bitmap;postMessage({...d,type:'result',processing_start_ms:start,processing_end_ms:end,inference_ms:end-start,world_landmarks:raw,landmarks:lm,mean_key_visibility:confidence,mean_key_presence:presence,valid,pose_detection_score:null});}}
catch(e){postMessage({type:'error',message:e.stack||String(e),epoch:d.epoch});if(d.bitmap)d.bitmap.close();}};
