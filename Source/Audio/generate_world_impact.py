"""Export the user-selected original sample 01 at the user-approved previous playback level.

The authored PCM is pinned byte-for-byte. Apply a linear 0.85 gain only; never
normalize it back up. Audit6 scrape/swing/disarm WAVs and runtime code are untouched.
"""
import argparse, hashlib, io, json, wave
from pathlib import Path
import numpy as np

RATE = 44100
SOURCE = Path(__file__).resolve().parent / 'Selected/iron_impact_sample1.wav'
SOURCE_SHA256 = '60db444271b0c2c204b4a175451236ac618b37dc02830fecfbcc448f0a6cb2fa'
GAIN = .85
REFERENCE_SOURCE = Path(__file__).resolve().parent / 'Selected/iron_impact_sample5.wav'
REFERENCE_SOURCE_SHA256 = '49b4c050514c43861ebdf8e1ddae76748b1076e993694b552559f724473491f5'
REFERENCE_OUTPUT_SHA256 = '48fc4e54b6a4f5dd3a9de3c0f286a15350b5cdc471a8c9325cfba2ef95b8e455'

def weighted_attack_rms(pcm):
    # Same comparison metric used when authoring the audition samples. This is
    # approximate loudness matching, not proof of perceived VR volume equality.
    segment = pcm[:round(.30 * RATE)].astype(np.float64) / 32768
    freq = np.fft.rfftfreq(len(segment), 1 / RATE)
    weight = np.interp(freq, [0,50,90,160,300,700,1600,3500,7500,22050],
                       [0,.12,.32,.64,.87,1,1,.90,.50,.12])
    y = np.fft.irfft(np.fft.rfft(segment) * weight, len(segment))
    return float(np.sqrt(np.mean(y*y)))

def read_pcm(data):
    with wave.open(io.BytesIO(data), 'rb') as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) == (1, 2, RATE, 'NONE')
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    return pcm

def synthesize():
    source = SOURCE.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA256, 'Selected sound source was modified'
    original = read_pcm(source)
    assert len(original) == round(RATE * .72)
    pcm = np.rint(original.astype(np.float64) * GAIN).astype('<i2')
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())
    data = buf.getvalue()
    report = validate(data)
    reference = REFERENCE_SOURCE.read_bytes()
    assert hashlib.sha256(reference).hexdigest() == REFERENCE_SOURCE_SHA256
    reference_pcm = np.rint(read_pcm(reference).astype(np.float64) * GAIN).astype('<i2')
    level = weighted_attack_rms(pcm); reference_level = weighted_attack_rms(reference_pcm)
    level_delta_db = float(20*np.log10(level/reference_level))
    assert abs(level_delta_db) < .05, 'Volume differs from the user-approved sound5 level'
    report.update(volume_matching_reference_output_sha256=REFERENCE_OUTPUT_SHA256,
                  volume_matching_metric='0-300ms band-weighted RMS, approximate; not LUFS',
                  weighted_attack_rms=level, previous_sound5_weighted_attack_rms=reference_level,
                  level_delta_db_from_sound5=level_delta_db,
                  previous_sound5_volume_accepted_user_report=True)
    report.update(source='original authored PCM synthesis; user selected sample 01; no external audio',
                  sample_number=1, source_sample_sha256=SOURCE_SHA256,
                  source_sample_seed='0xc05a900', gain=GAIN, gain_db=float(20 * np.log10(GAIN)),
                  processing='linear sample attenuation only; no normalization or timbre processing')
    return data, report

def validate(data):
    pcm = read_pcm(data)
    y = pcm.astype(np.float64) / 32768
    peak = float(np.max(abs(y))); rms = float(np.sqrt(np.mean(y * y)))
    assert len(y) == round(RATE * .72)
    assert .61 < peak < .67 and .070 < rms < .082 and abs(float(y.mean())) < .002
    assert np.max(abs(y[-2205:])) < .006 and y[0] == y[-1] == 0
    power = abs(np.fft.rfft(y)) ** 2; freq = np.fft.rfftfreq(len(y), 1 / RATE)
    low = float(power[freq < 700].sum() / power.sum())
    sub140 = float(power[freq < 140].sum() / power.sum())
    metal = float(power[(freq >= 700) & (freq < 3500)].sum() / power.sum())
    assert low > .97 and sub140 < .35 and metal < .025, (low, sub140, metal, rms)
    return dict(sha256=hashlib.sha256(data).hexdigest(), seconds=len(y) / RATE,
                pcm='mono 16-bit 44100Hz', peak=peak, rms=rms,
                power_below_700hz=low, power_below_140hz=sub140,
                power_700_to_3500hz=metal, clipping=False, quiet_tail=True)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); a = p.parse_args()
    data, report = synthesize(); a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_bytes(data)
    a.out.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
