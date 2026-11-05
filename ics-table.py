#!/usr/bin/env python3

import sys
import csv
from datetime import datetime

def unfold(lines):
    result = []
    for line in lines:
        line = line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and result:
            result[-1] += line[1:]
        else:
            result.append(line)
    return result

def unescape(value):
    return (
        value
        .replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )

def parse_value(line):
    if ":" not in line:
        return None, None
    key, value = line.split(":", 1)
    key = key.split(";", 1)[0]
    return key, unescape(value)

events = []
current = None

with open(sys.argv[1], encoding="utf-8-sig", errors="replace") as f:
    lines = unfold(f)

for line in lines:
    if line == "BEGIN:VEVENT":
        current = {}

    elif line == "END:VEVENT":
        if current is not None:
            events.append(current)
        current = None

    elif current is not None:
        key, value = parse_value(line)
        if key:
            current[key] = value

writer = csv.writer(sys.stdout, delimiter="\t")
writer.writerow([
    "DTSTART",
    "DTEND",
    "SUMMARY",
    "LOCATION",
    "DESCRIPTION",
    "UID",
])

for event in events:
    writer.writerow([
        event.get("DTSTART", ""),
        event.get("DTEND", ""),
        event.get("SUMMARY", ""),
        event.get("LOCATION", ""),
        event.get("DESCRIPTION", ""),
        event.get("UID", ""),
    ])