# tests/test_agent.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from google.genai import types
from google.adk.sessions import DatabaseSessionService

client = TestClient(app, raise_server_exceptions=True)

import os


@pytest.fixture(autouse=True)
def clean_database():
    import app.session
    import asyncio

    try:
        asyncio.run(app.session.session_service.close())
    except Exception:
        pass
    db_path = "data/sessions.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
    # Recreate the service to reset internal state flags
    app.session.session_service = DatabaseSessionService(db_url=app.session.db_url)
    yield
    try:
        asyncio.run(app.session.session_service.close())
    except Exception:
        pass
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


# ==============================================================================
# Scenario 1: Weather-aware planning (Rain -> Indoor suggestions)
# ==============================================================================
class WeatherScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)

        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system
        print(f"\n[Mock Weather] System: {system}")
        print(
            f"[Mock Weather] is_coordinator: {is_coordinator}, is_worker: {is_worker}"
        )

        response = None
        if is_coordinator:
            has_worker_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Check weather and restaurants in Chicago on 2026-08-15."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="It is raining in Chicago on 2026-08-15. I recommend indoor activities. For dining, I suggest Gino's East."
                                    )
                                ],
                            )
                        )
                    ]
                )

        elif is_worker:
            has_weather_response = False
            has_search_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "get_weather"
                    ):
                        has_weather_response = True
                    if (
                        p.function_response
                        and p.function_response.name == "search_restaurants"
                    ):
                        has_search_response = True

            if not has_weather_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="get_weather",
                                            args={
                                                "city": "Chicago",
                                                "date": "2026-08-15",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            elif not has_search_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="search_restaurants",
                                            args={"city": "Chicago"},
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "Weather in Chicago is Rain. Found Italian restaurants: Gino's East."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        if response is None:
            response = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text="Fallback")]
                        )
                    )
                ]
            )
        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_weather_scenario(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = WeatherScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    response = client.post(
        "/query",
        json={
            "user_id": "test_user_1",
            "session_id": "session_weather",
            "query": "Plan a day in Chicago on 2026-08-15.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "raining in Chicago" in data["response"]
    assert "indoor activities" in data["response"]
    assert "Gino's East" in data["response"]


# ==============================================================================
# Scenario 2: Preference storage and retrieval
# ==============================================================================
class PreferenceScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        has_restaurant_query = False
        for c in contents:
            for p in c.parts:
                if p.text and "restaurant" in p.text.lower():
                    has_restaurant_query = True

        response = None
        if is_coordinator:
            if not has_restaurant_query:
                # First turn: Acknowledge preference
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="I've noted your preference for Italian food."
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                # Second turn: Delegate
                has_worker_response = False
                for c in contents:
                    for p in c.parts:
                        if (
                            p.function_response
                            and p.function_response.name == "travel_worker"
                        ):
                            has_worker_response = True

                if not has_worker_response:
                    response = types.GenerateContentResponse(
                        candidates=[
                            types.Candidate(
                                content=types.Content(
                                    role="model",
                                    parts=[
                                        types.Part(
                                            function_call=types.FunctionCall(
                                                name="travel_worker",
                                                args={
                                                    "request": "Search restaurants in Chicago."
                                                },
                                            )
                                        )
                                    ],
                                )
                            )
                        ]
                    )
                else:
                    response = types.GenerateContentResponse(
                        candidates=[
                            types.Candidate(
                                content=types.Content(
                                    role="model",
                                    parts=[
                                        types.Part.from_text(
                                            text="I found Italian restaurants in Chicago: Gino's East."
                                        )
                                    ],
                                )
                            )
                        ]
                    )
        elif is_worker:
            has_search_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "search_restaurants"
                    ):
                        has_search_response = True

            if not has_search_response:
                # Call search_restaurants WITHOUT cuisine to test preference recall
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="search_restaurants",
                                            args={"city": "Chicago"},
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "Found Italian restaurants: Gino's East."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        if response is None:
            response = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text="Fallback")]
                        )
                    )
                ]
            )
        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_preference_scenario(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = PreferenceScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    # Step 1: Tell preference
    response1 = client.post(
        "/query",
        json={
            "user_id": "test_user_2",
            "session_id": "session_pref",
            "query": "I prefer Italian food.",
        },
    )
    assert response1.status_code == 200
    assert "noted your preference" in response1.json()["response"]

    # Step 2: Ask for restaurants (should recall preference)
    response2 = client.post(
        "/query",
        json={
            "user_id": "test_user_2",
            "session_id": "session_pref",
            "query": "Find a restaurant in Chicago.",
        },
    )
    assert response2.status_code == 200
    assert "Italian" in response2.json()["response"]
    assert "Gino's East" in response2.json()["response"]


# ==============================================================================
# Scenario 3: HITL Booking (Pause and Resume)
# ==============================================================================
class BookingScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        response = None
        if is_coordinator:
            print(f"\n[Mock Booking Coordinator] Contents: {contents}")
            has_worker_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True
            print(
                f"[Mock Booking Coordinator] has_worker_response: {has_worker_response}"
            )

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Book Gino's East at 7 PM."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="I have successfully booked Gino's East for you at 7 PM."
                                    )
                                ],
                            )
                        )
                    ]
                )

        elif is_worker:
            print(f"\n[Mock Booking Worker] Contents: {contents}")
            has_booking_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "book_reservation"
                    ):
                        has_booking_response = True
            print(f"[Mock Booking Worker] has_booking_response: {has_booking_response}")

            if not has_booking_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="book_reservation",
                                            args={
                                                "restaurant_name": "Gino's East",
                                                "time": "7 PM",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "Successfully booked Gino's East for 7 PM."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        if response is None:
            response = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text="Fallback")]
                        )
                    )
                ]
            )
        print(f"[Mock Booking] Returning: {response}")
        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_hitl_booking_scenario(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = BookingScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    # Step 1: Initial request to book (should pause)
    response1 = client.post(
        "/query",
        json={
            "user_id": "test_user_3",
            "session_id": "session_booking",
            "query": "Book Gino's East at 7 PM.",
        },
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "paused"
    assert data1["message"] == "Requires human approval"
    assert "invocation_id" in data1
    assert "approval_info" in data1
    assert "approval_id" in data1["approval_info"]

    invocation_id = data1["invocation_id"]
    approval_id = data1["approval_info"]["approval_id"]

    # Step 2: Resume with confirmation
    response2 = client.post(
        "/query",
        json={
            "user_id": "test_user_3",
            "session_id": "session_booking",
            "invocation_id": invocation_id,
            "approval_response": {"approval_id": approval_id, "confirmed": True},
        },
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "success"
    assert "successfully booked" in data2["response"]
    assert "Gino's East" in data2["response"]
    assert "7 PM" in data2["response"]


def test_invalid_query():
    response = client.post(
        "/query",
        json={
            "user_id": "test_user_invalid",
            "session_id": "session_invalid",
            "query": "",
        },
    )
    assert response.status_code == 400
    assert "Query is required" in response.json()["detail"]


@pytest.mark.asyncio
@patch("app.main.get_runner")
async def test_agent_execution_error(mock_get_runner):
    mock_runner = MagicMock()
    mock_runner.run_async.side_effect = Exception("Test agent error")
    mock_get_runner.return_value = mock_runner

    response = client.post(
        "/query",
        json={
            "user_id": "test_user_err",
            "session_id": "session_err",
            "query": "Hello",
        },
    )
    assert response.status_code == 500
    assert "Agent execution error" in response.json()["detail"]


# ==============================================================================
# Scenario 4: Preference storage with explicit cuisine in search
# ==============================================================================
class CuisineScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        response = None
        if is_coordinator:
            has_worker_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Search Italian restaurants in Chicago."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="I found Gino's East in Chicago."
                                    )
                                ],
                            )
                        )
                    ]
                )
        elif is_worker:
            has_search_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "search_restaurants"
                    ):
                        has_search_response = True

            if not has_search_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="search_restaurants",
                                            args={
                                                "city": "Chicago",
                                                "cuisine": "Italian",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={"result": "Found Gino's East."},
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_preference_scenario_with_cuisine(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = CuisineScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    response = client.post(
        "/query",
        json={
            "user_id": "test_user_cuisine",
            "session_id": "session_cuisine",
            "query": "Find an Italian restaurant in Chicago.",
        },
    )
    assert response.status_code == 200
    assert "Gino's East" in response.json()["response"]


# ==============================================================================
# Scenario 5: Search restaurants with no matches
# ==============================================================================
class NoMatchCuisineScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        response = None
        if is_coordinator:
            has_worker_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Search French restaurants in Chicago."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="No French restaurants found in Chicago."
                                    )
                                ],
                            )
                        )
                    ]
                )
        elif is_worker:
            has_search_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "search_restaurants"
                    ):
                        has_search_response = True

            if not has_search_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="search_restaurants",
                                            args={
                                                "city": "Chicago",
                                                "cuisine": "French",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "No French restaurants found."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_search_restaurants_no_matches(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = NoMatchCuisineScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    response = client.post(
        "/query",
        json={
            "user_id": "test_user_nomatch",
            "session_id": "session_nomatch",
            "query": "Find a French restaurant in Chicago.",
        },
    )
    assert response.status_code == 200
    assert "No French restaurants found" in response.json()["response"]


# ==============================================================================
# Scenario 6: HITL Booking (Rejected)
# ==============================================================================
class BookingRejectedScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        response = None
        if is_coordinator:
            has_worker_response = False
            is_rejected = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True
                        if "rejected" in str(p.function_response.response):
                            is_rejected = True

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Book Gino's East at 7 PM."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            elif is_rejected:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="I could not book Gino's East because you rejected the confirmation."
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[types.Part.from_text(text="I booked it.")],
                            )
                        )
                    ]
                )

        elif is_worker:
            has_booking_response = False
            is_rejected = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "book_reservation"
                    ):
                        has_booking_response = True
                        if "rejected" in str(p.function_response.response):
                            is_rejected = True

            if not has_booking_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="book_reservation",
                                            args={
                                                "restaurant_name": "Gino's East",
                                                "time": "7 PM",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            elif is_rejected:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "Booking was rejected by user."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={"result": "Booked."},
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_hitl_booking_rejected(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = BookingRejectedScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    # Step 1: Initial request to book (should pause)
    response1 = client.post(
        "/query",
        json={
            "user_id": "test_user_4",
            "session_id": "session_booking_rej",
            "query": "Book Gino's East at 7 PM.",
        },
    )

    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["status"] == "paused"
    assert data1["message"] == "Requires human approval"

    invocation_id = data1["invocation_id"]
    approval_id = data1["approval_info"]["approval_id"]

    # Step 2: Resume with rejection
    response2 = client.post(
        "/query",
        json={
            "user_id": "test_user_4",
            "session_id": "session_booking_rej",
            "invocation_id": invocation_id,
            "approval_response": {"approval_id": approval_id, "confirmed": False},
        },
    )

    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "success"
    assert "could not book" in data2["response"]
    assert "rejected" in data2["response"]


# ==============================================================================
# Scenario 7: Tool argument validation and LLM recovery
# ==============================================================================
class ValidationRecoveryScenarioMock:
    async def __call__(self, *args, **kwargs):
        config = kwargs.get("config")
        system = ""
        if config and config.system_instruction:
            if hasattr(config.system_instruction, "parts"):
                system = config.system_instruction.parts[0].text
            else:
                system = str(config.system_instruction)
        contents = kwargs.get("contents") or []

        is_coordinator = "personal concierge" in system
        is_worker = "travel assistant" in system

        response = None
        if is_coordinator:
            has_worker_response = False
            for c in contents:
                for p in c.parts:
                    if (
                        p.function_response
                        and p.function_response.name == "travel_worker"
                    ):
                        has_worker_response = True

            if not has_worker_response:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={
                                                "request": "Check weather in Chicago on 2026-08-15."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            else:
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="The weather in Chicago on 2026-08-15 is Rain."
                                    )
                                ],
                            )
                        )
                    ]
                )

        elif is_worker:
            has_invalid_weather_call = False
            has_invalid_weather_response = False
            has_valid_weather_response = False

            for c in contents:
                for p in c.parts:
                    if p.function_call and p.function_call.name == "get_weather":
                        if p.function_call.args.get("date") == "2026/08/15":
                            has_invalid_weather_call = True
                    if (
                        p.function_response
                        and p.function_response.name == "get_weather"
                    ):
                        if "Error" in str(p.function_response.response):
                            has_invalid_weather_response = True
                        else:
                            has_valid_weather_response = True

            if not has_invalid_weather_call:
                # First turn: worker tries to call with invalid date format
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="get_weather",
                                            args={
                                                "city": "Chicago",
                                                "date": "2026/08/15",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            elif has_invalid_weather_response and not has_valid_weather_response:
                # Second turn: worker sees error response and corrects it
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="get_weather",
                                            args={
                                                "city": "Chicago",
                                                "date": "2026-08-15",
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )
            elif has_valid_weather_response:
                # Third turn: worker completed the weather check, finish task
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={
                                                "result": "Weather in Chicago is Rain."
                                            },
                                        )
                                    )
                                ],
                            )
                        )
                    ]
                )

        if response is None:
            response = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model", parts=[types.Part.from_text(text="Fallback")]
                        )
                    )
                ]
            )
        return response


@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_tool_validation_recovery(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_mock = ValidationRecoveryScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    response = client.post(
        "/query",
        json={
            "user_id": "test_user_val_rec",
            "session_id": "session_val_rec",
            "query": "What's the weather in Chicago on 2026-08-15?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Rain" in data["response"]


def test_pii_redaction(caplog):
    import logging

    logger = logging.getLogger("test_pii")

    with caplog.at_level(logging.INFO):
        logger.info("User email is test@example.com and phone is 555-555-0199.")
        logger.info(
            "Safe message.",
            extra={
                "intent": "Contact user at test@example.com",
                "outcome": "Called 555-555-0199.",
            },
        )

    log_text = caplog.text

    # Assert raw PII is NOT in logs
    assert "test@example.com" not in log_text
    assert "555-555-0199" not in log_text

    # Assert redacted placeholders are in logs
    assert "[REDACTED_EMAIL]" in log_text
    assert "[REDACTED_PHONE]" in log_text
