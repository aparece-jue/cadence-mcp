"""Exact simple-ring validation and strict segment containment, no fill-rule guesses."""
from .core import CadenceError

def turn(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def on_segment(p,a,b):return turn(a,b,p)==0 and all(min(a[i],b[i])<=p[i]<=max(a[i],b[i]) for i in (0,1))
def edges_meet(a,b,c,d):
    t1,t2,t3,t4=turn(a,b,c),turn(a,b,d),turn(c,d,a),turn(c,d,b)
    return ((t1>0 and t2<0 or t1<0 and t2>0) and (t3>0 and t4<0 or t3<0 and t4>0)) or any((t==0 and on_segment(p,x,y)) for t,p,x,y in ((t1,c,a,b),(t2,d,a,b),(t3,a,c,d),(t4,b,c,d)))

def simple_ring(points):
    ring=[]
    for p in points:
        if not ring or p!=ring[-1]:ring.append(p)
    if len(ring)>1 and ring[0]==ring[-1]:ring.pop()
    n=len(ring)
    if n<3 or len({tuple(p) for p in ring})!=n:return None
    if n*n>1000000:raise CadenceError('geometry_limit','Closed-outline simplicity exceeds pair budget.')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]+ring[:1]))
    if area==0:return None
    for i in range(n):
        a,b,c=ring[i-1],ring[i],ring[(i+1)%n]
        if turn(a,b,c)==0 and (on_segment(c,a,b) or on_segment(a,b,c)):return None
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if edges_meet(ring[i],ring[(i+1)%n],ring[j],ring[(j+1)%n]):return None
    return ring

def strictly_inside(p,ring):
    winding=0
    for a,b in zip(ring,ring[1:]+ring[:1]):
        if on_segment(p,a,b):return False
        if a[1]<=p[1]<b[1] and turn(a,b,p)>0:winding+=1
        elif b[1]<=p[1]<a[1] and turn(a,b,p)<0:winding-=1
    return winding!=0

def segment_inside(a,b,ring):
    if a==b or not strictly_inside(a,ring) or not strictly_inside(b,ring):return False
    # Endpoint tests alone would accept a segment crossing a concave notch.
    return not any(edges_meet(a,b,c,d) for c,d in zip(ring,ring[1:]+ring[:1]))
