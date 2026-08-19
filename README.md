# Ponte OPC UA: um modelo, dois vendors (OpenPLC + Siemens)

Um gateway de borda que roda o modelo preditivo **uma vez** e conversa com
qualquer CLP via OPC UA. Trocar de vendor = trocar de **perfil no config.yaml**,
sem tocar no codigo do modelo.

```
                         config.yaml (perfil)
                                 |
  [Siemens S7-1500/PLCSIM] --OPC UA nativo--\
                                             +--> gateway.py --(writeback)--> CLP
  [OpenPLC] --Modbus--> openplc_shim.py --OPC UA--/     (Isolation Forest)
  [plc_sim.py] --OPC UA--------------------/
```

O ponto-chave: o `gateway.py` resolve **todas** as tags por NodeId. Siemens,
OpenPLC (via shim) e o simulador expoem os mesmos nomes logicos, entao o mesmo
modelo serve os tres. So o config muda.

## Arquivos

| Arquivo             | Papel                                                        |
|---------------------|-------------------------------------------------------------|
| `gateway.py`        | Gateway universal: le OPC UA, roda o modelo, escreve alerta |
| `config.yaml`       | Perfis `sim` / `openplc` / `siemens` (a UNICA coisa que muda)|
| `plc_sim.py`        | Simulador OPC UA (tambem emula um endpoint estilo Siemens)  |
| `openplc_shim.py`   | Da' cara OPC UA ao OpenPLC (Modbus <-> OPC UA, dois sentidos)|

## Rodar

```bash
pip install -r requirements.txt
```

### A) Simulador (rapido, sem nada instalado)
```bash
python plc_sim.py           # terminal 1
python gateway.py sim       # terminal 2
```

### B) OpenPLC (open source, ladder real)
1. Suba o OpenPLC Runtime com seu programa e o servidor Modbus (porta 502).
2. Mapeie os located variables para os input/holding registers usados no
   `openplc_shim.py` (veja o cabecalho do arquivo; ajuste enderecos/escala).
```bash
python openplc_shim.py      # terminal 1  (Modbus -> OPC UA em :4842)
python gateway.py openplc   # terminal 2
```

### C) Siemens (S7-1500 / PLCSIM Advanced)
1. No TIA Portal, ative o **servidor OPC UA** da CPU e marque os tags do DB
   como acessiveis (leitura + escrita nos de writeback).
2. Ajuste `endpoint` e os NodeIds no perfil `siemens` do `config.yaml`
   (padrao Siemens: `ns=3;s="DB_Motor"."Current"`).
```bash
python gateway.py siemens
```

## O que ja foi validado
- Gateway resolvendo tags por NodeId e escrevendo o alarme de volta (caminho
  `sim`/`siemens`).
- Shim OpenPLC nos dois sentidos: sensores Modbus -> OPC UA e writeback OPC UA
  -> holding register.

O perfil `siemens` e' config-only (PLCSIM/TIA sao licenciados). Ate ter a
licenca, use `plc_sim.py` como stand-in: ele expoe NodeIds no mesmo esquema de
enderecamento, entao o `gateway.py siemens` funciona sem mudar codigo -- so o
endpoint.

## Nota de seguranca OT
O writeback e' **advisorio** (alarme + chamado). Em campo, o intertravamento
critico fica no proprio CLP, determinístico. A IA levanta a mao; o CLP decide.

---

## Track de vibracao com FFT (manutencao preditiva de rolamento)

Versao mais proxima de um caso industrial real. O CLP publica a **forma de onda**
da vibracao (nao um numero so), e o gateway faz a **FFT** para pegar o defeito
na frequencia caracteristica (BPFO) antes de o RMS total subir.

| Arquivo             | Papel                                                         |
|---------------------|--------------------------------------------------------------|
| `plc_sim_vib.py`    | Soft-PLC OPC UA que publica bloco de forma de onda (defeito BPFO cresce) |
| `gateway_fft.py`    | Le a onda, extrai features de tempo (RMS, crest, kurtose) e frequencia (bandas 1x/BPFO/2xBPFO), detecta e escreve o alerta |

Autonomo (nao usa config.yaml; endpoint proprio na porta 4841):

```bash
python plc_sim_vib.py     # terminal 1
python gateway_fft.py     # terminal 2
```

No terminal do gateway voce ve, lado a lado, quanto o **RMS** e a **energia BPFO**
subiram vs baseline. A BPFO dispara muito antes -- foi por isso que se trocou a
vibracao "crua" pela analise espectral. Ajuste `FR` e `BPFO` conforme a rotacao e
o rolamento reais do seu ativo (a BPFO vem da geometria do rolamento x rotacao).
