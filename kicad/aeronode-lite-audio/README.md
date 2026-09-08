# aeronode-lite audio interface — mirror, NOT canonical

**Canonical:** `~/aerosense/aeronode/aerosense/aeronode-lite/` on Peter's Mac. That tree is **not
under git**, which is why this mirror exists.

`before/` is a byte copy taken **2026-09-08, immediately before LIMA drew the transformer + relay
block** into the canonical `aeronode-audio-interface.kicad_sch`. It is the undo.

To roll the canonical file back:

```
cp kicad/aeronode-lite-audio/before/aeronode-audio-interface.kicad_sch \
   ~/aerosense/aeronode/aerosense/aeronode-lite/aeronode-audio-interface.kicad_sch
```

A timestamped `.bak-LIMA-<stamp>` also sits beside the canonical file.

**Do not edit this mirror.** Changes go to the canonical tree through Konnect MCP tools, then get
re-copied here. Editing a `.kicad_sch` as text breaks its UUIDs and cross-references.
