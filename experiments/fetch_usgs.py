"""Скачивает суточные данные USGS Water Services (dv) в CSV для пайплайна.

Пример:
  python experiments/fetch_usgs.py --sites 01646500 01491000 --start 2024-01-01 --end 2024-12-31 --out usgs.csv
Параметры USGS: 00400 pH, 00010 температура, 63680 мутность, 00300 растворённый O2.
"""
import argparse
import csv
import json
import urllib.request

PARAMS = {"00400": "ph", "00010": "temperature", "63680": "turbidity", "00300": "dissolved_oxygen"}


def fetch(sites, start, end):
    url = (
        "https://waterservices.usgs.gov/nwis/dv/?format=json"
        f"&sites={','.join(sites)}&parameterCd={','.join(PARAMS)}"
        f"&startDT={start}&endDT={end}&statCd=00003"
    )
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def to_rows(payload):
    table = {}
    for series in payload["value"]["timeSeries"]:
        site = series["sourceInfo"]["siteCode"][0]["value"]
        name = PARAMS.get(series["variable"]["variableCode"][0]["value"])
        if not name:
            continue
        for item in series["values"][0]["value"]:
            key = (site, item["dateTime"])
            table.setdefault(key, {})[name] = item["value"]
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", default="usgs.csv")
    args = parser.parse_args()
    table = to_rows(fetch(args.sites, args.start, args.end))
    with open(args.out, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["station_id", "measured_at", *PARAMS.values()])
        for (site, stamp), values in sorted(table.items()):
            writer.writerow([site, stamp, *[values.get(name, "") for name in PARAMS.values()]])
    print(f"{len(table)} rows -> {args.out}")


if __name__ == "__main__":
    main()
