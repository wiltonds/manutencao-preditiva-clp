"""
plc_sim_vib.py - Soft-PLC OPC UA que publica a FORMA DE ONDA da vibracao.

Diferente do plc_sim.py (que dava so um numero de vibracao), aqui o CLP expoe
um bloco de amostras de alta frequencia num no de array OPC UA -- e o gateway
faz a FFT. Simula um defeito de pista externa (BPFO) que cresce ao longo do
tempo: a energia na banda da BPFO sobe MUITO antes do RMS total.

Endpoint proprio (4841) para nao colidir com o plc_sim.py.
Rode:  python plc_sim_vib.py    depois:  python gateway_fft.py
"""
import asyncio
import numpy as np
from asyncua import Server, ua

FS = 2000       # taxa de amostragem (Hz)
N = 1024        # amostras por bloco publicado (df = FS/N ~ 1.95 Hz)
FR = 30.0       # frequencia de rotacao do eixo (Hz) ~ 1800 rpm
BPFO = 107.6    # frequencia de defeito da pista externa (Hz)


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://localhost:4841/sme/vib")
    server.set_server_name("SME Virtual PLC - Vibracao Motor01")

    idx = await server.register_namespace("http://sme.industrial.demo")
    motor = await server.nodes.objects.add_object(idx, "Motor01")

    def nid(name):
        return ua.NodeId(f"Motor01.{name}", idx)

    wf = await motor.add_variable(
        nid("VibrationWaveform"), "VibrationWaveform",
        ua.Variant([0.0] * N, ua.VariantType.Double))
    fs_node = await motor.add_variable(nid("SampleRate_Hz"), "SampleRate_Hz", float(FS))
    temp = await motor.add_variable(nid("BearingTemp_C"), "BearingTemp_C", 45.0)

    alarm = await motor.add_variable(nid("AlarmActive"), "AlarmActive", False)
    maint = await motor.add_variable(nid("MaintenanceRequest"), "MaintenanceRequest", False)
    health = await motor.add_variable(nid("HealthScore"), "HealthScore", 100.0)
    for node in (alarm, maint, health):
        await node.set_writable()

    print(f"PLC vibracao no ar: opc.tcp://localhost:4841/sme/vib  (ns={idx})")
    print(f"Fs={FS}Hz  N={N}  fr={FR}Hz  BPFO={BPFO}Hz  |  degrada apos ~30 blocos\n")

    rng = np.random.default_rng(0)
    t = np.arange(N) / FS
    t_block = 0
    async with server:
        while True:
            degr = max(0, t_block - 30) / 60.0

            # Componente saudavel: 1x e 2x rotacao + ruido de fundo
            x = (0.60 * np.sin(2 * np.pi * FR * t)
                 + 0.30 * np.sin(2 * np.pi * 2 * FR * t)
                 + 0.15 * rng.standard_normal(N))

            # Defeito de pista externa: tom em BPFO + bandas laterais (fr) + impactos
            if degr > 0:
                a = 0.80 * degr
                x += a * np.sin(2 * np.pi * BPFO * t)
                x += 0.40 * a * np.sin(2 * np.pi * (BPFO + FR) * t)
                x += 0.40 * a * np.sin(2 * np.pi * (BPFO - FR) * t)
                # trem de impactos na taxa da BPFO -> eleva crest factor / kurtose
                step = FS / BPFO
                impacts = np.arange(0, N, step).astype(int)
                x[impacts[impacts < N]] += 2.5 * a

            temp_val = 45.0 + degr * 25.0 + rng.normal(0, 0.8)

            await wf.write_value(ua.Variant(x.tolist(), ua.VariantType.Double))
            await temp.write_value(round(float(temp_val), 3))
            t_block += 1
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPLC vibracao encerrado.")