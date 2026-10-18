import subprocess,json,hashlib,pathlib
root=pathlib.Path(__file__).resolve().parents[1];p=root/'assets/videos/candidates-commons';o=p.parent/'seamless'
for stem,key in [('overhead-kettlebell-squat-720p','commons-overhead25'),('jumping-jacks-burpees-20s','commons-jumping2997'),('grands-battements-pirouettes-720p','commons-pirouettes25')]:
 src=p/(stem+'.mp4'); dst=o/(key+'.mp4')
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(src),'-c','copy','-an','-movflags','+frag_keyframe+empty_moov+default_base_moof+negative_cts_offsets','-y',str(dst)],check=True)
 def probe(f):return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,codec_tag_string,profile,level,width,height,time_base,duration,extradata:packet=pts_time,dts_time,duration_time,data_hash','-show_data_hash','sha256','-show_data','-of','json',str(f)]))
 a,b=probe(src),probe(dst); offset=float(b['packets'][0]['pts_time'])-float(a['packets'][0]['pts_time'])
 assert len(a['packets'])==len(b['packets'])
 assert all(abs(float(y['pts_time'])-float(x['pts_time'])-offset)<1e-6 for x,y in zip(a['packets'],b['packets']))
 assert [x['data_hash'] for x in a['packets']]==[x['data_hash'] for x in b['packets']]
 # AVCDecoderConfigurationRecord starts 01 profile compatibility level.
 avcc=b['streams'][0]['extradata'].split('\n')[1].split(':')[1].split('  ')[0].replace(' ','')
 codec='avc1.'+avcc[2:8]
 meta={'clip':key,'duration_seconds':float(a['streams'][0]['duration']),'src':'/assets/videos/seamless/'+dst.name,'mime':'video/mp4; codecs="'+codec+'"','fragment_pts_offset_seconds':offset,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'fragment_sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'packet_count':len(a['packets']),'packet_payload_hashes_identical':True,'presentation_timestamps_identical_after_offset':True,'frame_pts_ms':[float(x['pts_time'])*1000 for x in sorted(a['packets'],key=lambda x:float(x['pts_time']))],'stream':{k:v for k,v in b['streams'][0].items() if k!='extradata'}}
 (o/(key+'.json')).write_text(json.dumps(meta,indent=2));print(key,codec,offset)
