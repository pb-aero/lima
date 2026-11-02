#!/usr/bin/env python3
"""AeroNode rev 0.0.2 + AeroImu + AeroVault power budget, at the battery.

Boards: the vendor schematics "Schematic for {Aeronode,AeroImu,AeroVault} HW ver 0.0.2 rev 1",
drawn 2026-10-01, read 2026-11-02.  Every input below is tagged.  NOTHING IS MEASURED.

  [fetched]  from a datasheet or the vendor's own published figure
  [repo]     from a decision or figure already on our record
  [assumed]  my estimate - the ones that matter are listed in the doc
"""
VBAT_NOM, VBAT_EMPTY, VBAT_FULL = 6.4, 5.0, 7.3   # [repo] 2S LiFePO4, ARCHITECTURE.md

ETA_BUCK = 0.90    # [assumed] TPS564252 at these loads; datasheet curves peak ~93%
V5, V33 = 5.0, 3.3

# ---- 5 V rail (Vcm5) -------------------------------------------------------
CM5_IDLE_A  = 0.400   # [fetched] Raspberry Pi CM5 datasheet: "idle typically 400mA"
CM5_OPER_A  = 0.900   # [fetched] same: "operating typically around 900mA"
                      #   both EXCLUDE the module's own 3V3/1V8 regulator outputs
HEATER_W    = 1.0     # [repo] "heater ~1 W into 0.5 ohm off 5 V", AeroNode decisions 4 Aug

# ---- 3.3 V rail (Vcm3) -----------------------------------------------------
HAILO_TYP_W = 1.5     # [fetched] Hailo product page / ICPDAS datasheet, Hailo-8L M.2 typical
HAILO_MAX_W = 6.6     # [fetched] Hailo-8L M.2 datasheet TDP, "2 A total from 3.3V pins"
PHY_W       = 0.50    # [assumed] BCM54210PE 1000BASE-T active; Broadcom datasheet not obtained
GPS_A       = 0.024   # [fetched] u-blox DAN-F10N, I_VCC 24 mA
SENSORS_A   = 0.002   # [fetched] BME690 uA-class + [assumed] MMC5983MA/BMP390/BMP581 ~0.5 mA ea
CO_CHAIN_A  = 0.0012  # [assumed] ADS1115 150 uA + TLV8811 ~1 mA; TGS5141 cell is passive
LED_A       = 0.020   # [assumed] LP5815 driver + status LEDs, average
IMU_A       = 0.002   # [assumed] ICM-45686 + LSM6DSV320X via the island's TPS7A2033
VAULT_RD_A  = 0.025   # [assumed] F35SQB004G active read/program
VAULT_IDLE_A= 0.00005 # [assumed] standby

HEADSET_W   = 1.733   # [repo] my own H1 budget, 2026-10-30, normal use at the battery

def rail(v, amps, eta=ETA_BUCK):
    """Power drawn from the battery to deliver `amps` at `v` through a buck."""
    return v*amps/eta

def total(mode, vbat=VBAT_NOM):
    cm5 = CM5_IDLE_A if mode in ("idle","cruise") else CM5_OPER_A
    hailo_w = 0.0 if mode=="idle" else (HAILO_TYP_W if mode=="cruise" else HAILO_MAX_W)
    heater = 0.0 if mode=="idle" else HEATER_W          # island heats in flight
    vault = VAULT_IDLE_A if mode=="idle" else VAULT_RD_A
    p5  = rail(V5,  cm5) + heater/ETA_BUCK
    a33 = hailo_w/V33 + PHY_W/V33 + GPS_A + SENSORS_A + CO_CHAIN_A + LED_A + IMU_A + vault
    p33 = rail(V33, a33)
    return {"CM5":rail(V5,cm5), "heater":heater/ETA_BUCK, "Hailo":rail(V33,hailo_w/V33),
            "PHY":rail(V33,PHY_W/V33), "GPS":rail(V33,GPS_A),
            "sensors+CO+LED+IMU+vault":rail(V33,SENSORS_A+CO_CHAIN_A+LED_A+IMU_A+vault),
            "_node_total":p5+p33}

if __name__=="__main__":
    print("AeroNode rev 0.0.2 + island + vault, at VBAT = %.1f V\n"%VBAT_NOM)
    for mode,label in (("idle","Idle - CM5 idle, Hailo off, no heat"),
                       ("cruise","Cruise - CM5 idle, Hailo typical, heater on"),
                       ("peak","Peak - CM5 operating, Hailo at TDP, heater on")):
        d=total(mode); n=d.pop("_node_total")
        print("%s\n  %s"%(label,"-"*66))
        for k,v in d.items():
            if v>0.001: print("    %-28s %7.0f mW"%(k,v*1000))
        print("    %-28s %7.0f mW   = %.0f mA at %.1f V"%("AeroNode subtotal",n*1000,n/VBAT_NOM*1000,VBAT_NOM))
        print("    %-28s %7.0f mW"%("H1 headset [repo]",HEADSET_W*1000))
        tot=n+HEADSET_W
        print("    %-28s %7.0f mW   = %.0f mA at %.1f V, %.0f mA at %.1f V\n"%(
            "SYSTEM TOTAL",tot*1000,tot/VBAT_NOM*1000,VBAT_NOM,tot/VBAT_EMPTY*1000,VBAT_EMPTY))
    # endurance on the specified pack
    PACK_AH=6.0   # [repo] 2S LiFePO4 6000 mAh, ARCHITECTURE.md
    for mode in ("idle","cruise","peak"):
        d=total(mode); n=d["_node_total"]; tot=n+HEADSET_W
        wh=PACK_AH*VBAT_NOM
        print("%-7s system %5.2f W  ->  %.1f h on a %.0f Ah 2S pack (%.0f Wh)"%(mode,tot,wh/tot,PACK_AH,wh))
