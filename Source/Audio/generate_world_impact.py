"""Deterministic original heavy iron strike. No recorded/licensed input audio.

Independent of audit6's three WAV generators: never replace their bytes.
"""
import argparse, hashlib, io, json, wave
from pathlib import Path
import numpy as np
from generate_audio import band_noise

def synthesize():
    rate=44100; t=np.arange(int(rate*.80),dtype=np.float64)/rate
    rng=np.random.default_rng(0xC05A8)
    # Keep a low heavy body, but place enough energy in the headset's audible
    # low-mid/metal bands. Audit7 had 77% of its power below 140 Hz.
    body=(np.sin(2*np.pi*(88*t+1.5*(1-np.exp(-t*28))))*.46+
          np.sin(2*np.pi*159*t+.25)*.48)*np.exp(-t*8)
    ring=sum(a*np.sin(2*np.pi*f*t+p)*np.exp(-t*d)
             for f,a,p,d in ((247,.55,.1,6),(409,.38,.6,7),(683,.24,.8,10),
                             (1123,.30,.2,12),(1751,.18,.5,16)))
    crack=band_noise(rng,len(t),180,4800)*.30*np.exp(-t*42)
    grit=band_noise(rng,len(t),150,2400)*.12*np.exp(-t*10)
    y=body+ring+crack+grit; y-=y.mean()
    y=np.tanh(1.25*y)
    y*=(1-np.exp(-t*1500))*np.clip((.8-t)/.18,0,1)
    y*=.89/np.max(np.abs(y))
    pcm=np.round(y*32767).astype('<i2')
    buf=io.BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm.tobytes())
    data=buf.getvalue(); report=validate(data)
    report.update(source='original deterministic synthesis; no external audio',seed='0xC05A8')
    return data,report

def validate(data):
    with wave.open(io.BytesIO(data),'rb') as w:
        assert (w.getnchannels(),w.getsampwidth(),w.getframerate())==(1,2,44100)
        y=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
    peak=float(np.max(abs(y)));rms=float(np.sqrt(np.mean(y*y)))
    assert .85<peak<.95 and .10<rms<.30 and abs(float(y.mean()))<.002
    assert np.max(abs(y[-2205:]))<.006 and y[0]==0
    power=abs(np.fft.rfft(y))**2;freq=np.fft.rfftfreq(len(y),1/44100)
    low=float(power[freq<700].sum()/power.sum())
    sub140=float(power[freq<140].sum()/power.sum())
    metal=float(power[(freq>=700)&(freq<3500)].sum()/power.sum())
    assert .45<low<.92 and sub140<.40 and metal>.06,(low,sub140,metal,rms)
    return dict(sha256=hashlib.sha256(data).hexdigest(),seconds=len(y)/44100,
                pcm='mono 16-bit 44100Hz',peak=peak,rms=rms,power_below_700hz=low,
                power_below_140hz=sub140,power_700_to_3500hz=metal,
                clipping=False,quiet_tail=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    data,report=synthesize();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_bytes(data)
    a.out.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
