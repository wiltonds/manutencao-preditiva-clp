# Predictive Maintenance at the Edge — OPC UA + ML

> Applied industrial AI project for anomaly detection and predictive maintenance, connecting PLC/Soft-PLC signals to edge analytics through a vendor-neutral OPC UA layer.

**Portfolio focus:** Predictive Analytics · Industrial AI · Anomaly Detection · Edge Computing · OPC UA · Signal Processing · Decision Support

![Architecture](./docs/architecture.svg)

## Business Problem

Industrial maintenance teams need to detect abnormal equipment behavior early enough to plan intervention without turning a predictive model into a safety-critical control loop.

This project explores that boundary: **machine-learning analytics at the edge, integrated with industrial control infrastructure, while deterministic PLC logic remains responsible for critical interlocks.**

## Solution

The gateway reads industrial signals through OPC UA, applies the predictive model locally, and writes an advisory alert back to the control environment.

The design separates:

- **industrial communication** — OPC UA and vendor-specific integration;
- **analytics** — anomaly detection and vibration features;
- **decision support** — alert generation and maintenance signaling;
- **safety control** — deterministic logic remains in the PLC.

## Architecture

`PLC / Soft-PLC → OPC UA → Edge Analytics → Risk / Alert → Decision Support`

The same gateway logic can work with different PLC environments by changing the configuration profile rather than the predictive-model code.

### Two analytical tracks

**1. Multivariate anomaly detection**

The gateway uses **Isolation Forest** to identify abnormal operating conditions from industrial signals.

**2. Vibration analytics**

The vibration track processes waveform data and extracts:

- RMS;
- crest factor;
- kurtosis;
- frequency-band energy;
- 1× rotational frequency;
- BPFO and 2× BPFO components.

The objective is to demonstrate why spectral features can reveal bearing-related anomalies before a simple aggregate vibration metric becomes strongly abnormal.

## Industrial Integration

Supported development paths include:

| Environment | Role |
|---|---|
| Soft-PLC simulator | Fast, reproducible development and testing |
| OpenPLC | Open-source PLC integration through Modbus/OPC UA |
| Siemens S7-1500 / PLCSIM Advanced | Industrial vendor integration through native OPC UA |

The Siemens path is configuration-driven and depends on licensed Siemens/TIA tooling.

## Safety & Governance

The model is **advisory**, not a replacement for industrial control.

> **AI raises the signal; the PLC remains responsible for deterministic critical interlocks.**

In a production deployment, thresholds, writeback permissions, fail-safe behavior, network isolation, model validation and change management would require formal OT engineering and safety review.

## Repository Structure

```text
gateway.py          # OPC UA gateway + anomaly model + writeback
config.yaml         # environment profiles
plc_sim.py          # OPC UA simulator
openplc_shim.py     # Modbus ↔ OPC UA bridge
plc_sim_vib.py      # vibration waveform simulator
gateway_fft.py      # FFT + vibration feature extraction
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

### Simulator

Terminal 1:

```bash
python plc_sim.py
```

Terminal 2:

```bash
python gateway.py sim
```

### Vibration / FFT track

Terminal 1:

```bash
python plc_sim_vib.py
```

Terminal 2:

```bash
python gateway_fft.py
```

## What This Project Demonstrates

- Integration of ML with industrial communication protocols.
- Vendor-neutral architecture through OPC UA.
- Edge inference rather than dependence on a central application.
- Time-domain and frequency-domain signal analysis.
- Separation between predictive analytics and safety-critical control.
- A path from simulation to industrial integration.

## Limitations

This repository is a portfolio and engineering prototype. Simulated signals and development environments do not represent a production-certified predictive-maintenance system.

Before industrial deployment, the model would require representative historical data, validated failure labels, calibration, drift monitoring, false-positive/false-negative analysis, cybersecurity controls and field validation.

## Portfolio Perspective

This project demonstrates a broader principle in applied AI:

**Data → Signal Processing → Model → Operational Context → Decision Support**

The value of industrial ML is not only the model itself. It is the ability to place analytics inside a reliable operational architecture without compromising deterministic control.