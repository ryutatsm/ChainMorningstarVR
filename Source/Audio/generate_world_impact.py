"""Deterministic original heavy iron strike. No recorded/licensed input audio.

Independent of audit6's three WAV generators: never replace their bytes.
"""
import argparse, hashlib, io, json, wave
from pathlib import Path
import numpy as np

def synthesize():
    rate=44100; t=np.arange(int(rate*.90),dtype=np.float64)/rate
    rng=np.random.default_rng(0xC05A7)
    # Dense low body plus short, inharmonic forged-iron ring and contact crack.
    body=(np.sin(2*np.pi*(76*t+1.8*(1-np.exp(-t*22))))*.72+
          np.sin(2*np.pi*119*t+.25)*.38)*np.exp(-t*12)
    ring=sum(a*np.sin(2*np.pi*f*t+p)*np.exp(-t*d)
             for f,a,p,d in ((237,.27,.1,7),(391,.18,.6,9),(647,.12,.8,12),
                             (1039,.07,.2,17),(1717,.04,.5,26)))
    noise=rng.standard_normal(len(t))
    crack=noise*.35*np.exp(-t*155)
    grit=np.convolve(noise,np.ones(7)/7,mode='same')*.19*np.exp(-t*30)
    y=body+ring+crack+grit; y-=y.mean()
    y*=(1-np.exp(-t*1500))*np.clip((.9-t)/.08,0,1)
    y*=.89/np.max(np.abs(y))
    pcm=np.round(y*32767).astype('<i2')
    buf=io.BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
    data=buf.getvalue(); report=validate(data)
    report.update(source='original deterministic synthesis; no external audio',seed='0xC05A7')
    return data,report

def validate(data):
    with wave.open(io.BytesIO(data),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,44100)
        y=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
    peak=float(np.max(abs(y)));rms=float(np.sqrt(np.mean(y*y)))
    assert .85<peak<.95 and .04<rms<.35 and abs(float(y.mean()))<.001
    assert np.max(abs(y[-2205:]))<.006 and y[0]==0
    power=abs(np.fft.rfft(y))**2;freq=np.fft.rfftfreq(len(y),1/44100)
    low=float(power[freq<700].sum()/power.sum()); assert low>.80
    return dict(sha256=hashlib.sha256(data).hexdigest(),seconds=len(y)/44100,
                pcm='mono 16-bit 44100Hz',peak=peak,rms=rms,power_below_700hz=low,
                clipping=False,quiet_tail=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    data,report=synthesize();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(data)
    a.out.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
