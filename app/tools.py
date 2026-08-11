# app/tools.py
import functools
import logging
import datetime
from typing import Optional, Annotated
from pydantic import validate_call, ValidationError, Field, ConfigDict, BeforeValidator
from google.adk.tools import ToolContext

logger = logging.getLogger("tools")

# Custom error handler decorator to format validation errors for the LLM
def tool_error_handler(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            errors = e.errors()
            error_msgs = []
            for err in errors:
                # Remove "args" from location path for cleaner messages to LLM
                loc = [str(x) for x in err["loc"] if x != "args"]
                loc_str = " -> ".join(loc)
                msg = err["msg"]
                error_msgs.append(f"Invalid argument '{loc_str}': {msg}")
            error_response = "Error: " + "; ".join(error_msgs) + ". Please correct the arguments and try again."
            logger.warning(f"Tool {func.__name__} validation failed: {error_response}")
            return error_response
        except Exception as e:
            error_response = f"Error executing tool: {str(e)}. Please check parameters and try again."
            logger.error(f"Tool {func.__name__} failed: {error_response}", exc_info=True)
            return error_response
    return wrapper

# Validator for YYYY-MM-DD date format
def validate_date_format(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("Date must be a string.")
    try:
        datetime.datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format (e.g. '2026-08-15').")
    return v

DateStr = Annotated[str, BeforeValidator(validate_date_format)]

@tool_error_handler
@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def get_weather(
    city: Annotated[str, Field(description="The name of the city.")],
    date: Annotated[DateStr, Field(description="The date in YYYY-MM-DD format.")]
) -> str:
    """Gets the weather forecast for a city on a specific date.

    Args:
        city: The name of the city.
        date: The date in YYYY-MM-DD format.
    """
    logger.info(
        f"get_weather tool called for {city} on {date}",
        extra={"intent": f"Retrieve weather data for {city} on {date}"}
    )
    
    result = "Sunny"
    if city.lower() == "chicago" and date == "2026-08-15":
        result = "Rain"
        
    logger.info(
        f"get_weather tool finished: {result}",
        extra={"outcome": f"Weather is {result}"}
    )
    return result

@tool_error_handler
@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def search_restaurants(
    city: Annotated[str, Field(description="The city to search in.")],
    cuisine: Annotated[Optional[str], Field(description="Optional cuisine type (e.g., 'Italian'). If not provided, recalls from preferences.")] = None,
    tool_context: Optional[ToolContext] = None
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
        extra={"intent": f"Search restaurants in {city} for cuisine: {target_cuisine}"}
    )
    
    if cuisine and tool_context and tool_context.state:
        tool_context.state["user:preference"] = cuisine

    restaurants = [
        {"name": "Gino's East", "city": "Chicago", "cuisine": "Italian"},
        {"name": "Lou Malnati's", "city": "Chicago", "cuisine": "Italian"},
        {"name": "Al's Beef", "city": "Chicago", "cuisine": "American"},
    ]
    
    matches = [
        r["name"] for r in restaurants 
        if r["city"].lower() == city.lower() 
        and (target_cuisine.lower() == "any" or r["cuisine"].lower() == target_cuisine.lower())
    ]
    
    if not matches:
        outcome_msg = f"No {target_cuisine} restaurants found."
        result_str = f"No {target_cuisine} restaurants found in {city}."
    else:
        outcome_msg = f"Found {len(matches)} restaurants."
        result_str = f"Found restaurants in {city} matching '{target_cuisine}': " + ", ".join(matches)
        
    logger.info(
        f"search_restaurants tool finished: {outcome_msg}",
        extra={"outcome": outcome_msg}
    )
    return result_str

@tool_error_handler
@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def book_reservation(
    restaurant_name: Annotated[str, Field(description="The name of the restaurant.")],
    time: Annotated[str, Field(description="The time of the reservation (e.g., '7 PM').")],
    tool_context: ToolContext
) -> str:
    """Books a reservation at a restaurant. Requires user confirmation.

    Args:
        restaurant_name: The name of the restaurant.
        time: The time of the reservation (e.g., '7 PM').
        tool_context: The ADK tool context for HITL confirmation.
    """
    logger.info(
        f"book_reservation tool called for {restaurant_name} at {time}",
        extra={"intent": f"Book reservation at {restaurant_name} for {time}"}
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
        payload={"restaurant_name": restaurant_name, "time": time}
    )
    return "Booking pending approval."

