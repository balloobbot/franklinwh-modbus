"""SunSpec components for the FranklinWH aGate's register map."""

from __future__ import annotations

from ._generated import (
    Common,
    DERCapacity,
    DERCtl,
    DERCtlAC,
    DEREnterService,
    DERFreqDroop,
    DERMeasureAC,
    DERMeasureDC,
    DERStorageCapacity,
    DERTripHF,
    DERTripHV,
    DERTripLF,
    DERTripLV,
    DERVoltVar,
    DERVoltWatt,
    DERWattVar,
    SolarModule,
)

#: Every model this firmware exposes, by SunSpec model ID.
MODELS: dict[int, type] = {
    1: Common,
    502: SolarModule,
    701: DERMeasureAC,
    702: DERCapacity,
    703: DEREnterService,
    704: DERCtlAC,
    705: DERVoltVar,
    706: DERVoltWatt,
    707: DERTripLV,
    708: DERTripHV,
    709: DERTripLF,
    710: DERTripHF,
    711: DERFreqDroop,
    712: DERWattVar,
    713: DERStorageCapacity,
    714: DERMeasureDC,
    715: DERCtl,
}

__all__ = ["MODELS", *sorted(cls.__name__ for cls in MODELS.values())]
