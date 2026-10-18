// CPU model is selectable: original browser JS runtime, or separately identified Python CPU service.
let model=null,origin=0,lastTimestamp=-1,lastEpoch=null,baseOffset=0,backend='js',sessionId='',transport='rgba',input=null;
const now=()=>performance.timeOrigin+performance.now()-origin;
onmessage=async({data:d})=>{try{
 if(d.type==='init'){
  origin=d.origin;transport=d.transport||'rgba';backend=d.backend||'js';sessionId=d.session_id||String(d.origin);const start=now();
  if(backend==='python'){
   const response=await fetch('/health');if(!response.ok)throw new Error('Python backend health failed '+response.status);const health=await response.json();if(!health.ok)throw new Error('Python backend not ready');
   const prepareStart=now(),prepareResponse=await fetch('/prepare?'+new URLSearchParams({epoch:sessionId+':'+(d.initial_epoch??1)}),{method:'POST'});if(!prepareResponse.ok)throw new Error('Python tracker prepare failed '+prepareResponse.status);const preparation=await prepareResponse.json();
   postMessage({type:'capabilities',backend:'python',webgl_required:false,backend_health:health,preparation,preparation_http_ms:now()-prepareStart,preparation_has_image:false});
   postMessage({type:'ready',backend:'python',initialization_ms:now()-start,worker_time_origin:performance.timeOrigin,main_time_origin:origin,backend_health:health,preparation,preparation_has_image:false});return;
  }
  importScripts('/node_modules/@mediapipe/tasks-vision/vision_bundle.js');
  const glCanvas=new OffscreenCanvas(1,1),gl=glCanvas.getContext('webgl2')||glCanvas.getContext('webgl');
  postMessage({type:'capabilities',backend:'js',offscreen_canvas:true,webgl_required:true,webgl_available:!!gl,webgl_version:gl?.getParameter(gl.VERSION)??null,webgl_renderer:gl?.getParameter(gl.RENDERER)??null});
  if(!gl)throw new Error('Worker WebGL unavailable: MediaPipe JS CPU inference still requires a WebGL image-upload context. No inference was run.');
  const files=await Vision.FilesetResolver.forVisionTasks('/node_modules/@mediapipe/tasks-vision/wasm');
  model=await Vision.PoseLandmarker.createFromOptions(files,{canvas:glCanvas,baseOptions:{modelAssetPath:'/assets/pose_landmarker_lite.task',delegate:'CPU'},runningMode:'VIDEO',numPoses:1,minPoseDetectionConfidence:.5,minPosePresenceConfidence:.5,minTrackingConfidence:.5,outputSegmentationMasks:false});
  postMessage({type:'ready',backend:'js',initialization_ms:now()-start,worker_time_origin:performance.timeOrigin,main_time_origin:origin});return;
 }
 if(d.type!=='frame')return;
 const epochChanged=lastEpoch!==d.epoch,modelReused=epochChanged&&lastEpoch!==null;
 if(epochChanged){baseOffset=lastEpoch===null?0:Math.max(0,lastTimestamp+1000/d.source_fps-d.source_pts_ms);lastEpoch=d.epoch;}
 const timestamp=Math.max(lastTimestamp+.001,baseOffset+d.source_pts_ms);lastTimestamp=timestamp;
 const start=now();let raw,lm,inferenceMs,extra={};
 if(backend==='python'){
  if(!input||input.width!==d.bitmap.width||input.height!==d.bitmap.height)input=new OffscreenCanvas(d.bitmap.width,d.bitmap.height);const inputCtx=input.getContext('2d',{alpha:false,willReadFrequently:transport==='rgba'});inputCtx.drawImage(d.bitmap,0,0);
  const blob=transport==='rgba'?inputCtx.getImageData(0,0,input.width,input.height).data:await input.convertToBlob({type:'image/png'}),encoded=now();
  const backendEpoch=sessionId+':'+d.epoch;const query=new URLSearchParams({frame_id:d.frame_id,epoch:backendEpoch,source_pts_ms:d.source_pts_ms,source_fps:d.source_fps,...(transport==='rgba'?{encoding:'rgba',width:input.width,height:input.height}:{})});
  const response=await fetch('/infer?'+query,{method:'POST',headers:{'Content-Type':transport==='rgba'?'application/octet-stream':'image/png'},body:blob});
  if(!response.ok)throw new Error('Python inference HTTP '+response.status+': '+await response.text());
  const result=await response.json(),received=now();if(Number(result.frame_id)!==d.frame_id||String(result.epoch)!==backendEpoch||Math.abs(result.source_pts_ms-d.source_pts_ms)>.001)throw new Error('Python returned mismatched frame_id/epoch/source_pts_ms');
  if(typeof result.model_reused_across_context!=='boolean')throw new Error('Backend omitted tracker reuse policy');raw=result.world_landmarks?.[0]||[];lm=result.landmarks?.[0]||[];inferenceMs=result.inference_ms;
  extra={backend:'python',backend_epoch_policy:result.epoch_policy??'cold',backend_tracker_reset:result.tracker_reset,backend_model_reused_across_context:result.model_reused_across_context,backend_tracker_roi_history_retained:result.tracker_roi_history_retained??false,backend_source_pts_rounded_ms:result.source_pts_rounded_ms,backend_model_epoch_offset_ms:result.model_epoch_offset_ms,backend_previous_model_timestamp_ms:result.previous_model_timestamp_ms,backend_epoch_source_pts_start_ms:result.epoch_source_pts_start_ms,backend_pose_output_cache_used:result.pose_output_cache_used??false,backend_input_encoding:transport==='rgba'?'lossless RGBA8 sRGB from same exact 512px bitmap':'lossless PNG from same exact 512px bitmap',backend_input_bytes:blob.byteLength??blob.size,backend_input_encode_ms:encoded-start,backend_http_ms:received-encoded,backend_decode_ms:result.backend_decode_ms,backend_total_ms:result.backend_total_ms,backend_reset_ms:result.backend_reset_ms,backend_init_ms:result.backend_init_ms,backend_processing_ms:result.backend_processing_ms,backend_input_sha256:result.input_sha256,backend_input_dimensions:{width:result.input_width,height:result.input_height},backend_response_identity:{frame_id:result.frame_id,epoch:result.epoch,source_pts_ms:result.source_pts_ms,source_fps:result.source_fps},backend_expected_epoch:backendEpoch,backend_metadata:result.backend,backend_inference_start_monotonic_ms:result.backend_inference_start_monotonic_ms,backend_inference_end_monotonic_ms:result.backend_inference_end_monotonic_ms,backend_model_timestamp_ms:result.model_timestamp_ms,processing_interval_semantics:'browser worker encode + HTTP round trip bracket; inference_ms is separately measured backend duration'};
 }else{
  if(!model)throw new Error('Model not initialized');const result=model.detectForVideo(d.bitmap,timestamp);raw=result.worldLandmarks?.[0]||[];lm=result.landmarks?.[0]||[];inferenceMs=now()-start;extra={backend:'js',processing_interval_semantics:'synchronous browser model inference'};
 }
 const end=now(),key=[11,12,13,14,15,16,23,24,25,26,27,28];
 const confidence=lm.length?key.reduce((s,i)=>s+(lm[i].visibility??0),0)/key.length:0,presence=lm.length?key.reduce((s,i)=>s+(lm[i].presence??0),0)/key.length:0;
 const valid=raw.length===33&&confidence>=.5&&presence>=.5&&raw.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)&&Number.isFinite(p.z));
 // The exact input bitmap stays owned by this Worker until inference finishes.
 postMessage({...d,...extra,type:'result',processing_start_ms:start,processing_end_ms:end,worker_processing_total_ms:end-start,inference_ms:inferenceMs,model_timestamp_ms:backend==='python'?extra.backend_model_timestamp_ms:timestamp,model_reused_across_context:backend==='python'?extra.backend_model_reused_across_context:modelReused,backend_epoch_model_reset:backend==='python'?!!extra.backend_tracker_reset:false,world_landmarks:raw,landmarks:lm,mean_key_visibility:confidence,mean_key_presence:presence,valid,pose_detection_score:null},[d.bitmap]);
}catch(e){d.bitmap?.close();postMessage({type:'error',phase:d.type==='init'?'initialization':'inference',message:e.stack||String(e),epoch:d.epoch,frame_id:d.frame_id});}};
