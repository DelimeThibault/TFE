from fitparse import FitFile
import csv

fitfile = FitFile("callibration.fit")
with open("output.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "power", "cadence"])
    for record in fitfile.get_messages("record"):
        data = {d.name: d.value for d in record}
        writer.writerow([data.get("timestamp"), data.get("power"), data.get("cadence")])
