#!/usr/bin/env python3

import argparse
import shutil
import textwrap
from collections import defaultdict


def unfold(lines):
    """Unfold RFC 5545 continuation lines."""
    result = []

    for raw in lines:
        line = raw.rstrip("\r\n")

        if line.startswith((" ", "\t")) and result:
            result[-1] += line[1:]
        else:
            result.append(line)

    return result


def unescape(value):
    """Unescape common iCalendar text escapes."""
    return (
        value
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def parse_property(line):
    """
    Parse an iCalendar property.

    Keep the complete property name including parameters, for example:
        DTSTART;TZID=Europe/Berlin
    """
    if ":" not in line:
        return None, None

    key, value = line.split(":", 1)
    return key, unescape(value)


class Component:
    def __init__(self, name):
        self.name = name
        self.properties = []
        self.children = []


def parse_ics(lines):
    root = Component("ROOT")
    stack = [root]

    for line in lines:
        if line.startswith("BEGIN:"):
            name = line[6:]
            component = Component(name)
            stack[-1].children.append(component)
            stack.append(component)

        elif line.startswith("END:"):
            if len(stack) > 1:
                stack.pop()

        else:
            key, value = parse_property(line)

            if key is not None:
                stack[-1].properties.append((key, value))

    return root


def find_components(component, name):
    """Recursively find components of a given type."""
    found = []

    for child in component.children:
        if child.name == name:
            found.append(child)

        found.extend(find_components(child, name))

    return found


def add_value(result, key, value):
    """Preserve duplicate properties instead of overwriting them."""
    if key not in result:
        result[key] = []

    result[key].append(value)


def flatten_component(component, prefix=""):
    """
    Flatten a component and all nested components.

    Example:
        SUMMARY
        DTSTART;TZID=Europe/Berlin
        VALARM[1].TRIGGER
        VALARM[1].ACTION
        VALARM[2].TRIGGER
    """
    result = {}

    for key, value in component.properties:
        full_key = f"{prefix}{key}"
        add_value(result, full_key, value)

    child_counts = defaultdict(int)

    for child in component.children:
        child_counts[child.name] += 1
        index = child_counts[child.name]

        child_prefix = f"{prefix}{child.name}[{index}]."

        child_values = flatten_component(
            child,
            prefix=child_prefix,
        )

        for key, values in child_values.items():
            for value in values:
                add_value(result, key, value)

    return result


def join_values(values):
    """Represent repeated properties without losing information."""
    return "\n".join(values)


def visible(value):
    """Make embedded newlines easier to show in a table."""
    return value.replace("\r", "")


def determine_columns(rows):
    """
    Keep commonly useful calendar columns first, then append every other
    property in the order it first appears.
    """
    preferred = [
        "DTSTART",
        "DTEND",
        "SUMMARY",
        "DESCRIPTION",
        "LOCATION",
        "STATUS",
        "TRANSP",
        "RRULE",
        "UID",
    ]

    discovered = []

    for row in rows:
        for key in row:
            if key not in discovered:
                discovered.append(key)

    result = []

    # Match preferred names even if parameters are present,
    # e.g. DTSTART;TZID=Europe/Berlin
    for preferred_key in preferred:
        for key in discovered:
            base_key = key.split(";", 1)[0]

            if base_key == preferred_key and key not in result:
                result.append(key)

    for key in discovered:
        if key not in result:
            result.append(key)

    return result


def calculate_widths(columns, rows, max_column_width):
    widths = {}

    for column in columns:
        width = len(column)

        for row in rows:
            value = join_values(row.get(column, []))

            for line in value.splitlines() or [""]:
                width = max(width, len(line))

        widths[column] = min(width, max_column_width)

    return widths


def wrap_cell(value, width):
    if not value:
        return [""]

    result = []

    for original_line in value.splitlines() or [""]:
        wrapped = textwrap.wrap(
            original_line,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        )

        result.extend(wrapped or [""])

    return result


def print_table(columns, rows, max_column_width):
    widths = calculate_widths(
        columns,
        rows,
        max_column_width,
    )

    separator = (
        "+"
        + "+".join("-" * (widths[c] + 2) for c in columns)
        + "+"
    )

    def print_row(values):
        cells = []

        for column, value in zip(columns, values):
            cells.append(
                wrap_cell(
                    visible(value),
                    widths[column],
                )
            )

        height = max(len(cell) for cell in cells)

        for line_number in range(height):
            parts = []

            for column, cell in zip(columns, cells):
                text = (
                    cell[line_number]
                    if line_number < len(cell)
                    else ""
                )

                parts.append(
                    f" {text:<{widths[column]}} "
                )

            print("|" + "|".join(parts) + "|")

    print(separator)
    print_row(columns)
    print(separator)

    for row in rows:
        values = [
            join_values(row.get(column, []))
            for column in columns
        ]

        print_row(values)
        print(separator)


def print_calendar_properties(calendar):
    if not calendar.properties:
        return

    print("CALENDAR PROPERTIES")
    print("===================")

    width = max(len(key) for key, _ in calendar.properties)

    for key, value in calendar.properties:
        value = visible(value).replace("\n", "\\n")
        print(f"{key:<{width}}  {value}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Display an ICS file as a structured terminal table."
    )

    parser.add_argument(
        "file",
        help="Path to the .ics file",
    )

    parser.add_argument(
        "--max-width",
        type=int,
        default=64,
        help="Maximum width of each table column (default: 64)",
    )

    args = parser.parse_args()

    with open(
        args.file,
        encoding="utf-8-sig",
        errors="replace",
    ) as f:
        lines = unfold(f)

    root = parse_ics(lines)

    calendars = find_components(root, "VCALENDAR")

    if not calendars:
        raise SystemExit("No VCALENDAR component found.")

    calendar = calendars[0]

    print_calendar_properties(calendar)

    events = [
        child
        for child in calendar.children
        if child.name == "VEVENT"
    ]

    if not events:
        print("No VEVENT components found.")
        return

    rows = [
        flatten_component(event)
        for event in events
    ]

    columns = determine_columns(rows)

    print(f"EVENTS ({len(events)})")
    print("=" * (9 + len(str(len(events)))))
    print()

    print_table(
        columns,
        rows,
        args.max_width,
    )


if __name__ == "__main__":
    main()