"""Synthesize original CMS audio; no game recordings or external samples.

Mono PCM16 44.1 kHz. Scrape is a periodic 2-second loop; swing is a 240 ms
low "boon" one-shot. The DLL retriggers it from actual angular motion.
Disarm is a separate metal transient played only
after Skyrim returns the dropped object. SNDR paths are relative to Data/sound.
"""
from pathlib import Path
import argparse
import hashlib
import json
import wave
import numpy as np

RATE = 44100
FILES = ('iron_scrape.wav', 'air_cut.wav', 'disarm_strike.wav')


def band_noise(rng, n, low, high):
    freq = np.fft.rfftfreq(n, 1 / RATE)
    spectrum = np.fft.rfft(rng.normal(size=n))
    gain = (1 - np.exp(-(freq / low) ** 4)) * np.exp(-(freq / high) ** 4)
    data = np.fft.irfft(spectrum * gain, n)
    return data / np.sqrt(np.mean(data * data))


def generate(out):
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0xC05A5)
    t = np.arange(RATE * 2, dtype=np.float64) / RATE
    # Rough contact grains excite several non-harmonic iron resonances.
    grains = np.maximum(band_noise(rng, len(t), 5, 32), -.65) + .8
    scrape = .22 * band_noise(rng, len(t), 65, 850) * grains
    for f, gain in [(83.5, .13), (137.5, .10), (241, .07), (389.5, .05), (677, .025)]:
        scrape += gain * np.sin(2*np.pi*f*t + rng.uniform(0, 2*np.pi)) * (.55 + .3*grains)
    scrape += .045 * band_noise(rng, len(t), 1100, 3600) * grains
    # Keep the audit5 scrape/strike RNG stream and bytes unchanged while replacing
    # only the old two-noise-block air loop with its own original one-shot.
    rng.normal(size=(2, len(t)))
    swing_rng = np.random.default_rng(0xB006)
    ts = np.arange(round(RATE*.24), dtype=np.float64)/RATE
    attack = np.sin(.5*np.pi*np.minimum(ts/.042, 1))**2
    tail = np.exp(-(np.maximum(ts-.042, 0)/.064)**1.5)
    envelope = attack*tail*np.minimum((.24-ts)/.025, 1)
    # Dense low-mid turbulence supplies the body, with a short descending
    # resonance and little high hiss. No sharp impact attack or metallic ring.
    body = .62*band_noise(swing_rng, len(ts), 85, 530)
    body += .20*band_noise(swing_rng, len(ts), 38, 145)
    body += .055*band_noise(swing_rng, len(ts), 700, 1700)*np.exp(-ts/.07)
    phase = 2*np.pi*(78*ts+110*.065*(1-np.exp(-ts/.065)))
    body += .20*np.sin(phase+.18*np.sin(2*np.pi*19*ts))
    air = body*envelope
    ti = np.arange(int(RATE * .85), dtype=np.float64) / RATE
    strike = .70 * np.sin(2*np.pi*(92*ti + 1.8*(1-np.exp(-ti/.025)))) * np.exp(-ti/.055)
    strike += .36 * band_noise(rng, len(ti), 140, 4700) * np.exp(-ti/.024)
    for f, gain, decay in [(211, .36, .19), (347, .24, .23), (593, .14, .17), (941, .08, .13)]:
        strike += gain * np.sin(2*np.pi*f*ti) * np.exp(-ti/decay)
    strike *= np.minimum(ti/.0015, 1) * np.minimum((.85-ti)/.06, 1)
    report = {}
    for name, samples in zip(FILES, [scrape, air, strike]):
        samples -= np.mean(samples)
        samples *= .88 / np.max(np.abs(samples))
        pcm = np.rint(samples * 32767).astype('<i2')
        path = out / name
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE)
            wav.writeframes(pcm.tobytes())
        report[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'frames': len(pcm), 'sample_rate': RATE, 'channels': 1, 'bits': 16,
            'seconds': len(pcm)/RATE, 'peak': float(np.max(np.abs(samples))),
            'rms': float(np.sqrt(np.mean(samples*samples))), 'loop': name == FILES[0]}
    (out/'audio_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    validate(out)


def validate(out):
    report = json.loads((out/'audio_validation.json').read_text())
    assert set(report) == set(FILES)
    for name, expected in report.items():
        path = out/name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']
        with wave.open(str(path), 'rb') as wav:
            assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) == (1, 2, RATE, 'NONE')
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2').astype(float)/32767
        assert len(samples) == expected['frames'] and np.all(np.isfinite(samples))
        assert .1 < np.max(np.abs(samples)) < .95 and .02 < np.sqrt(np.mean(samples*samples)) < .4
        assert abs(np.mean(samples)) < .0001
        if expected['loop']:
            # Boundary discontinuity must fit the ordinary adjacent waveform.
            assert abs(samples[0]-samples[-1]) < max(.02, 4*np.sqrt(np.mean(np.diff(samples)**2)))
        else:
            assert abs(samples[0]) < .005 and abs(samples[-1]) < .005
        if name == 'air_cut.wav':
            assert len(samples) == round(RATE*.24) and not expected['loop']
            power = np.abs(np.fft.rfft(samples))**2
            freq = np.fft.rfftfreq(len(samples), 1/RATE)
            assert power[freq<700].sum()/power.sum() > .9
            # The low sound has a soft attack and a quiet tail, not a click or
            # another continuous hiss. RMS alone does not prove subjective tone.
            rms = lambda data: np.sqrt(np.mean(data*data))
            body_rms = rms(samples[round(RATE*.03):round(RATE*.11)])
            assert rms(samples[:round(RATE*.005)]) < .08*body_rms
            assert rms(samples[-round(RATE*.025):]) < .08*body_rms
    print('AUDIO_ASSETS_PASS mono PCM16 44100Hz; 1 scrape loop, 240ms low swing and disarm one-shots; no clipping/DC/click boundary')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=Path('build/sound/fx/ChainMorningstarVR'))
    p.add_argument('--check', action='store_true')
    a = p.parse_args()
    validate(a.out) if a.check else generate(a.out)
