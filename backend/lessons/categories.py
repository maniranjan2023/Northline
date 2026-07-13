"""Lesson categories used for retrieval and organization."""

from __future__ import annotations

CATEGORIES = (
    "Opening Hours",
    "Travel Efficiency",
    "Budget",
    "Hotels",
    "Restaurants",
    "Transportation",
    "Activity Balance",
    "Destination Tips",
    "User Preferences",
    "Crowd Management",
    "Weather",
    "Itinerary Structure",
)

ISSUE_CATEGORY_MAP = {
    "itinerary_too_short": "Itinerary Structure",
    "missing_destination": "Destination Tips",
    "day_count_mismatch": "Itinerary Structure",
    "missing_budget": "Budget",
    "missing_preference": "User Preferences",
    "missing_flights": "Transportation",
    "missing_hotels": "Hotels",
    "too_much_travel": "Travel Efficiency",
    "duplicate_attractions": "Activity Balance",
    "overloaded_day": "Activity Balance",
    "poor_daily_balance": "Activity Balance",
    "missing_meal_break": "Restaurants",
}
