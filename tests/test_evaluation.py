# tests/test_evaluation.py
import asyncio
from typing import Optional
from unittest.mock import patch, MagicMock
import pytest
from google.genai import types
from google.adk.evaluation.simulation.user_simulator import UserSimulator, NextUserMessage, Status, BaseUserSimulatorConfig
from google.adk.evaluation.eval_set import EvalSet
from google.adk.evaluation.eval_case import EvalCase, SessionInput, Invocation
from google.adk.evaluation.in_memory_eval_sets_manager import InMemoryEvalSetsManager
from google.adk.evaluation.local_eval_service import LocalEvalService
from google.adk.evaluation.base_eval_service import InferenceRequest, InferenceConfig, InferenceStatus
from google.adk.events.event import Event
from app.agents import coordinator

def _find_unanswered_confirmation(events: list[Event]) -> Optional[types.FunctionCall]:
    # Find the latest confirmation request
    confirmation_call = None
    for e in reversed(events):
        for fc in e.get_function_calls():
            if fc.name == "adk_request_confirmation":
                confirmation_call = fc
                break
        if confirmation_call:
            break
            
    if not confirmation_call:
        return None
        
    # Check if we already responded to this specific confirmation call
    for e in reversed(events):
        if e.author != "user":
            continue
        for fr in e.get_function_responses():
            if fr.id == confirmation_call.id:
                return None # Already responded
                
    return confirmation_call

class HITLUserSimulator(UserSimulator):
    def __init__(self, queries: list):
        super().__init__(BaseUserSimulatorConfig(), BaseUserSimulatorConfig)
        self.queries = queries
        self.query_idx = 0

    async def get_next_user_message(self, events: list[Event]) -> NextUserMessage:
        unanswered_call = _find_unanswered_confirmation(events)
        if unanswered_call:
            confirmation_response = types.FunctionResponse(
                id=unanswered_call.id,
                name="adk_request_confirmation",
                response={"confirmed": True},
            )
            user_content = types.Content(
                role="user",
                parts=[types.Part(function_response=confirmation_response)]
            )
            return NextUserMessage(
                status=Status.SUCCESS,
                user_message=user_content
            )

        if self.query_idx >= len(self.queries):
            return NextUserMessage(status=Status.STOP_SIGNAL_DETECTED)

        query = self.queries[self.query_idx]
        self.query_idx += 1
        
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=query)]
        )
        return NextUserMessage(
            status=Status.SUCCESS,
            user_message=user_content
        )

    def get_simulation_evaluator(self):
        return None

class CustomUserSimulatorProvider:
    def __init__(self, queries: list):
        self.queries = queries
    def provide(self, eval_case: EvalCase) -> UserSimulator:
        return HITLUserSimulator(self.queries)

class EvalBookingScenarioMock:
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
                    if p.function_response and p.function_response.name == "travel_worker":
                        has_worker_response = True
            
            if not has_worker_response:
                # Coordinator first turn: delegates to travel_worker
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="travel_worker",
                                            args={"request": "Book Gino's East at 7 PM."}
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
            else:
                # Coordinator second turn: wraps up
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part.from_text(
                                        text="I have successfully booked Gino's East at 7 PM for you."
                                    )
                                ]
                            )
                        )
                    ]
                )
                
        elif is_worker:
            has_booking_response = False
            has_booking_call = False
            
            for c in contents:
                for p in c.parts:
                    if p.function_call and p.function_call.name == "book_reservation":
                        has_booking_call = True
                    if p.function_response and p.function_response.name == "book_reservation":
                        has_booking_response = True
            
            if not has_booking_call:
                # Worker first turn: calls book_reservation (will pause for HITL)
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="book_reservation",
                                            args={"restaurant_name": "Gino's East", "time": "7 PM"}
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
            elif has_booking_response:
                # Worker second turn: finished after resume
                response = types.GenerateContentResponse(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="model",
                                parts=[
                                    types.Part(
                                        function_call=types.FunctionCall(
                                            name="finish_task",
                                            args={"result": "Successfully booked a table at Gino's East for 7 PM."}
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
        
        if response is None:
            response = types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model",
                            parts=[types.Part.from_text(text="Fallback")]
                        )
                    )
                ]
            )
        return response

@pytest.mark.asyncio
@patch("google.genai.Client")
async def test_automated_evaluation_suite(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    
    mock_mock = EvalBookingScenarioMock()
    mock_client.aio.models.generate_content.side_effect = mock_mock
    mock_client.aio.models.generate_content_stream.side_effect = mock_mock

    # Setup eval case
    dummy_invocation = Invocation(
        user_content=types.Content(parts=[types.Part.from_text(text="dummy")])
    )
    eval_case = EvalCase(
        eval_id="booking_flow_eval",
        conversation=[dummy_invocation],
        session_input=SessionInput(app_name="mini-concierge", user_id="eval_user")
    )
    
    eval_sets_manager = InMemoryEvalSetsManager()
    eval_sets_manager.create_eval_set(app_name="mini-concierge", eval_set_id="golden_set")
    eval_sets_manager.add_eval_case(app_name="mini-concierge", eval_set_id="golden_set", eval_case=eval_case)
    
    provider = CustomUserSimulatorProvider(queries=[
        "Book Gino's East at 7 PM."
    ])
    
    eval_service = LocalEvalService(
        root_agent=coordinator,
        eval_sets_manager=eval_sets_manager,
        user_simulator_provider=provider
    )
    
    inference_request = InferenceRequest(
        app_name="mini-concierge",
        eval_set_id="golden_set",
        inference_config=InferenceConfig()
    )
    
    results = []
    async for res in eval_service.perform_inference(inference_request):
        results.append(res)
        
    assert len(results) == 1
    res = results[0]
    assert res.status == InferenceStatus.SUCCESS
    assert len(res.inferences) == 1
    
    # Verify the final response contains the expected booking confirmation
    final_inv = res.inferences[0]
    assert final_inv.final_response is not None
    assert "booked" in final_inv.final_response.parts[0].text.lower()

