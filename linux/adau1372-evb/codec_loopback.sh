#!/usr/bin/env bash
# DIGITAL LOOPBACK THROUGH THE ADAU1372.
# Serial Output slot N <- Serial Input slot N, inside the codec.  The Pi plays a
# different tone into each TDM slot and records what comes back, so the slot map
# identifies itself instead of being assumed.  No rewiring: it uses the data
# lines already in place.
set -u
C=adau1372

echo "=== route serial input -> serial output inside the codec ==="
for n in 0 1 2 3; do
  amixer -c $C -q cset name="Serial Output $n Capture Mux" "Serial Input $n" >/dev/null 2>&1 \
    || echo "  MISS: Serial Output $n Capture Mux"
  printf '  Serial Output %s Capture Mux -> %s\n' "$n" \
    "$(amixer -c $C cget name="Serial Output $n Capture Mux" 2>/dev/null | grep ': values=' | tr -d ' ')"
done

python3 - <<'EOF'
import wave, struct, math
w = wave.open("/tmp/slots.wav", "w"); w.setnchannels(4); w.setsampwidth(4); w.setframerate(48000)
f = [250, 1000, 3000, 6000]
n = 48000 * 6
w.writeframes(b"".join(struct.pack("<iiii",
    *(int(0.25*(2**31-1)*math.sin(2*math.pi*fk*i/48000)) for fk in f)) for i in range(n)))
w.close()
print("  tx: slot0=250Hz slot1=1kHz slot2=3kHz slot3=6kHz, -12 dBFS each")
EOF

timeout 20 aplay -D hw:2,0 /tmp/slots.wav >/dev/null 2>&1 &
sleep 0.8
timeout 20 arecord -D hw:2,0 -f S32_LE -c 4 -r 48000 -d 3 /tmp/slotsrx.wav 2>&1 | grep -iE 'error|fail'
wait 2>/dev/null

python3 - <<'EOF'
import wave, struct, math
w = wave.open("/tmp/slotsrx.wav"); ch = w.getnchannels(); d = w.readframes(w.getnframes())
v = struct.unpack("<%di" % (len(d)//4), d)
tones = [250, 1000, 3000, 6000]
print("=== what came back ===")
for c in range(ch):
    s = v[c::ch][4800:4800+8192]
    nz = [x for x in s if x]
    if not nz:
        print(f"  ch{c}: ALL ZERO"); continue
    mags = []
    for fk in tones:
        re = sum(x*math.cos(2*math.pi*fk*i/48000) for i, x in enumerate(s))
        im = sum(x*math.sin(2*math.pi*fk*i/48000) for i, x in enumerate(s))
        mags.append((math.hypot(re, im)/len(s), fk))
    mags.sort(reverse=True)
    pk = max(abs(x) for x in nz)
    top, second = mags[0], mags[1]
    ratio = top[0]/second[0] if second[0] else float('inf')
    print(f"  ch{c}: peak={pk} ({20*math.log10(pk/2**31):+.1f} dBFS)  "
          f"dominant {top[1]} Hz = tx slot {tones.index(top[1])}  ({ratio:.0f}x above next)")
EOF

echo "=== restore the capture path to the ADCs ==="
for n in 0 1 2 3; do
  amixer -c $C -q cset name="Serial Output $n Capture Mux" "Output ASRC$n" >/dev/null 2>&1
done
echo "  done"
