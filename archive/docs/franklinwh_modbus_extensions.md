| Address | Register | Access | Notes |
|---------|----------|--------|-------|
| 15500 | PV Installed | R | PVUse: Installed Solar PV Flag |
| 15501 | PV Installed | R | apBoxPVUse: Installed Remote Solar PV System Flag |
| 15502 | PV Total Power  | R | PVOutputP: Solar PV power in W |
| 15503 | PV Proximal Power | R | proximalPVOutputP: Proximal Solar PV power in W |
| 15504 | PV Remote 1 Power | R | RemotePV1: Remote Solar PV 1 power in W |
| 15505 | PV Remote 2 Power | R | RemotePV2: Remote Solar PV 2 power in W |
| 15506 | Home Load | R | LoadActiveP: Total home loads powerin W |
| 15507 | Set/Current Operating Mode | RW | OnGridMode: **1=Emergency Backup, 2=Self-Consumption, 3=Time-Of-Use** |
| 15508 | Self-Consumption SOC Reserve % | RW | SelfReserve: SOC reserved for Self mode |
| 15509 | Time-of-User SOC Reserve % | RW | TouReserve: SOC reserved for TOU mode |
| 15510 | PV Energy | R | PVOutputWh: PV Power Output in Wh (High Word) (32-bit) |
| 15511 | PV Energy | R | --> low word|
| 15512 | PV Energy Proximal | R | proximalOutputWh: Proximal PV Power in Wh (High Word) Wh counters (32-bit) |
| 15513 | PV Energy Proximal| R | --> low word|