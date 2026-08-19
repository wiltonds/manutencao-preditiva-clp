"""
gateway_fft.py - Gateway de borda com analise espectral (FFT).
Le a forma de onda via OPC UA, extrai features de tempo e frequencia,
treina Isolation Forest no saudavel e detecta o defeito de rolamento.
"""
import asyncio
import numpy as np
from asyncua import Client
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

URL = "opc.tcp://localhost:4841/sme/vib"
NS = "http://sme.industrial.demo"
BASELINE_N = 20
PERSIST = 5
FR = 30.0
BPFO = 107.6


def band_energy(freqs, amp, f0, tol=3.0):
    mask = np.abs(freqs - f0) <= tol
    return float(amp[mask].sum())


def extract_features(x, fs):
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    rms = float(np.sqrt(np.mean(x ** 2)))
    peak = float(np.max(np.abs(x)))
    crest = peak / rms if rms > 0 else 0.0
    kurt = float(np.mean((x / (x.std() + 1e-9)) ** 4))
    win = np.hanning(len(x))
    spec = np.abs(np.fft.rfft(x * win)) / len(x)
    freqs = np.fft.rfftfreq(len(x), 1.0 / fs)
    e_1x = band_energy(freqs, spec, FR)
    e_bpfo = band_energy(freqs, spec, BPFO)
    e_bpfo2 = band_energy(freqs, spec, 2 * BPFO)
    feats = np.array([rms, crest, kurt, e_1x, e_bpfo, e_bpfo2])
    return feats, rms, e_bpfo


async def main():
    async with Client(url=URL) as client:
        ns = await client.get_namespace_index(NS)

        def node(tag):
            return client.get_node(f"ns={ns};s=Motor01.{tag}")

        wf = node("VibrationWaveform")
        fs = await node("SampleRate_Hz").read_value()
        alarm, maint, health = node("AlarmActive"), node("MaintenanceRequest"), node("HealthScore")

        print("[fft] aprendendo baseline saudavel...")
        base, rms0, bpfo0 = [], [], []
        while len(base) < BASELINE_N:
            f, rms, ebpfo = extract_features(await wf.read_value(), fs)
            base.append(f); rms0.append(rms); bpfo0.append(ebpfo)
            await asyncio.sleep(1)
        X = np.vstack(base)
        scaler = StandardScaler().fit(X)
        model = IsolationForest(contamination=0.01, random_state=42).fit(scaler.transform(X))
        rms_base, bpfo_base = float(np.mean(rms0)), float(np.mean(bpfo0))
        print(f"[fft] baseline: RMS~{rms_base:.3f}  energia_BPFO~{bpfo_base:.4f}. Monitorando...\n")

        streak, alarmed = 0, False
        while True:
            f, rms, ebpfo = extract_features(await wf.read_value(), fs)
            xs = scaler.transform(f.reshape(1, -1))
            score = model.decision_function(xs)[0]
            anom = model.predict(xs)[0] == -1
            hp = float(np.clip(50 + score * 250, 0, 100))
            await health.write_value(round(hp, 1))
            rms_up = 100.0 * (rms / rms_base - 1.0)
            bpfo_up = 100.0 * (ebpfo / (bpfo_base + 1e-9) - 1.0)
            streak = streak + 1 if anom else 0
            tail = f" (streak {streak})" if streak else ""
            print(f"[fft] RMS {rms_up:+6.1f}%   BPFO {bpfo_up:+8.1f}%   "
                  f"score={score:+.3f}  health={hp:5.1f}%  "
                  + ("ANOMALIA" if anom else "ok") + tail)
            if streak >= PERSIST and not alarmed:
                await alarm.write_value(True)
                await maint.write_value(True)
                alarmed = True
                print("\n>>> ALERTA: assinatura de BPFO -> defeito de pista externa")
                print(">>> AlarmActive=True | torre de luz / SCADA / chamado CMMS\n")
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGateway FFT encerrado.")
