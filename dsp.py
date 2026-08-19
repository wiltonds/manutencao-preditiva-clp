"""
dsp.py - Geracao de sinal de vibracao + extracao de features espectrais.

Modulo compartilhado (sem dependencia de Streamlit nem de OPC UA) para que a
mesma logica de FFT/features usada no gateway de borda seja reaproveitada pelo
dashboard. Mantem uma unica fonte de verdade para a analise de sinal.
"""
import numpy as np

FS = 2000   # taxa de amostragem (Hz)
N = 1024    # amostras por bloco (df = FS/N ~ 1.95 Hz)


def generate_block(t_block, fr, bpfo, rng, degr_speed=1.0, warmup=20):
    """Gera um bloco de forma de onda com defeito de pista externa crescente."""
    degr = max(0.0, (t_block - warmup) * degr_speed / 60.0)
    degr = min(degr, 1.5)
    t = np.arange(N) / FS
    x = (0.60 * np.sin(2 * np.pi * fr * t)
         + 0.30 * np.sin(2 * np.pi * 2 * fr * t)
         + 0.15 * rng.standard_normal(N))
    if degr > 0:
        a = 0.80 * degr
        x += a * np.sin(2 * np.pi * bpfo * t)
        x += 0.40 * a * np.sin(2 * np.pi * (bpfo + fr) * t)
        x += 0.40 * a * np.sin(2 * np.pi * (bpfo - fr) * t)
        step = FS / bpfo
        imp = np.arange(0, N, step).astype(int)
        x[imp[imp < N]] += 2.5 * a
    return x, degr


def band_energy(freqs, amp, f0, tol=3.0):
    mask = np.abs(freqs - f0) <= tol
    return float(amp[mask].sum())


def extract_features(x, fr, bpfo):
    """Forma de onda -> (features, rms, energia_bpfo, espectro, freqs)."""
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))
    crest = peak / rms if rms > 0 else 0.0
    kurt = float(np.mean((x / (x.std() + 1e-9)) ** 4))
    win = np.hanning(len(x))
    spec = np.abs(np.fft.rfft(x * win)) / len(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / FS)
    e_1x = band_energy(freqs, spec, fr)
    e_bpfo = band_energy(freqs, spec, bpfo)
    e_bpfo2 = band_energy(freqs, spec, 2 * bpfo)
    feats = np.array([rms, crest, kurt, e_1x, e_bpfo, e_bpfo2])
    return feats, rms, e_bpfo, spec, freqs