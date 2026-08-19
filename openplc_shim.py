"""
openplc_shim.py - Da' uma "cara" OPC UA ao OpenPLC.

O OpenPLC fala Modbus TCP nativo, nao OPC UA. Este shim e' um cliente Modbus
que le os registradores do OpenPLC e os republica como nos OPC UA -- com os
MESMOS NodeIds do perfil 'openplc' no config.yaml. Assim o gateway universal
consome o OpenPLC exatamente como consumiria um Siemens.

Mapeamento assumido (ajuste aos located variables do seu programa OpenPLC):
    input register 0..3  = sensores (inteiro = valor * escala)
    holding register 0   = AlarmActive (0/1)  <- writeback do gateway

    Modbus (OpenPLC)                     OPC UA (para o gateway)
      IR0 = MotorCurrent_A * 100           ns=2;s=Motor01.MotorCurrent_A
      IR1 = Vibration_mmps * 100           ns=2;s=Motor01.Vibration_mmps
      IR2 = BearingTemp_C  * 10            ns=2;s=Motor01.BearingTemp_C
      IR3 = Pressure_bar   * 100           ns=2;s=Motor01.Pressure_bar

Rode:  python openplc_shim.py    (com o OpenPLC no ar em :502)
Depois: python gateway.py openplc
"""
import asyncio
from asyncua import Server, ua
from pymodbus.client import ModbusTcpClient

OPENPLC_HOST = "localhost"
OPENPLC_PORT = 502
SHIM_ENDPOINT = "opc.tcp://0.0.0.0:4842/openplc"

SENSORS = ["MotorCurrent_A", "Vibration_mmps", "BearingTemp_C", "Pressure_bar"]
SCALE = {"MotorCurrent_A": 100.0, "Vibration_mmps": 100.0,
         "BearingTemp_C": 10.0, "Pressure_bar": 100.0}


async def main():
    mb = ModbusTcpClient(OPENPLC_HOST, port=OPENPLC_PORT)
    if not mb.connect():
        print(f"[shim] AVISO: nao conectou ao OpenPLC em {OPENPLC_HOST}:{OPENPLC_PORT}. "
              "Suba o OpenPLC ou ajuste OPENPLC_HOST/PORT.")

    server = Server()
    await server.init()
    server.set_endpoint(SHIM_ENDPOINT)
    idx = await server.register_namespace("http://sme.industrial.demo")
    motor = await server.nodes.objects.add_object(idx, "Motor01")

    nodes = {}
    for n in SENSORS:
        nodes[n] = await motor.add_variable(ua.NodeId(f"Motor01.{n}", idx), n, 0.0)
    for n in ("AlarmActive", "MaintenanceRequest"):
        v = await motor.add_variable(ua.NodeId(f"Motor01.{n}", idx), n, False)
        await v.set_writable()
        nodes[n] = v
    hs = await motor.add_variable(ua.NodeId("Motor01.HealthScore", idx), "HealthScore", 100.0)
    await hs.set_writable()
    nodes["HealthScore"] = hs

    print(f"[shim] OPC UA no ar: {SHIM_ENDPOINT}  (ns={idx})  <-> Modbus OpenPLC")

    async with server:
        while True:
            # OpenPLC -> OPC UA
            rr = mb.read_input_registers(0, count=4)
            if not rr.isError():
                for i, n in enumerate(SENSORS):
                    await nodes[n].write_value(rr.registers[i] / SCALE[n])
            # OPC UA (writeback do gateway) -> OpenPLC
            try:
                alarm = await nodes["AlarmActive"].read_value()
                mb.write_register(0, 1 if alarm else 0)
            except Exception:
                pass
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShim encerrado.")