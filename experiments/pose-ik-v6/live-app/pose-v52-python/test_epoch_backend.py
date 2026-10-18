"""Source-extracted unit checks. No MediaPipe import, model load, HTTP, or inference."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from epoch_clock import EpochClock

SOURCE = ast.parse(Path(__file__).with_name('server_epoch_modes.py').read_text())

class TooLarge(Exception):
    def __init__(self, max_size, actual_size):
        self.max_size=max_size; self.actual_size=actual_size

class FakeContent:
    def __init__(self,chunks):self.chunks=chunks
    async def iter_chunked(self,size):
        for chunk in self.chunks:yield chunk

def extracted(name, scope=None):
    if scope is None: body=SOURCE.body
    else: body=next(x for x in SOURCE.body if isinstance(x,ast.ClassDef) and x.name==scope).body
    node=next(x for x in body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name)
    module=ast.Module(body=[node],type_ignores=[])
    env={'web':SimpleNamespace(HTTPRequestEntityTooLarge=TooLarge)}
    exec(compile(ast.fix_missing_locations(module),'<source-extracted-unit>','exec'),env)
    return env,env[name]

class RequestLimitTests(unittest.TestCase):
    def test_small_body(self):
        _,read=extracted('read_limited');request=SimpleNamespace(content_length=4,content=FakeContent([b'ab',b'cd']))
        self.assertEqual(asyncio.run(read(request,4)),b'abcd')
    def test_known_length_rejected(self):
        _,read=extracted('read_limited');request=SimpleNamespace(content_length=2*1024*1024+1,content=FakeContent([]))
        with self.assertRaises(TooLarge):asyncio.run(read(request,2*1024*1024))
    def test_chunked_length_rejected(self):
        _,read=extracted('read_limited');request=SimpleNamespace(content_length=None,content=FakeContent([b'abcd',b'efgh']))
        with self.assertRaises(TooLarge):asyncio.run(read(request,6))
    def test_distinct_route_limits(self):
        constants={x.targets[0].id:eval(compile(ast.Expression(x.value),'<constant>','eval')) for x in SOURCE.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name) and x.targets[0].id in ('MAX_FRAME_BYTES','MAX_RESULTS_BYTES')}
        self.assertEqual(constants,{'MAX_FRAME_BYTES':2*1024*1024,'MAX_RESULTS_BYTES':128*1024*1024})

class PrepareTests(unittest.TestCase):
    def backend(self,policy):
        env,prepare=extracted('prepare','CpuBackend');env['EPOCH_POLICY']=policy
        self.creates=0
        def create():self.creates+=1;return 123
        obj=SimpleNamespace(epoch='a',calls=10,clock=EpochClock(policy),roi_history_retained=False,last_close_ms=100,last_create_ms=23,create_model=create)
        obj.clock.prepare('a');obj.clock.commit(1200,1200)
        return obj,lambda epoch:prepare(obj,epoch)
    def test_warm_retains_roi_without_close(self):
        obj,prepare=self.backend('warm');r=prepare('b')
        self.assertEqual(self.creates,0);self.assertFalse(r['tracker_reset']);self.assertTrue(r['tracker_roi_history_retained']);self.assertTrue(r['model_reused_across_context']);self.assertFalse(r['inference_performed']);self.assertEqual(obj.clock.last_model_ms,1200)
    def test_cold_resets_model(self):
        obj,prepare=self.backend('cold');r=prepare('b')
        self.assertEqual(self.creates,1);self.assertTrue(r['tracker_reset']);self.assertFalse(r['tracker_roi_history_retained']);self.assertEqual(r['backend_reset_ms'],123);self.assertEqual(obj.clock.last_model_ms,-1)
    def test_same_warm_epoch_retention_remains_visible(self):
        obj,prepare=self.backend('warm');prepare('b');r=prepare('b')
        self.assertTrue(r['tracker_roi_history_retained']);self.assertEqual(self.creates,0)

if __name__=='__main__':unittest.main()
