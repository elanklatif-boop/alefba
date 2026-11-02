from playwright.sync_api import sync_playwright
res=[]
def check(n, ok, x=""): res.append(bool(ok)); print("PASS" if ok else "FAIL", n, "" if ok else x)
def comps(pts, cell=4):
    S={(round(x/cell),round(y/cell)):(x,y) for x,y in pts}; seen=set(); out=[]
    for k in S:
        if k in seen: continue
        st=[k]; seen.add(k); c=[]
        while st:
            a=st.pop(); c.append(S[a])
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    j=(a[0]+dx,a[1]+dy)
                    if j in S and j not in seen: seen.add(j); st.append(j)
        out.append(c)
    return sorted(out,key=len,reverse=True)
def draw(pg, pts):
    pts=[q for q in pts if round(q[0])%4<2 and round(q[1])%4<2] or pts
    pts=sorted(pts,key=lambda p:(round(p[1]/6),p[0])); prev=None
    for x,y in pts:
        if prev is None or abs(prev[0]-x)>10 or abs(prev[1]-y)>10:
            if prev is not None: pg.mouse.up()
            pg.mouse.move(x,y); pg.mouse.down()
        else: pg.mouse.move(x,y)
        prev=(x,y)
    if prev: pg.mouse.up()
import numpy as np
from skimage.morphology import skeletonize
def centre(pts):
    """the middle line of a stroke, the way a child writes it with one line"""
    xs=[x for x,y in pts]; ys=[y for x,y in pts]; x0,y0=min(xs),min(ys)
    m=np.zeros((int((max(ys)-y0)/2)+3,int((max(xs)-x0)/2)+3),bool)
    for x,y in pts: m[int((y-y0)/2)+1,int((x-x0)/2)+1]=True
    sk=skeletonize(m); yy,xx=np.nonzero(sk)
    return [(x0+(x-1)*2,y0+(y-1)*2) for x,y in zip(xx,yy)]
def dot(pg,x,y):
    pg.mouse.move(x,y); pg.mouse.down(); pg.mouse.move(x+2,y+1); pg.mouse.up()
cen=lambda m:(sum(x for x,y in m)/len(m),sum(y for x,y in m)/len(m))
def taps(c, f=lambda x,y:(x,y)):
    for m in c[1:]:
        if len(m)<3: continue
        w=max(x for x,y in m)-min(x for x,y in m); cx,cy=cen(m)
        if w>40: [dot(pg,*f(*cen([q for q in m if (q[0]<cx)==side]))) for side in (True,False)]  # two dots drawn as one piece (ق)
        else: dot(pg,*f(cx,cy))
with sync_playwright() as p:
    b=p.chromium.launch();import os; pg=b.new_page(viewport={"width":390,"height":844},device_scale_factor=float(os.environ.get("DPR","1")));pg.goto("http://127.0.0.1:8811/");pg.wait_for_timeout(1500)
    pg.evaluate("document.fonts.load('600 40px Vazirmatn','ابتثجحخن')")
    pg.wait_for_timeout(500)
    def tracer(g, memory=False):
        pg.evaluate("""([g,m])=>{document.querySelectorAll('.dt').forEach(e=>e.remove());const d=document.createElement('div');d.className='dt';
          d.style.cssText='position:fixed;left:20px;top:20px;width:300px;height:300px;z-index:99999;background:#fff';document.body.append(d);
          const cv=document.createElement('canvas');cv.style.cssText='width:300px;height:300px;touch-action:none';d.append(cv);window.__t=makeTracer(cv,g,()=>{},{memory:m})}""",[g,memory])
        return pg.evaluate("window.__t.pieces()")
    score=lambda: pg.evaluate("window.__t.score()")
    ok=lambda s,mem=False: s["coverage"]>=(0.4 if mem else 0.5) and s["precision"]>=(0.5 if mem else 0.55) and not s["missing"] and not s["extra"]
    # 1. whole letter traced, dots too: right
    for g in "بتثجخن":
        c=tracer(g); draw(pg,[q for part in c for q in part]); s=score()
        check(f"{g} traced with its dots is right {s}", ok(s))
    # 2. dots left off: wrong
    for g in "بتثجخن":
        c=tracer(g); draw(pg,c[0]); s=score()
        check(f"{g} without its dots is wrong (shape alone would pass: {s['coverage']:.2f}/{s['precision']:.2f}, missing {s['missing']})", s["missing"]>0 and not ok(s))
    # 3. wrong dots
    c=tracer("ب"); body=c[0]; draw(pg,body); xs=[x for x,y in body]; ys=[y for x,y in body]; cx=(min(xs)+max(xs))/2; top=min(ys)
    dot(pg,cx-12,top-30); dot(pg,cx+12,top-30); s=score()
    check(f"ب with two dots on top (that's ت) is wrong {s}", not ok(s) and s["missing"] and s["extra"])
    c=tracer("ح"); body=c[0]; draw(pg,body); xs=[x for x,y in body]; ys=[y for x,y in body]
    dot(pg,(min(xs)+max(xs))/2+10,(min(ys)+max(ys))/2+15); s=score()
    check(f"ح with a dot in the middle (that's ج) is wrong {s}", not ok(s) and s["extra"])
    c=tracer("ح"); draw(pg,c[0]); s=score(); check(f"ح traced, no dots, is right {s}", ok(s))
    c=tracer("ت"); draw(pg,[q for part in c for q in part]); dts=[q for part in c[1:] for q in part]; xs=[x for x,y in dts]; ys=[y for x,y in dts]
    dot(pg,(min(xs)+max(xs))/2,min(ys)-22); s=score()
    check(f"ت with a third dot on top (that's ث) is wrong {s}", not ok(s) and s["extra"])
    c=tracer("خ"); draw(pg,c[0]); xs=[x for x,y in c[0]]; ys=[y for x,y in c[0]]
    dot(pg,(min(xs)+max(xs))/2+10,max(ys)+25); s=score()
    check(f"خ with its dot underneath instead of on top is wrong {s}", not ok(s))
    # 4. from memory: the whole letter, smaller and off to one side, is still right; without the dot it isn't
    c=tracer("ب",True); allp=[q for part in c for q in part]; mx=min(x for x,y in allp); my=min(y for x,y in allp)
    draw(pg,[(mx+(x-mx)*0.7+15,my+(y-my)*0.7+10) for x,y in centre(c[0])]); taps(c,lambda x,y:(mx+(x-mx)*0.7+15,my+(y-my)*0.7+10)); s=score(); check(f"ب from memory, smaller, with its dot is right {s}", ok(s,True))
    c=tracer("ب",True); draw(pg,[(mx+(x-mx)*0.7+15,my+(y-my)*0.7+10) for x,y in centre(c[0])]); s=score(); check(f"ب from memory without its dot is wrong {s}", not ok(s,True))
    # 5. dots written as single taps, the way a child writes them
    for g in "بپتثجچشقن":
        c=tracer(g); draw(pg,c[0]); taps(c); s=score()
        check(f"{g} traced, dots tapped once each, is right {s}", ok(s))
    for g in "بتثشقنج":
        c=tracer(g,True); allp=[q for part in c for q in part]; mx=min(x for x,y in allp); my=min(y for x,y in allp); f=lambda x,y:(mx+(x-mx)*0.9+12,my+(y-my)*0.9+8)
        draw(pg,[f(x,y) for x,y in centre(c[0])]); taps(c,f); s=score()
        check(f"{g} from memory, dots tapped, is right {s}", ok(s,True))
    for g,flip in (("ب","on top"),("ث","underneath"),("ن","underneath")):
        c=tracer(g,True); allp=[q for part in c for q in part]; mx=min(x for x,y in allp); my=min(y for x,y in allp); f=lambda x,y:(mx+(x-mx)*0.9+12,my+(y-my)*0.9+8)
        draw(pg,[f(x,y) for x,y in centre(c[0])]); ys=[y for x,y in c[0]]; xs=[x for x,y in c[0]]
        y=(min(ys)-30) if flip=="on top" else (max(ys)+30)
        [dot(pg,*f((min(xs)+max(xs))/2+dx,y)) for dx in ((0,) if g!="ث" else (-14,14,0))]; s=score()
        check(f"{g} from memory with its dots {flip} (wrong side) is wrong {s}", not ok(s,True))
    c=tracer("ح",True); allp=[q for part in c for q in part]; mx=min(x for x,y in allp); my=min(y for x,y in allp); f=lambda x,y:(mx+(x-mx)*0.9+12,my+(y-my)*0.9+8)
    draw(pg,[f(x,y) for x,y in centre(c[0])]); xs=[x for x,y in c[0]]; ys=[y for x,y in c[0]]; dot(pg,*f((min(xs)+max(xs))/2,min(ys)-30)); s=score()
    check(f"ح from memory with a dot on top (that's خ) is wrong {s}", not ok(s,True))
    c=tracer("ح",True); draw(pg,[f(x,y) for x,y in centre(c[0])]); s=score(); check(f"ح from memory, no dots, is right {s}", ok(s,True))
    b.close()
print(f"{sum(res)}/{len(res)} passed")
