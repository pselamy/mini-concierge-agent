# app/tools.py
from google.adk.tools import ToolContext
from typing import Optional, List
import logging

logger = logging.getLogger("tools")


def get_weather(city: str, date: str) -> str:
    """Gets the weather forecast for a city on a specific date.

    Args:
        city: The name of the city.
        date: The date in YYYY-MM-DD format.
    """
    logger.info(
        f"get_weather tool called for {city} on {date}",
        extra={"intent": f"Retrieve weather data for {city} on {date}"},
    )

    result = "Sunny"
    if city.lower() == "chicago" and date == "2026-08-15":
        result = "Rain"

    logger.info(
        f"get_weather tool finished: {result}",
        extra={"outcome": f"Weather is {result}"},
    )
    return result


def search_restaurants(
    city: str, cuisine: Optional[str] = None, tool_context: Optional[ToolContext] = None
) -> str:
    """Searches for restaurants in a city, prioritizing user preferences.

    Args:
        city: The city to search in.
        cuisine: Optional cuisine type (e.g., 'Italian'). If not provided, recalls from preferences.
        tool_context: The ADK tool context.
    """
    recalled_cuisine = None
    if tool_context and tool_context.state:
        recalled_cuisine = tool_context.state.get("user:preference")

    target_cuisine = cuisine or recalled_cuisine or "Any"

    logger.info(
        f"search_restaurants tool called for {city} (cuisine requested: {cuisine}, recalled: {recalled_cuisine})",
        extra={"intent": f"Search restaurants in {city} for cuisine: {target_cuisine}"},
    )

    if cuisine and tool_context and tool_context.state:
        tool_context.state["user:preference"] = cuisine

    restaurants = [
        {"name": "Gino's East", "city": "Chicago", "cuisine": "Italian"},
        {"name": "Lou Malnati's", "city": "Chicago", "cuisine": "Italian"},
        {"name": "Al's Beef", "city": "Chicago", "cuisine": "American"},
    ]

    matches = [
        r["name"]
        for r in restaurants
        if r["city"].lower() == city.lower()
        and (
            target_cuisine.lower() == "any"
            or r["cuisine"].lower() == target_cuisine.lower()
        )
    ]

    if not matches:
        outcome_msg = f"No {target_cuisine} restaurants found."
        result_str = f"No {target_cuisine} restaurants found in {city}."
    else:
        outcome_msg = f"Found {len(matches)} restaurants."
        result_str = (
            f"Found restaurants in {city} matching '{target_cuisine}': "
            + ", ".join(matches)
        )

    logger.info(
        f"search_restaurants tool finished: {outcome_msg}",
        extra={"outcome": outcome_msg},
    )
    return result_str


def book_reservation(restaurant_name: str, time: str, tool_context: ToolContext) -> str:
    """Books a reservation at a restaurant. Requires user confirmation.

    Args:
        restaurant_name: The name of the restaurant.
        time: The time of the reservation (e.g., '7 PM').
        tool_context: The ADK tool context for HITL confirmation.
    """
    logger.info(
        f"book_reservation tool called for {restaurant_name} at {time}",
        extra={"intent": f"Book reservation at {restaurant_name} for {time}"},
    )

    if tool_context.tool_confirmation:
        if tool_context.tool_confirmation.confirmed:
            outcome_msg = "Booking approved and completed."
            logger.info(outcome_msg, extra={"outcome": outcome_msg})
            return f"Successfully booked a table at {restaurant_name} for {time}."
        else:
            outcome_msg = "Booking rejected by user."
            logger.info(outcome_msg, extra={"outcome": outcome_msg})
            return f"Booking at {restaurant_name} was rejected by user."

    # If we get here, we need confirmation
    outcome_msg = "Booking paused, awaiting confirmation."
    logger.info(outcome_msg, extra={"outcome": outcome_msg})

    tool_context.request_confirmation(
        hint=f"Confirm booking at {restaurant_name} for {time}?",
        payload={"restaurant_name": restaurant_name, "time": time},
    )
    return "Booking pending approval."
