#!/usr/bin/env python3
"""Quick end-to-end test: renders a small label and prints it via the shim's
own code path to the given CUPS queue.  Usage:  python3 test-print.py [queue]"""
import sys
sys.path.insert(0, "/home/tomashaaland/.local/share/dymo-bridge")
import dymo_bridge as db

queue = sys.argv[1] if len(sys.argv) > 1 else (db.list_dymo_printers() or [{"queue": None}])[0]["queue"]
if not queue:
    sys.exit("No DYMO CUPS queue found.")

xml = '''<?xml version="1.0" encoding="utf-8"?>
<DieCutLabel Version="8.0" Units="twips">
  <PaperOrientation>Landscape</PaperOrientation>
  <PaperName>30321 Large Address</PaperName>
  <RootCell>
    <ObjectInfo>
      <TextObject><Name>T</Name><HorizontalAlignment>Center</HorizontalAlignment>
        <VerticalAlignment>Middle</VerticalAlignment><TextFitMode>ShrinkToFit</TextFitMode>
        <StyledText><Element><String>SkyKeeper
dymo-bridge OK</String>
        <Attributes><Font Family="Arial" Size="12" Bold="True" Italic="False"/>
        <ForeColor Alpha="255" Red="0" Green="0" Blue="0"/></Attributes></Element></StyledText>
      </TextObject><Bounds X="100" Y="100" Width="3400" Height="1600"/>
    </ObjectInfo>
    <ObjectInfo>
      <BarcodeObject><Name>QRCode</Name><Text>https://skykeeper.aero</Text>
        <Type>QRCode</Type><ECLevel>0</ECLevel>
        <HorizontalAlignment>Center</HorizontalAlignment></BarcodeObject>
      <Bounds X="3700" Y="200" Width="1200" Height="1200"/>
    </ObjectInfo>
  </RootCell>
</DieCutLabel>'''

print(f"Rendering test label and sending to CUPS queue '{queue}' ...")
img = db.render_label(xml)
ok = db.print_image(queue, img, copies=1)
print("Printed ✅" if ok else "Print failed ❌ — see dymo-bridge.log")
