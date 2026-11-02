import wave,numpy as np,sherpa_onnx,json,sys
D="/tmp/claude-0/-home-claude/b7b836a8-070c-54c2-99a3-2a27892ac005/scratchpad/"
M=D+"asr/sherpa-onnx-whisper-small/"
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M+"small-encoder.onnx",decoder=M+"small-decoder.onnx",tokens=M+"small-tokens.txt",language="fa",task="transcribe",num_threads=4)
def rd(p):
    w=wave.open(p);sr=w.getframerate();return np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768,sr
def segs(x,sr,gap=0.45):
    h=sr//100;fr=x[:len(x)//h*h].reshape(-1,h);db=20*np.log10(np.sqrt((fr**2).mean(1))+1e-9)
    db=np.convolve(db,np.ones(3)/3,mode="same");noise=float(np.percentile(db,20));on=db>noise+18
    idx=np.where(on)[0];out=[];s=idx[0];p=idx[0]
    for i in idx[1:]:
        if i-p>gap*100: out.append((s,p+1));s=i
        p=i
    out.append((s,p+1));return [(a/100,b/100) for a,b in out if b-a>=12],noise
res={}
for n in sys.argv[1:]:
    x,sr=rd(D+"rec30/"+n+".wav");S,noise=segs(x,sr);print(n,"noise",round(noise,1),"segments",len(S),"peak",round(20*np.log10(np.abs(x).max()+1e-9),1),flush=True)
    out=[]
    for i,(a,b) in enumerate(S):
        y=x[int(max(0,a-0.2)*sr):int((b+0.2)*sr)];st=rec.create_stream();st.accept_waveform(sr,y);rec.decode_stream(st);t=st.result.text.strip()
        seg=x[int(a*sr):int(b*sr)];clip=int((np.abs(seg)>0.98).sum());pk=round(float(20*np.log10(np.abs(seg).max()+1e-9)),1)
        out.append(dict(i=i,a=a,b=b,text=t,clip=clip,peak=pk));print(n,i,a,b,round(b-a,2),t,"clip",clip,"peak",pk,flush=True)
    res[n]=out
json.dump(res,open(D+"rec30/takes.json","w"),ensure_ascii=False,indent=1)
