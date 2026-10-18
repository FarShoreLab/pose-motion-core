import argparse,csv,gc,json,os,pathlib,sys,threading,time,traceback,zipfile
from isolate_env import ROOT as root
repo=root/'src'/'GVHMR-ee960bb6e2ea2d381aa97f08e9b71ef320b624b1'
sys.path[:0]=[str(repo),str(root/'src'/'pytorch3d-0.7.6')]

os.chdir(repo)
parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['preflight','modelcheck','bbox','vitpose','hmr2','vo','gvhmr'],required=True);parser.add_argument('--name',default='smoke');parser.add_argument('--device',default='cuda');parser.add_argument('--precision',choices=['float32','float16'],default='float16');parser.add_argument('--camera',choices=['static','simplevo'],default='static');parser.add_argument('--vo-scale',type=float,default=.5);args=parser.parse_args()
out=root/'outputs'/args.name;out.mkdir(parents=True,exist_ok=True)
import numpy as np,psutil,torch
torch.set_num_threads(4)
process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
def monitor():
    while not stop.wait(.1):peak[0]=max(peak[0],process.memory_info().rss)
threading.Thread(target=monitor,daemon=True).start()
metrics={'stage':args.stage,'torch':torch.__version__,'python':sys.version,'device':args.device,'precision':args.precision if args.stage in ('vitpose','hmr2') else 'float32','batch_size':1 if args.stage in ('vitpose','hmr2') else None,'mode':'offline; future frames available','memory_sampling_interval_s':.1}
started=time.perf_counter()
def sync():
    if args.device=='cuda':torch.cuda.synchronize()
def save_metrics(status):
    metrics['status']=status;metrics['wall_seconds']=time.perf_counter()-started;metrics['peak_rss_bytes_sampled']=max(peak[0],process.memory_info().rss)
    if torch.cuda.is_available():
        metrics['gpu_peak_allocated_bytes']=torch.cuda.max_memory_allocated();metrics['gpu_peak_reserved_bytes']=torch.cuda.max_memory_reserved();metrics['gpu_free_bytes_at_end']=torch.cuda.mem_get_info()[0]
    (out/(args.stage+'-metrics.json')).write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    stop.set();print(json.dumps(metrics),flush=True)
def timed(name,fn):
    sync();begin=time.perf_counter();value=fn();sync();metrics[name+'_seconds']=time.perf_counter()-begin;return value
def load_demo_config():
    # Register the same inference components as the official demo, without training/renderer imports.
    from hmr4d.model.gvhmr.gvhmr_pl_demo import DemoPL
    from hmr4d.model.gvhmr.utils.endecoder import EnDecoder
    from hmr4d.network.gvhmr.relative_transformer import NetworkEncoderRoPE
    from hydra import initialize_config_module,compose
    from omegaconf import OmegaConf
    with initialize_config_module(version_base='1.3',config_module='hmr4d.configs'):
        cfg=compose(config_name='demo',overrides=['video_name='+args.name,'static_cam='+str(args.camera=='static')])
    OmegaConf.save(cfg,out/'effective-demo-config.yaml')
    return cfg
def to_cpu(x):
    if isinstance(x,torch.Tensor):return x.detach().cpu()
    if isinstance(x,dict):return {k:to_cpu(v) for k,v in x.items()}
    if isinstance(x,list):return [to_cpu(v) for v in x]
    return x
try:
    assert torch.cuda.is_available() or args.device=='cpu','CUDA is unavailable'
    if args.device=='cuda':
        metrics['gpu_name']=torch.cuda.get_device_name();metrics['gpu_free_bytes_at_start']=torch.cuda.mem_get_info()[0];torch.cuda.reset_peak_memory_stats()
    if args.stage=='preflight':
        from pytorch3d.transforms import axis_angle_to_matrix
        from hmr4d.utils.preproc import Tracker,Extractor,VitPoseExtractor
        from hmr4d.model.gvhmr.gvhmr_pl_demo import DemoPL
        from hmr4d.utils.body_model.smplx_lite import SmplxLiteV437Coco17
        rotation=axis_angle_to_matrix(torch.zeros(1,3,device=args.device))
        assert torch.allclose(rotation,torch.eye(3,device=args.device)[None])
        metrics['imports']='passed';metrics['pytorch3d']='official v0.7.6 Python source; transforms only; native renderer/KNN unavailable'
    elif args.stage=='modelcheck':
        from hydra.utils import instantiate
        from omegaconf import OmegaConf
        cfg=load_demo_config()
        model=timed('model_construct',lambda:instantiate(cfg.model,_recursive_=False))
        checkpoint=root/'assets/checkpoints/gvhmr/gvhmr_siga24_release.ckpt'
        state=timed('checkpoint_read',lambda:torch.load(checkpoint,map_location='cpu',mmap=zipfile.is_zipfile(checkpoint))['state_dict'])
        mismatch=model.load_state_dict(state,strict=False)
        metrics['missing_checkpoint_keys']=mismatch.missing_keys;metrics['unexpected_checkpoint_keys']=mismatch.unexpected_keys
        assert not (set(mismatch.missing_keys)&dict(model.named_parameters()).keys())
        metrics['learned_parameters']=sum(p.numel() for p in model.parameters())
        metrics['learned_parameters_finite']=all(torch.isfinite(p).all().item() for p in model.parameters())
        metrics['pose_inference_executed']=False
        assert metrics['learned_parameters_finite']
    else:
        video=out/'input_30fps.mp4';mapping=list(csv.DictReader((out/'frame-map.csv').open(encoding='utf-8')));length=len(mapping)
        assert np.allclose(np.diff([float(x['input_seconds']) for x in mapping]),1/30)
        metrics['frames']=length
        if args.stage=='vo':
            from hmr4d.utils.preproc.relpose.simple_vo import SimpleVO
            import pycolmap
            from hmr4d.utils.preproc.relpose.solver_two_view import TwoPairSolver
            original_solve=TwoPairSolver.solve
            pair_calls=[];sample_indices=list(range(0,length,8))
            if sample_indices[-1]!=length-1:sample_indices.append(length-1)
            def audited_solve(self,points0,points1):
                i=len(pair_calls);a,b=sample_indices[i:i+2]
                rec={'pair_index':i,'input_frames':[a,b],'input_seconds':[a/30,b/30],'source_seconds':[float(mapping[a]['source_seconds']),float(mapping[b]['source_seconds'])],'matched_points':len(points0)}
                pair_calls.append(rec);begin=time.perf_counter()
                try:
                    value=original_solve(self,points0,points1);rec['status']='completed';return value
                except Exception as error:
                    rec['status']='failed';rec['error_type']=type(error).__name__;rec['error']=str(error);raise
                finally:
                    rec['seconds']=time.perf_counter()-begin
                    (out/'vo-pair-audit.json').write_text(json.dumps(pair_calls,indent=2),encoding='utf-8')
            TwoPairSolver.solve=audited_solve
            estimator=SimpleVO(str(video),scale=args.vo_scale,step=8,method='sift',num_workers=1)
            trajectory=timed('camera_rotation_estimation',estimator.compute)
            assert trajectory.shape==(length,4,4) and np.isfinite(trajectory).all()
            R=trajectory[:,:3,:3]
            assert np.allclose(R@R.transpose(0,2,1),np.eye(3),atol=1e-4)
            assert np.allclose(np.linalg.det(R),1,atol=1e-4)
            angles=np.degrees(np.arccos(np.clip((np.trace(R,axis1=1,axis2=2)-1)/2,-1,1)))
            np.save(out/'simplevo_trajectory.npy',trajectory)
            metrics['pycolmap']=pycolmap.__version__;metrics['max_camera_rotation_from_start_degrees']=float(angles.max())
            metrics['vo_scale']=args.vo_scale
            metrics['camera']=f'Official SimpleVO: SIFT, {args.vo_scale} image scale, step 8, 24mm assumption, serial; interpolation uses future frames; no camera ground truth'
        elif args.stage=='bbox':
            from hmr4d.utils.preproc import Tracker
            from hmr4d.utils.geo.hmr_cam import get_bbx_xys_from_xyxy
            tracker=timed('model_load',lambda:Tracker(device=args.device))
            history=timed('tracking',lambda:tracker.track(str(video)))
            assert len(history)==length
            (out/'yolo_raw_detections.json').write_text(json.dumps(history,default=lambda x:x.tolist() if isinstance(x,np.ndarray) else x),encoding='utf-8')
            tracker.track=lambda _:history
            boxes=timed('official_bbox_interpolation_and_smoothing',lambda:tracker.get_one_track(str(video)).float())
            xys=get_bbx_xys_from_xyxy(boxes,base_enlarge=1.2).float()
            assert torch.isfinite(xys).all()
            torch.save({'bbx_xyxy':boxes,'bbx_xys':xys},out/'bbox.pt')
            metrics['raw_frames_with_no_tracks']=sum(not x for x in history)
            ids,_,ranked=Tracker.sort_track_length(history,str(video))
            chosen=ranked[0];present=set(ids[chosen])
            metrics['selected_track_id']=chosen
            metrics['selected_track_observed_frames']=sorted(present)
            metrics['selected_track_missing_frames']=[i for i in range(length) if i not in present]
            metrics['selected_track_interpolated_or_edge_held_rate']=len(metrics['selected_track_missing_frames'])/length
            metrics['all_track_ids_by_area_rank']=ranked
            metrics['bbox_processing']='Official largest area track, missing-frame linear interpolation, two 5-frame moving averages; raw detections retained.'
        elif args.stage in ('vitpose','hmr2'):
            from hmr4d.utils.preproc import VitPoseExtractor,Extractor
            boxes=torch.load(out/'bbox.pt',map_location='cpu')['bbx_xys']
            factory=VitPoseExtractor if args.stage=='vitpose' else Extractor
            dtype=torch.float16 if args.precision=='float16' else torch.float32
            extractor=timed('model_load',lambda:factory(device=args.device,batch_size=1,dtype=dtype))
            model=extractor.pose if args.stage=='vitpose' else extractor.extractor
            if args.precision=='float16':model.half()
            with torch.inference_mode():
                result=timed('feature_extraction',lambda:extractor.extract(str(video),boxes) if args.stage=='vitpose' else extractor.extract_video_features(str(video),boxes))
            result=result.float().cpu();assert torch.isfinite(result).all();assert result.shape[0]==length
            torch.save(result,out/(args.stage+'.pt'));metrics['output_shape']=list(result.shape)
        else:
            from hydra.utils import instantiate
            from omegaconf import OmegaConf
            from hmr4d.utils.geo.hmr_cam import estimate_K,normalize_kp2d
            from hmr4d.utils.geo_transform import compute_cam_angvel
            import av
            with av.open(str(video)) as c:width=c.streams.video[0].width;height=c.streams.video[0].height
            boxes=torch.load(out/'bbox.pt',map_location='cpu')['bbx_xys'];kps=torch.load(out/'vitpose.pt',map_location='cpu');features=torch.load(out/'hmr2.pt',map_location='cpu')
            K=estimate_K(width,height).repeat(length,1,1)
            rotations=torch.eye(3).repeat(length,1,1) if args.camera=='static' else torch.from_numpy(np.load(out/'simplevo_trajectory.npy')[:,:3,:3]).float()
            data={'length':torch.tensor(length),'bbx_xys':boxes,'kp2d':kps,'K_fullimg':K,'cam_angvel':compute_cam_angvel(rotations),'f_imgseq':features}
            torch.save(data,out/'gvhmr_real_features.pt')
            cfg=load_demo_config()
            model=timed('model_construct',lambda:instantiate(cfg.model,_recursive_=False))
            checkpoint=root/'assets/checkpoints/gvhmr/gvhmr_siga24_release.ckpt'
            def load_weights():
                state=torch.load(checkpoint,map_location='cpu',mmap=zipfile.is_zipfile(checkpoint))['state_dict']
                mismatch=model.load_state_dict(state,strict=False)
                metrics['missing_checkpoint_keys']=mismatch.missing_keys;metrics['unexpected_checkpoint_keys']=mismatch.unexpected_keys
                missing_parameters=set(mismatch.missing_keys)&dict(model.named_parameters()).keys()
                assert not missing_parameters,'Missing learned weights: '+str(missing_parameters)
            timed('checkpoint_load',load_weights);model=model.eval().to(args.device)
            batch={'length':data['length'][None],'obs':normalize_kp2d(kps,boxes)[None],'bbx_xys':boxes[None],'K_fullimg':K[None],'cam_angvel':data['cam_angvel'][None],'f_imgseq':features[None]}
            batch={k:v.to(args.device) for k,v in batch.items()}
            with torch.inference_mode():
                raw=timed('network_raw',lambda:model.pipeline.forward(batch,train=False,postproc=False,static_cam=args.camera=='static'))
                raw=to_cpu(raw);torch.save(raw,out/'gvhmr_raw.pt')
                (out/'raw-output-ready.json').write_text(json.dumps({'perf_counter':time.perf_counter(),'definition':'raw official model tensor output serialized to gvhmr_raw.pt; numerical FK export and optional second postprocessing forward follow'}),encoding='utf-8')
                processed=timed('network_official_postprocess',lambda:model.pipeline.forward(batch,train=False,postproc=True,static_cam=args.camera=='static'))
                processed=to_cpu(processed);torch.save(processed,out/'gvhmr_official_postprocessed.pt')
                arrays={'timestamps_s':np.arange(length)/30,'K_fullimg':K.numpy(),'vitpose_coco17':kps.numpy()}
                for label,result in [('raw',raw),('official_postprocessed',processed)]:
                    for space in ('incam','global'):
                        params=result['pred_smpl_params_'+space]
                        for key,value in params.items():arrays[label+'_'+space+'_'+key]=value[0].numpy()
                        joints=model.pipeline.endecoder.fk_v2(**{k:v.to(args.device) for k,v in params.items()})[0].cpu().numpy()
                        arrays[label+'_'+space+'_joints22']=joints
                assert all(np.isfinite(a).all() for a in arrays.values())
                np.savez_compressed(out/'gvhmr_predictions.npz',**arrays)
            metrics['camera']=args.camera+'; focal length estimated by official heuristic; not calibrated'
            metrics['raw_and_postprocessed_retained']=True
    save_metrics('completed')
except Exception as e:
    metrics['error_type']=type(e).__name__;metrics['error']=str(e);metrics['traceback']=traceback.format_exc();save_metrics('failed');raise
