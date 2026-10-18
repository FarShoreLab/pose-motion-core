from isolation import ROOT
import json,subprocess,sys,time
from pathlib import Path

def main():
    folder=ROOT/'holdout-run-logs';folder.mkdir(exist_ok=False)
    scripts=Path(__file__).parent;receipts=[]
    for config in sorted(scripts.glob('holdout-r2_*.json')):
        clip=json.loads(config.read_text())['initialization']['clip']
        attempt='holdout-'+clip+'-v3'
        started=time.perf_counter()
        print('START '+clip,flush=True)
        with (folder/(clip+'.log')).open('w',encoding='utf-8') as log:
            process=subprocess.run([sys.executable,'-B','-X','utf8',str(scripts/'run_holdout_tracking.py'),
                '--clip',clip,'--attempt',attempt,'--policy',config.name],stdout=log,stderr=subprocess.STDOUT)
        receipt={'clip':clip,'attempt':attempt,'exit_code':process.returncode,'process_seconds':time.perf_counter()-started}
        summary=ROOT/'outputs'/attempt/'tracking-summary.json'
        if summary.exists():receipt['summary']=json.loads(summary.read_text())
        receipts.append(receipt)
        (folder/'batch-receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
        print(json.dumps({'clip':clip,'exit_code':process.returncode,'seconds':round(receipt['process_seconds'],2),
            'valid':receipt.get('summary',{}).get('observed_valid_frames'),'frames':receipt.get('summary',{}).get('frames')}),flush=True)
    if any(x['exit_code'] for x in receipts):sys.exit(1)
if __name__=='__main__':main()
