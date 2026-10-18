"""Small auditable joint partial assignment; labels/left-right order are never inputs to costs."""
import itertools
import numpy as np
from scipy.optimize import linear_sum_assignment

def unit(v):
    a=np.asarray(v,dtype=np.float64)
    return a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-12)
def center(b):return (np.asarray(b[:2])+np.asarray(b[2:4]))*.5
def scale(b):return np.maximum(np.asarray(b[2:4])-np.asarray(b[:2]),1.)
def iou(a,b):
    inter=np.maximum(0,np.minimum(a[2:4],b[2:4])-np.maximum(a[:2],b[:2])).prod()
    return float(inter/max(np.prod(scale(a))+np.prod(scale(b))-inter,1e-9))
def overlap(a,b):
    inter=np.maximum(0,np.minimum(a[2:4],b[2:4])-np.maximum(a[:2],b[:2])).prod()
    return float(inter/max(min(np.prod(scale(a)),np.prod(scale(b))),1e-9))
def velocity(tracklet):
    frames=np.array(tracklet['frames'][-4:],float);boxes=np.array(tracklet['boxes'][-4:])
    if len(frames)<2:return np.zeros(2)
    xy=(boxes[:,:2]+boxes[:,2:4])*.5
    dt=frames-frames.mean();den=float(dt@dt)
    return dt@(xy-xy.mean(0))/max(den,1e-9)
def pair_cost(before,after,c):
    a,b=unit(before['features']),unit(after['features'])
    cross=a@b.T
    similarity=float(.5*(np.median(cross.max(1))+np.median(cross.max(0))))
    ba,bb=np.asarray(before['boxes'][-1]),np.asarray(after['boxes'][0])
    va,vb=velocity(before),velocity(after)
    gap=max(after['frames'][0]-before['frames'][-1],1)
    diagonal=max(np.linalg.norm(scale(ba)),np.linalg.norm(scale(bb)),1.)
    uncertainty=diagonal*(1+.10*gap)
    forward=np.linalg.norm(center(bb)-(center(ba)+va*gap))
    backward=np.linalg.norm(center(ba)-(center(bb)-vb*gap))
    motion=float(min(1.,.5*(forward+backward)/uncertainty))
    size=float(min(1.,np.abs(np.log(scale(bb)/scale(ba))).mean()))
    direction=float((1-np.dot(va,vb)/(np.linalg.norm(va)*np.linalg.norm(vb)))/2) if min(np.linalg.norm(va),np.linalg.norm(vb))>.2 else .5
    cost=c['association_appearance_weight']*(1-similarity)+c['association_motion_weight']*motion+c['association_scale_weight']*size+c['association_direction_weight']*direction
    return {'cost':float(cost),'appearance_similarity':similarity,'motion_cost':motion,'scale_cost':size,
        'direction_cost':direction,'gap_frames':gap,'velocity_before':va.tolist(),'velocity_after':vb.tolist()}

def partial_assignments(costs,unmatched):
    """Enumerate unique partial matchings for small conflict groups, including birth/death dummies.

    Each unmatched before/after endpoint pays its own penalty. Dummy permutations
    are represented only once, so second-best means a different physical assignment.
    """
    costs=np.asarray(costs,float)
    n,m=costs.shape
    if max(n,m)>7:raise ValueError('Small conflict group limit exceeded; leave unresolved instead of factorial expansion')
    options=[]
    def visit(i,chosen,used,total):
        if i==n:
            options.append({'cost':float(total+unmatched*(m-len(used))),
                'pairs':[[k,j] for k,j in enumerate(chosen) if j is not None],
                'unmatched_before':[k for k,j in enumerate(chosen) if j is None],
                'unmatched_after':[j for j in range(m) if j not in used]})
            return
        visit(i+1,chosen+[None],used,total+unmatched)
        for j in range(m):
            if j not in used and np.isfinite(costs[i,j]):visit(i+1,chosen+[j],used|{j},total+costs[i,j])
    visit(0,[],set(),0.)
    return sorted(options,key=lambda x:(x['cost'],x['pairs']))

def associate(before,after,c):
    evidence=[[pair_cost(a,b,c) for b in after] for a in before]
    costs=np.array([[e['cost'] for e in row] for row in evidence]).reshape(len(before),len(after))
    ordered=partial_assignments(costs,c['unmatched_cost_per_endpoint'])
    best=ordered[0];gap=ordered[1]['cost']-best['cost'] if len(ordered)>1 else None
    acceptable=bool(best['pairs'] and gap is not None and gap>=c['joint_assignment_min_gap'] and
        all(evidence[i][j]['appearance_similarity']>=c['joint_assignment_similarity_floor'] for i,j in best['pairs']))
    pair_certainty=[]
    for i,j in best['pairs']:
        alternatives=[p for p in ordered if [i,j] not in p['pairs']]
        exclusion=alternatives[0]['cost']-best['cost'] if alternatives else None
        pair_certainty.append({'pair':[i,j],'global_exclusion_gap':exclusion,
            'confirmed':bool(exclusion is not None and exclusion>=c['joint_assignment_min_gap'] and evidence[i][j]['appearance_similarity']>=c['joint_assignment_similarity_floor'])})
    return {'pair_evidence':evidence,'cost_matrix':costs.tolist(),'best':best,'second_best':ordered[1] if len(ordered)>1 else None,
        'global_gap':float(gap) if gap is not None else None,'identity_status':'confirmed' if acceptable else 'unresolved',
        'pair_certainty':pair_certainty,
        'complete_permutations':[p for p in ordered if not p['unmatched_before'] and not p['unmatched_after']],
        'assignment_hypothesis_count':len(ordered),'candidate_matchings':ordered[:8]}

def joint_assignment(costs,unmatched):
    """Exact best partial matching and second-best physical matching, ignoring dummy permutations.

    Removing each chosen real edge covers alternatives which delete an edge.
    Forcing an edge between unmatched endpoints covers strict supersets of the
    selected edge set. Each edge confidence is a globally reoptimized exclusion gap.
    """
    costs=np.asarray(costs,float);n,m=costs.shape;limit=1e6
    def solve(forbid=None,force=None):
        if n+m==0:return {'cost':0.,'pairs':[],'unmatched_before':[],'unmatched_after':[]}
        a=np.full((n+m,n+m),limit);a[:n,:m]=np.where(np.isfinite(costs),costs,limit)
        for i in range(n):a[i,m+i]=unmatched
        for j in range(m):a[n+j,j]=unmatched
        a[n:,m:]=0.
        if forbid is not None:a[forbid[0],forbid[1]]=limit
        if force is not None:
            i,j=force;value=a[i,j];a[i,:]=limit;a[:,j]=limit;a[i,j]=value
        rr,cc=linear_sum_assignment(a)
        if np.any(a[rr,cc]>=limit):return None
        pairs=[[int(i),int(j)] for i,j in zip(rr,cc) if i<n and j<m]
        used_i={i for i,j in pairs};used_j={j for i,j in pairs}
        ub=[i for i in range(n) if i not in used_i];ua=[j for j in range(m) if j not in used_j]
        return {'cost':float(sum(costs[i,j] for i,j in pairs)+unmatched*(len(ub)+len(ua))),
            'pairs':pairs,'unmatched_before':ub,'unmatched_after':ua}
    best=solve();alts=[];certainty=[]
    for pair in best['pairs']:
        alt=solve(forbid=pair)
        if alt is not None:alts.append(alt)
        certainty.append({'pair':pair,'global_exclusion_gap':float(alt['cost']-best['cost']) if alt else None})
    for i in best['unmatched_before']:
        for j in best['unmatched_after']:
            if np.isfinite(costs[i,j]):
                alt=solve(force=(i,j))
                if alt is not None:alts.append(alt)
    alts.sort(key=lambda x:(x['cost'],x['pairs']))
    return {'best':best,'second_best':alts[0] if alts else None,
        'global_gap':float(alts[0]['cost']-best['cost']) if alts else None,'pair_certainty':certainty}
