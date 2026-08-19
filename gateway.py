"""
gateway.py - Gateway de borda UNIVERSAL (a "ponte").

Le tags via OPC UA, aprende o baseline saudavel, roda um modelo preditivo
(Isolation Forest) e escreve o alerta de volta no CLP. O codigo NAO sabe se
esta falando com um Siemens, um OpenPLC (via shim) ou o simulador -- isso vive
inteiramente no config.yaml. Trocar de vendor = trocar o perfil.

Uso:
    python gateway.py sim        # simulador local (plc_sim.py)
    python gateway.py openplc    # OpenPLC via openplc_shim.py
    python gateway.py siemens    # S7-1500 / PLCSIM Advanced (OPC UA nativo)
"""
import asyncio
import sys
import yaml
import numpy as np
from asyncua import Client
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASELINE_N = 20   # amostras saudaveis p/ treinar
PERSIST = 5       # ciclos anomalos seguidos antes de alarmar (anti-flapping)


def load_profile(name, path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if name not in cfg["profiles"]:
        raise SystemExit(f"Perfil '{name}' nao existe em {path}. "
                         f"Disponiveis: {list(cfg['profiles'])}")
    return cfg["profiles"][name]


def resolve(client, spec):
    """Resolve uma tag por NodeId (universal entre vendors)."""
    if "nodeid" in spec:
        return client.get_node(spec["nodeid"])
    raise ValueError(f"Tag sem 'nodeid' no config: {spec}")


async def main():
    profile_name = sys.argv[1] if len(sys.argv) > 1 else "sim"
    prof = load_profile(profile_name)
    feat_specs, wb_specs = prof["features"], prof.get("writeback", {})
    feat_names = list(feat_specs.keys())

    print(f"[gateway] perfil={profile_name}  endpoint={prof['endpoint']}")
    async with Client(url=prof["endpoint"]) as client:
        feats = {n: resolve(client, feat_specs[n]) for n in feat_names}
        wb = {n: resolve(client, wb_specs[n]) for n in wb_specs}

        async def read():
            return np.array([await feats[n].read_value() for n in feat_names], float)

        # 1) Aprende o "normal"
        print("[gateway] aprendendo baseline saudavel...")
        base = []
        while len(base) < BASELINE_N:
            base.append(await read())
            await asyncio.sleep(1)
        X = np.vstack(base)
        scaler = StandardScaler().fit(X)
        model = IsolationForest(contamination=0.02, random_state=42).fit(scaler.transform(X))
        print(f"[gateway] treinado com {BASELINE_N} amostras. Monitorando...\n")

        # 2) Scoring online + writeback
        streak, alarmed = 0, False
        while True:
            x = (await read()).reshape(1, -1)
            xs = scaler.transform(x)
            score = model.decision_function(xs)[0]
            anom = model.predict(xs)[0] == -1
            health = float(np.clip(50 + score * 250, 0, 100))
            if "HealthScore" in wb:
                await wb["HealthScore"].write_value(round(health, 1))

            streak = streak + 1 if anom else 0
            tail = f" (streak {streak})" if streak else ""
            print(f"[gateway] score={score:+.3f}  health={health:5.1f}%  "
                  + ("ANOMALIA" if anom else "ok") + tail)

            if streak >= PERSIST and not alarmed:
                if "AlarmActive" in wb:
                    await wb["AlarmActive"].write_value(True)
                if "MaintenanceRequest" in wb:
                    await wb["MaintenanceRequest"].write_value(True)
                alarmed = True
                print("\n>>> ALERTA escrito no CLP: AlarmActive=True")
                print(">>> Torre de luz / SCADA notificado / chamado CMMS aberto\n")

            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGateway encerrado.")