import subprocess,time,urllib.request,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
p=subprocess.Popen([sys.executable,str(root/'server.py'),'8877'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.2)
 file=root/'public/index.html';data=file.read_bytes()
 for spec,wanted in [('bytes=100-199',data[100:200]),('bytes=-20',data[-20:]),('bytes=100-',data[100:])]:
  r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8877/',headers={'Range':spec}));assert r.status==206;assert r.read()==wanted;assert r.headers.get('Accept-Ranges')=='bytes'
 print('HTTP byte-range, suffix-range and open-ended-range tests passed')
finally:p.terminate();p.wait()
