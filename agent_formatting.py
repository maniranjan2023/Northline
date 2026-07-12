"""Normalize MCP tool payloads and format agent output for the UI."""

from __future__ import annotations

import json
import re
from typing import Any


def _loads_if_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def parse_mcp_result(value: Any) -> Any:
    """Unwrap LangChain MCP results like [{'type': 'text', 'text': '{...}'}]."""
    if value is None:
        return None

    if isinstance(value, dict):
        if any(key in value for key in ("city", "forecast", "temperature_c", "results", "answer")):
            return value
        if value.get("type") == "text" and "text" in value:
            return parse_mcp_result(value["text"])

    if isinstance(value, list):
        if value and all(isinstance(item, dict) and item.get("type") == "text" for item in value):
            merged: dict[str, Any] = {}
            for block in value:
                parsed = parse_mcp_result(block.get("text"))
                if isinstance(parsed, dict):
                    merged.update(parsed)
            if merged:
                return merged
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                parsed = parse_mcp_result(item.get("text"))
                if parsed is not None:
                    return parsed

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            parsed = _loads_if_json(stripped)
            if parsed is not None:
                return parse_mcp_result(parsed)
        return stripped

    return value


def _format_temp(value: Any) -> str:
    try:
        return f"{float(value):.0f}°C"
    except (TypeError, ValueError):
        return str(value)


def format_weather_markdown(weather_data: Any, forecast_data: Any) -> str:
    """Turn raw MCP weather payloads into readable markdown."""
    current = parse_mcp_result(weather_data)
    forecast = parse_mcp_result(forecast_data)

    lines: list[str] = []

    if isinstance(current, dict) and "temperature_c" in current:
        city = current.get("city") or forecast.get("city") if isinstance(forecast, dict) else "Destination"
        lines.extend(
            [
                f"### 🌤️ Weather in **{city}**",
                "",
                f"**Right now:** {_format_temp(current.get('temperature_c'))} "
                f"(feels like {_format_temp(current.get('feels_like_c'))})",
                f"**Conditions:** {str(current.get('condition', '—')).title()}",
                f"**Humidity:** {current.get('humidity', '—')}% · "
                f"**Wind:** {current.get('wind_speed', '—')} m/s",
            ]
        )

    if isinstance(forecast, dict) and isinstance(forecast.get("forecast"), list):
        city = forecast.get("city") or (current.get("city") if isinstance(current, dict) else "Destination")
        if not lines:
            lines.append(f"### 🌤️ Forecast for **{city}**")
            lines.append("")
        lines.append("**Upcoming:**")
        for item in forecast["forecast"][:5]:
            if not isinstance(item, dict):
                continue
            when = item.get("datetime", "—")
            temp = _format_temp(item.get("temperature"))
            condition = str(item.get("weather", "—")).title()
            lines.append(f"- **{when}** — {temp}, {condition}")

    if lines:
        return "\n".join(lines)

    return "_Weather data unavailable for this destination._"


def split_hotel_markdown(text: str) -> tuple[str, list[str], str]:
    """
    Split hotel agent markdown into overview, bullet picks, and tip line.
    """
    overview_parts: list[str] = []
    picks: list[str] = []
    tip = ""
    in_picks = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if re.match(r"^[-*•]\s+", line) or re.match(r"^\d+\.\s+", line):
            in_picks = True
            clean = re.sub(r"^[-*•]\s+|^\d+\.\s+", "", line)
            picks.append(clean)
            continue

        if in_picks and line.lower().startswith(("tip:", "booking tip:", "💡")):
            tip = re.sub(r"^(tip|booking tip):\s*", "", line, flags=re.IGNORECASE)
            continue

        if not in_picks:
            overview_parts.append(line)
        elif not tip:
            tip = line

    overview = " ".join(overview_parts).strip()
    return overview, picks[:3], tip
