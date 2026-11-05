depth = 00
seen_component = False
import sys

with open(sys.argv[1], "r", encoding="utf-8-sig", errors="replace") as f:
    for lineno, raw in enumerate(f, 1):
        line = raw.rstrip("\r\n")

        if line.startswith("BEGIN:"):
            component = line[6:]
            if component != "VCALENDAR":
                if depth == 1:
                    seen_component = True
                depth += 1
            else:
                depth = 1
            continue

        if line.startswith("END:"):
            component = line[4:]
            if component != "VCALENDAR":
                depth -= 1
            continue

        if depth == 1 and seen_component and line and not line.startswith((" ", "\t")):
            print(f"{lineno}: {line}")