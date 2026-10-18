#!/usr/bin/env python3
import http.server, os, pathlib, json, subprocess, re, sys
ROOT=pathlib.Path(__file__).resolve().parent
os.chdir(ROOT)
(ROOT / "results").mkdir(parents=True, exist_ok=True)
class Handler(http.server.SimpleHTTPRequestHandler):
 def translate_path(self,path):
  path=path.split('?')[0]
  if path=='/': path='/public/index.html'
  elif not path.startswith(('/node_modules/','/assets/')):path='/public'+path
  return str(ROOT/path.lstrip('/'))
 def send_head(self):
  path=pathlib.Path(self.translate_path(self.path))
  try:
   path=path.resolve();path.relative_to(ROOT)
   f=path.open('rb');size=path.stat().st_size
  except (OSError,ValueError):self.send_error(404);return None
  start,end=0,size-1;partial=False
  header=self.headers.get('Range')
  if header:
   m=re.fullmatch(r'bytes=(\d*)-(\d*)',header.strip())
   if m:
    if m.group(1):start=int(m.group(1));end=min(end,int(m.group(2))) if m.group(2) else end
    elif m.group(2):start=max(0,size-int(m.group(2)))
    partial=True
  if start>=size or end<start:f.close();self.send_error(416);return None
  self.send_response(206 if partial else 200)
  self.send_header('Content-Type',self.guess_type(str(path)))
  self.send_header('Content-Length',str(end-start+1))
  self.send_header('Accept-Ranges','bytes')
  if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  self.end_headers();f.seek(start);self.copy_remaining=end-start+1
  return f
 def copyfile(self,source,outputfile):
  remaining=getattr(self,'copy_remaining',None)
  while remaining is None or remaining>0:
   block=source.read(min(65536,remaining) if remaining is not None else 65536)
   if not block:break
   outputfile.write(block)
   if remaining is not None:remaining-=len(block)
 def end_headers(self):
  self.send_header('Cross-Origin-Opener-Policy','same-origin');self.send_header('Cross-Origin-Embedder-Policy','require-corp');self.send_header('Cache-Control','no-store');super().end_headers()
 def do_POST(self):
  if self.path=='/save-results':
   data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   name=''.join(c for c in data['name'] if c.isalnum() or c in '-_')
   (ROOT/'results'/f'{name}.json').write_text(json.dumps(data['log']))
   self.send_response(200);self.end_headers();self.wfile.write(b'ok')
  else:self.send_response(404);self.end_headers()
port=int(sys.argv[1]) if len(sys.argv)>1 else 8765
print(f'POSE SERVER LISTENING http://127.0.0.1:{port}',flush=True)
http.server.ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
