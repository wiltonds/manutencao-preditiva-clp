"""
plc_sim.py - Fonte OPC UA (soft-PLC) com NodeIds string deterministicos.

Serve dois propositos:
  1) Testbed autonomo (perfil 'sim' no config.yaml).
  2) Emular um endpoint OPC UA no estilo Siemens S7-1500 enquanto voce nao
     tem PLCSIM/TIA a mao -- o gateway le por NodeId, exatamente como faria
     num S7 real.

Fase saudavel (~30s) -> degradacao progressiva -> falha.
Rode este arquivo, depois:  python gateway.py sim
"""
import asyncio
import random
from asyncua import Server, ua


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://localhost:4840/sme/plc")
    server.set_server_name("SME Virtual PLC - Motor01")

    idx = await server.register_namespace("http://sme.industrial.demo")
    motor = await server.nodes.objects.add_object(idx, "Motor01")

    def nid(name):
        return ua.NodeId(f"Motor01.{name}", idx)

    # Tags de processo (NodeIds -> ns=2;s=Motor01.<nome>)
    current = await motor.add_variable(nid("MotorCurrent_A"), "MotorCurrent_A", 12.0)
    vibration = await motor.add_variable(nid("Vibration_mmps"), "Vibration_mmps", 1.2)
    temp = await motor.add_variable(nid("BearingTemp_C"), "BearingTemp_C", 45.0)
    pressure = await motor.add_variable(nid("Pressure_bar"), "Pressure_bar", 6.0)

    # Tags de retorno (o gateway escreve de volta)
    alarm = await motor.add_variable(nid("AlarmActive"), "AlarmActive", False)
    maint = await motor.add_variable(nid("MaintenanceRequest"), "MaintenanceRequest", False)
    health = await motor.add_variable(nid("HealthScore"), "HealthScore", 100.0)
    for node in (alarm, maint, health):
        await node.set_writable()

    print(f"PLC virtual (OPC UA) no ar: opc.tcp://localhost:4840/sme/plc  (ns={idx})")
    print("NodeIds: ns=2;s=Motor01.<tag>   |  degrada apos ~30s\n")

    t = 0
    async with server:
        while True:
            degr = max(0, t - 30) / 60.0
            await current.write_value(round(12.0 + degr * 6.0 + random.gauss(0, .30), 3))
            await vibration.write_value(round(1.2 + degr * 5.0 + random.gauss(0, .15), 3))
            await temp.write_value(round(45.0 + degr * 25.0 + random.gauss(0, .80), 3))
            await pressure.write_value(round(6.0 - degr * 1.0 + random.gauss(0, .10), 3))
            t += 1
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPLC virtual encerrado.")