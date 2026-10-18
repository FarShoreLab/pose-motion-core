import unittest, copy, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_raw import audit

def fixture():
 d={'observation':{'start_ms':1000,'end_ms':2000},'metadata':{'synthetic_fault_injection':False},'segments':[{'segment_id':1,'epoch':1,'wall_anchor_ms':1000,'source_anchor_ms':0,'playback_rate':1,'clip':'test'}],'frames':[],'inferences':[],'renders':[],'events':[],'replay_renders':[]}
 for n in range(3):
  pts=n*100;frame={'frame_id':n+1,'epoch':1,'segment_id':1,'clip':'test','source_pts_ms':pts,'scheduled_release_ms':1000+pts,'callback_ms':990+pts};d['frames'].append(frame)
  raw=[{'x':0,'y':0,'z':0,'visibility':1,'presence':1} for _ in range(33)];states=['measured']*33
  if n==1:raw[13]['visibility']=.2;states[13]='lost'
  filt={'frame_id':n+1,'epoch':1,'clip':'test','source_pts_ms':pts,'states':states,'reasons':[None]*33,'world':[{'x':0,'y':0,'z':0} if s=='measured' else None for s in states],'landmarks':[{'x':0,'y':0,'z':0} if s=='measured' else None for s in states],'valid':n!=1}
  inf={**frame,'dispatch_ms':1000+pts,'processing_start_ms':1001+pts,'processing_end_ms':1050+pts,'inference_ms':49,'result_received_ms':1051+pts,'render_submit_ms':1060+pts,'total_delay_ms':60,'disposition':'strict_paired','world_landmarks':copy.deepcopy(raw),'landmarks':raw,'filtered_observation':filt,'filtered_valid':n!=1,'valid':True,'display_frame_id':n+1,'observed_2d_frame_id':n+1,'observed_3d_frame_id':n+1,'display_pts_ms':pts,'pose_pts_ms':pts};d['inferences'].append(inf)
  d['renders'].append({'wall_ms':1060+pts,'epoch':1,'video_frame_id':n+1,'observed_2d_frame_id':n+1,'observed_3d_frame_id':n+1,'display_pts_ms':pts,'pose_pts_ms':pts,'sync_error_ms':0,'shown_joint_states':states[:],'new_observation':True,'new_valid_pose':n!=1})
 states=['lost']*33;bases=[None]*33;states[13]='predicted';bases[13]={'last_source_pts_ms':200,'previous_source_pts_ms':0,'horizon_ms':50,'last_frame_id':3}
 d['events'].append({'type':'prediction_preview','wall_ms':1300,'epoch':1,'target_source_pts_ms':250,'states':states,'basis':bases,'new_valid_pose':False})
 states=d['inferences'][1]['filtered_observation']['states'][:];states[13]='repaired';d['replay_renders']=[{'wall_ms':2100,'frame_id':2,'epoch':1,'source_pts_ms':100,'repair_enabled':True,'shown_joint_states':states,'repairs':[{'joint':13,'left_frame_id':1,'right_frame_id':3,'bracket_ms':200}]}]
 return d
class AuditTests(unittest.TestCase):
 def test_valid_fixture(self):self.assertTrue(audit(fixture())['pass'])
 def test_held_image_age_counts_full_visible_time(self):
  a=audit(fixture())['time_weighted_visible_image_age'];self.assertAlmostEqual(a['blank_ms'],60);self.assertAlmostEqual(a['paired_image_visible_ms'],940);self.assertAlmostEqual(a['max_ms'],800);self.assertAlmostEqual(a['p95_ms'],753)
 def test_reset_blanks_end_the_held_image_interval(self):
  d=fixture();d['events'].append({'type':'reset','wall_ms':1500});a=audit(d)['time_weighted_visible_image_age'];self.assertAlmostEqual(a['blank_ms'],560);self.assertAlmostEqual(a['paired_image_visible_ms'],440);self.assertAlmostEqual(a['max_ms'],300);self.assertAlmostEqual(a['p95_ms'],278)
 def bad(self,mut,code):
  d=fixture();mut(d);a=audit(d);self.assertFalse(a['pass']);self.assertIn(code,{x['code'] for x in a['errors']})
 def test_mismatched_frame(self):self.bad(lambda d:d['renders'][0].update(observed_2d_frame_id=3),'strict_video_2d_3d_frame_identity')
 def test_delay(self):self.bad(lambda d:d['inferences'][0].update(total_delay_ms=20),'total_includes_release_to_submit')
 def test_future_inference(self):self.bad(lambda d:d['inferences'][0].update(processing_start_ms=999),'causal_phase_order')
 def test_raw_rewrite(self):self.bad(lambda d:d['inferences'][0]['filtered_observation']['world'][0].update(x=1),'measured_coordinates_equal_raw')
 def test_prediction_detection(self):self.bad(lambda d:d['events'][0].update(new_valid_pose=True),'prediction_not_detection')
 def test_unbounded_prediction(self):self.bad(lambda d:d['events'][0].update(target_source_pts_ms=500),'prediction_bounded_causal')
 def test_future_prediction(self):self.bad(lambda d:d['events'][0].update(target_source_pts_ms=100),'past_only_prediction_basis')
 def test_cross_epoch_prediction(self):self.bad(lambda d:d['events'][0].update(epoch=2),'prediction_last_basis_same_epoch')
 def test_invalid_original_toggle(self):self.bad(lambda d:d['replay_renders'][0].update(repair_enabled=False),'original_toggle_preserves_observations')
 def test_invalid_repair_endpoint(self):self.bad(lambda d:d['replay_renders'][0]['repairs'][0].update(right_frame_id=2),'replay_actually_bracketed')
 def test_duplicate_counts(self):self.bad(lambda d:d['renders'].append(copy.deepcopy(d['renders'][0])),'unique_new_observations')
if __name__=='__main__':unittest.main()
