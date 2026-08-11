# app/agents.py
from google.adk import Agent
from google.adk.tools import AgentTool

from app.tools import get_weather, search_restaurants, book_reservation

travel_worker = Agent(
    name="travel_worker",
    model="gemini-2.5-flash",
    mode="single_turn",
    instruction=(
        "You are a travel assistant. Help the coordinator by executing tools "
        "to check weather, search restaurants, and book reservations. "
        "Always use the correct tool and report the raw findings clearly."
    ),
    tools=[get_weather, search_restaurants, book_reservation],
)

coordinator = Agent(
    name="coordinator",
    model="gemini-2.5-pro",
    instruction=(
        "You are a personal concierge. Help the user plan their day. "
        "You MUST delegate all travel details, weather checks, restaurant searches, "
        "and reservation bookings to the travel_worker agent. "
        "Do not try to guess weather or restaurants yourself. "
        "Keep track of user preferences and guide the conversation."
    ),
    sub_agents=[travel_worker],
)

