"""
streamlit_app.py - Dashboard de manutencao preditiva na borda + CLP.

Demo visual do loop OT->IT->OT: um motor com defeito de rolamento em evolucao
tem sua vibracao amostrada, o gateway de borda faz FFT + Isolation Forest,
detecta a assinatura de BPFO e "escreve o alerta de volta no CLP" (torre de luz
/ SCADA / chamado CMMS). A camada de integracao real via OPC UA esta no
repositorio (gateway_fft.py, plc_sim_vib.py); aqui a simulacao roda embarcada
para que o link publico funcione sem infraestrutura.
"""
import time
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from dsp import FS, N, generate_block, extract_features

st.set_page_config(page_title="IA na Borda + CLP | Manutencao Preditiva",
                   page_icon="⚙️", layout="wide")


def init_state():
    ss = st.session_state
    ss.t = 0
    ss.rng = np.random.default_rng(0)
    ss.baseline = []
    ss.model = None
    ss.scaler = None
    ss.rms_base = None
    ss.bpfo_base = None
    ss.hist = {"t": [], "rms_up": [], "bpfo_up": [], "health": []}
    ss.streak = 0
    ss.alarmed = False
    ss.alarm_t = None
    ss.last_wave = np.zeros(N)
    ss.last_spec = None
    ss.last_freqs = None
    ss.health = 100.0
    ss.initialized = True


if "initialized" not in st.session_state:
    init_state()
if "playing" not in st.session_state:
    st.session_state.playing = True


def advance(fr, bpfo, degr_speed, contamination, persist, baseline_n):
    ss = st.session_state
    x, degr = generate_block(ss.t, fr, bpfo, ss.rng, degr_speed=degr_speed)
    feats, rms, eb, spec, freqs = extract_features(x, fr, bpfo)
    ss.last_wave, ss.last_spec, ss.last_freqs = x, spec, freqs

    if ss.model is None:
        ss.baseline.append((feats, rms, eb))
        if len(ss.baseline) >= baseline_n:
            X = np.vstack([b[0] for b in ss.baseline])
            ss.scaler = StandardScaler().fit(X)
            ss.model = IsolationForest(
                contamination=contamination, random_state=42).fit(ss.scaler.transform(X))
            ss.rms_base = float(np.mean([b[1] for b in ss.baseline]))
            ss.bpfo_base = float(np.mean([b[2] for b in ss.baseline]))
        ss.t += 1
        return

    xs = ss.scaler.transform(feats.reshape(1, -1))
    score = ss.model.decision_function(xs)[0]
    anom = ss.model.predict(xs)[0] == -1
    ss.health = float(np.clip(50 + score * 250, 0, 100))
    rms_up = 100.0 * (rms / ss.rms_base - 1.0)
    bpfo_up = 100.0 * (eb / (ss.bpfo_base + 1e-9) - 1.0)
    ss.streak = ss.streak + 1 if anom else 0
    if ss.streak >= persist and not ss.alarmed:
        ss.alarmed, ss.alarm_t = True, ss.t
    for k, v in (("t", ss.t), ("rms_up", rms_up), ("bpfo_up", bpfo_up), ("health", ss.health)):
        ss.hist[k].append(v)
    ss.t += 1


# ----------------------------- Sidebar -----------------------------
with st.sidebar:
    st.header("Controles")
    c1, c2 = st.columns(2)
    if c1.button("▶ Play" if not st.session_state.playing else "⏸ Pausar", use_container_width=True):
        st.session_state.playing = not st.session_state.playing
        st.rerun()
    if c2.button("↺ Reiniciar", use_container_width=True):
        init_state()
        st.rerun()

    st.divider()
    fr = st.number_input("Rotacao do eixo — FR (Hz)", 5.0, 120.0, 30.0, 1.0,
                         help="RPM / 60. Define a frequencia de rotacao.")
    bpfo = st.number_input("Freq. defeito pista externa — BPFO (Hz)", 20.0, 400.0, 107.6, 0.5,
                           help="Vem da geometria do rolamento x rotacao. No ativo real, calcule-a.")
    degr_speed = st.slider("Velocidade de degradacao", 0.2, 3.0, 1.0, 0.1)
    st.divider()
    st.caption("Modelo (aplicados ao reiniciar)")
    contamination = st.slider("Sensibilidade (contamination)", 0.005, 0.10, 0.01, 0.005)
    persist = st.slider("Ciclos ate alarmar (PERSIST)", 1, 15, 5, 1)
    baseline_n = st.slider("Amostras de baseline", 10, 40, 20, 1)
    st.divider()
    refresh = st.slider("Intervalo de atualizacao (s)", 0.3, 2.0, 0.7, 0.1)
    st.caption("Alterou FR, BPFO ou parametros do modelo? Clique **Reiniciar**.")


# ----------------------------- Avanca 1 frame -----------------------------
if st.session_state.playing:
    advance(fr, bpfo, degr_speed, contamination, persist, baseline_n)

ss = st.session_state

# ----------------------------- Cabecalho -----------------------------
st.title("⚙️ IA na Borda conectada ao CLP — Manutencao Preditiva")
st.markdown(
    "Fluxo **OT → TI → OT**: o CLP amostra a vibracao → o gateway de borda faz "
    "**FFT + Isolation Forest** → ao detectar a assinatura de **BPFO**, escreve o "
    "alerta **de volta no CLP** (torre de luz / SCADA / chamado CMMS)."
)

# ----------------------------- Status / KPIs -----------------------------
if ss.model is None:
    st.info(f"🧠 Aprendendo o comportamento saudavel do equipamento… "
            f"{len(ss.baseline)}/{baseline_n} amostras")
elif ss.alarmed:
    st.error(f"🔴 **ALARME** — assinatura de BPFO detectada (bloco {ss.alarm_t}). "
             f"AlarmActive=True escrito no CLP · chamado CMMS aberto: "
             f"'Motor01 — defeito de pista externa'.")
else:
    st.success("🟢 Operacao normal — modelo monitorando.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Health Score", f"{ss.health:0.0f}%")
last_rms = ss.hist["rms_up"][-1] if ss.hist["rms_up"] else 0.0
last_bpfo = ss.hist["bpfo_up"][-1] if ss.hist["bpfo_up"] else 0.0
k2.metric("RMS vs baseline", f"{last_rms:+.0f}%")
k3.metric("Energia BPFO vs baseline", f"{last_bpfo:+.0f}%",
          help="Sobe muito antes do RMS — por isso a FFT antecipa o defeito.")
k4.metric("Status", "ALARME" if ss.alarmed else ("Aprendendo" if ss.model is None else "Normal"))

st.divider()

# ----------------------------- Graficos -----------------------------
left, right = st.columns(2)

with left:
    st.subheader("Tendencia: BPFO antecipa o RMS")
    if ss.hist["t"]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ss.hist["t"], y=ss.hist["bpfo_up"],
                                 name="Energia BPFO (%)", line=dict(color="#e45756", width=3)))
        fig.add_trace(go.Scatter(x=ss.hist["t"], y=ss.hist["rms_up"],
                                 name="RMS total (%)", line=dict(color="#4c78a8", width=2)))
        if ss.alarm_t is not None:
            fig.add_vline(x=ss.alarm_t, line_dash="dot", line_color="#e45756",
                          annotation_text="alarme")
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                          xaxis_title="bloco", yaxis_title="% vs baseline",
                          legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Coletando baseline…")

    st.subheader("Health Score")
    if ss.hist["t"]:
        figh = go.Figure(go.Scatter(x=ss.hist["t"], y=ss.hist["health"],
                                    fill="tozeroy", line=dict(color="#54a24b")))
        figh.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis_title="bloco", yaxis_title="saude (%)",
                           yaxis_range=[0, 100])
        st.plotly_chart(figh, use_container_width=True)

with right:
    st.subheader("Espectro (FFT) da vibracao")
    if ss.last_spec is not None:
        figs = go.Figure(go.Scatter(x=ss.last_freqs, y=ss.last_spec,
                                    line=dict(color="#333"), name="espectro"))
        for f0, lbl, col in ((fr, "1x", "#4c78a8"), (bpfo, "BPFO", "#e45756"),
                             (2 * bpfo, "2xBPFO", "#f58518")):
            figs.add_vline(x=f0, line_dash="dot", line_color=col,
                           annotation_text=lbl, annotation_position="top")
        figs.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                           xaxis_title="frequencia (Hz)", yaxis_title="amplitude",
                           xaxis_range=[0, min(3 * bpfo + 60, FS / 2)])
        st.plotly_chart(figs, use_container_width=True)

    st.subheader("Forma de onda no tempo")
    tw = np.arange(min(512, N)) / FS * 1000.0
    figw = go.Figure(go.Scatter(x=tw, y=ss.last_wave[:512], line=dict(color="#72b7b2")))
    figw.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10),
                       xaxis_title="tempo (ms)", yaxis_title="aceleracao (u.a.)")
    st.plotly_chart(figw, use_container_width=True)

# ----------------------------- Rodape -----------------------------
with st.expander("O que este demo prova (e o que e simulado)"):
    st.markdown(
        "- **Prova:** a arquitetura e o pipeline completos — transporte do sinal, "
        "FFT, extracao de features (RMS, crest factor, kurtose, bandas 1x/BPFO/2xBPFO), "
        "deteccao nao-supervisionada e o **loop fechado** que escreve o alerta de volta.\n"
        "- **Integracao real com CLP:** no repositorio, `gateway_fft.py` le a forma de "
        "onda via **OPC UA** de um soft-PLC (`plc_sim_vib.py`); `gateway.py` + `config.yaml` "
        "conectam a **Siemens (OPC UA nativo)** ou **OpenPLC (via shim Modbus→OPC UA)** "
        "trocando so o perfil. Aqui a simulacao roda embarcada para o link publico funcionar "
        "sem infraestrutura.\n"
        "- **Simulado:** o sinal de vibracao e sintetico, com a BPFO controlada. Num ativo "
        "real, a BPFO vem da geometria do rolamento x rotacao, e o baseline e treinado com "
        "dados saudaveis do proprio equipamento."
    )

# ----------------------------- Auto-avanco -----------------------------
if st.session_state.playing:
    time.sleep(refresh)
    st.rerun()