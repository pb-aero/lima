import json,math,sys
import os; D=os.path.dirname(os.path.abspath(__file__))+'/'
cy=json.load(open(D+'cup_crtyd.json'))
for h in('H1','H2','H3'): cy[h]=[-2.45,-2.45,2.45,2.45]
CX,CY,RI,RO=150.0,100.0,19.0,34.0
LO,HI=RI+0.35,RO-0.35; GAP=0.2; CONN={'J2','J7','J8'}; HOLES={'H1','H2','H3'}
T0=float(sys.argv[1]) if len(sys.argv)>1 else -10.0
ORDER=[['H1'],['R7','U4','R8'],['R17','U5','R18'],['Q2','J2'],['C22','C20','C21','J7'],['L3','L4','C18','C19'],
 ['R9','R10','FL1','C16','C17'],['L1','L2','C14','C15','C12'],['FB1','FB2','C13','C36','C37'],['C38','U6','C39'],
 ['FB3','FB4','C27','L7','L8'],['C28','FL2','C29','R15','R16'],['C30','C31','C32','C33','C34'],['L5','L6','R13','R14'],
 ['Q1','R11','R12','C25','C26'],['D1','C23','C24','J8'],['H2'],['C35','C41','U7','L9'],['C40','C42','U8','C43'],
 ['U9','C45','C46','C6'],['C7','U3','C8','R3'],['R1','R2','MK3','C11'],['H3'],['C2','C3','C47','C48','C1'],
 ['U1','C10'],['C9','R4','R5','R6'],['U2','C4','C5','C44'],['MK2','MK1']]
def orient(r):
    b=cy[r]; w,h=b[2]-b[0],b[3]-b[1]
    if r in CONN: return 0,w,h            # local +y radial (opening outward), tangential=w
    if h>w: return 90,h,w                 # local x radial: tangential=h, radial=w
    return 0,w,h
P={}; theta=T0; report=[]
for slot in ORDER:
    parts=[(r,)+orient(r) for r in slot]; rs=[]
    if slot[0] in HOLES: rs=[(RI+RO)/2]
    else:
        conn=[p for p in parts if p[0] in CONN]; rest=[p for p in parts if p[0] not in CONN]
        acc=LO
        for p in rest: rs.append(acc+p[3]/2); acc+=p[3]+GAP
        top=acc-GAP
        if conn:
            rc=30.8; rs.append(rc)
            if rc-conn[0][3]/2 < top+GAP-0.01: print("STACK CLASH",slot)
            parts=rest+conn
        elif top>HI+0.01: print("TOO TALL",slot,round(top,2))
        else:   # centre the stack in the band
            sh=(HI-top)/2; rs=[x+sh for x in rs]
    need=max((p[2]+GAP)/max(rr-p[3]/2,1.0) for p,rr in zip(parts,rs))
    dth=math.degrees(need); tc=theta+dth/2
    for (r,ex,te,re),rr in zip(parts,rs):
        a=math.radians(tc); rot=((90-tc+ex)+180)%360-180
        P[r]=(round(CX+rr*math.cos(a),3),round(CY+rr*math.sin(a),3),round(rot,2))
    theta+=dth
used=theta-T0
print("total angle used: %.1f deg of 360"%used)
json.dump(P,open(D+'cup_placement.json','w'))
# ---- check: ring containment (exact corners) + pairwise overlap (separating axis)
def corners(r):
    x,y,rot=P[r]; b=cy[r]; a=math.radians(rot); c,s=math.cos(a),math.sin(a)
    return [(x+px*c+py*s, y-px*s+py*c) for px,py in ((b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3]))]
def ov(A,B):
    for poly in (A,B):
        for i in range(4):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%4]; nx,ny=y2-y1,x1-x2
            pa=[nx*p[0]+ny*p[1] for p in A]; pb=[nx*p[0]+ny*p[1] for p in B]
            if max(pa)<=min(pb)+1e-6 or max(pb)<=min(pa)+1e-6: return False
    return True
Q={r:corners(r) for r in P}; bad=0
for r,q in Q.items():
    d=[math.hypot(px-CX,py-CY) for px,py in q]
    if min(d)<RI+0.3 or max(d)>RO+(0.35 if r in CONN else -0.3): print("RING",r,round(min(d),2),round(max(d),2)); bad+=1
ks=sorted(Q)
for i,a in enumerate(ks):
    for b in ks[i+1:]:
        if ov(Q[a],Q[b]): print("OVERLAP",a,b); bad+=1
print("unplaced:",sorted(set(cy)-set(P)),"| problems:",bad)
