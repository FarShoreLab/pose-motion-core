from isolation import ROOT
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

def main():
    p=ROOT/'diagnostics/visual-evaluation'
    detail=json.loads((p/'per-attempt-identity-decisions.json').read_text())
    annotation=json.loads((p/'per-frame-visual-annotations.json').read_text())
    fs=json.loads((p/'feature-separation.json').read_text())
    labels={'red_target':0,'wrong_blue_person':1,'ambiguous_people_overlap':2,'missing':3}
    names=['basketball-botsort-v1-model448-raw-seed-id2','basketball-deepocsort-gallery-v3-raw-seed-id2',
           'basketball-botsort-v1-model448','basketball-botsort-gallery-v2','basketball-botsort-gallery-v3']
    rows=[[labels[a['old_gvhmr_identity']] for a in annotation]]
    for name in names:rows.append([labels[x['identity']] for x in detail if x['attempt']==name])
    fig,axs=plt.subplots(2,1,figsize=(13,8.5),gridspec_kw={'height_ratios':[1.25,1]})
    cmap=ListedColormap(['#20ad72','#df4848','#e8b64f','#d6dce3'])
    axs[0].imshow(rows,aspect='auto',interpolation='nearest',cmap=cmap,vmin=0,vmax=3,extent=[0,207,5.5,-.5])
    axs[0].set_yticks(range(6),['Original GVHMR ID2','New BoT-SORT: initial ID2','Deep OC-SORT: initial ID2','Guard v1 (448)','Guard v2','Guard v3'])
    axs[0].set_xlabel('Input frame (30 fps; 207 input frames / 173 unique source frames)')
    axs[0].set_title('Basketball identity review: remaining missing observations make v3 unusable',loc='left',fontweight='bold')
    axs[0].legend(handles=[Patch(color=c,label=l) for c,l in zip(cmap.colors,['Red target','Wrong blue person','Ambiguous','Missing'])],loc='upper center',bbox_to_anchor=(.5,-.19),ncol=4,frameon=False)
    positive=[x['positive_anchor_cosine'] for x in fs];negative=[x['blue_anchor_cosine'] for x in fs if x['blue_anchor_cosine'] is not None]
    bins=np.linspace(0,1,26)
    axs[1].hist(positive,bins,alpha=.7,label='Clean target crops (n=120)',color='#20ad72')
    axs[1].hist(negative,bins,alpha=.65,label='Separated blue distractor crops (n=115)',color='#447ec2')
    axs[1].axvline(.7,color='#df4848',linestyle='--',label='v1 observation gate 0.70')
    axs[1].axvline(.78,color='#963b68',linestyle=':',label='v1 recovery gate 0.78')
    axs[1].set_xlabel('Cosine similarity to the immutable initial target view')
    axs[1].set_ylabel('Frames');axs[1].legend(fontsize=9,frameon=False)
    axs[1].set_title('First-view scores overlap: a fixed high cosine rejects true pose/view changes',loc='left')
    fig.text(.01,.01,'Assistant visual annotations, not independent human GT. Development-set diagnostic; no threshold search or held-out accuracy claim.',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1),h_pad=3)
    fig.savefig(ROOT/'evidence/identity-diagnostic.png',dpi=160)
    fig.savefig(ROOT/'evidence/identity-diagnostic.svg')
    print(str(ROOT/'evidence/identity-diagnostic.png'))
if __name__=='__main__':main()
