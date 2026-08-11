# app/patches.py
import logging
from typing import Any, AsyncGenerator, Optional
from contextlib import aclosing

import google.adk.workflow._llm_agent_wrapper as wrapper
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.flows.llm_flows.contents import _is_request_confirmation_event
from google.adk.utils.content_utils import to_user_content

from google.adk.workflow._llm_agent_wrapper import (
    _safe_canonical_tools_dict,
    _find_unresolved_task_delegations,
    _dispatch_task_fc,
    _synthesize_task_fr_event,
    _extract_task_delegation_fcs,
    _extract_finish_task_fc,
    _find_finish_task_tool,
    _is_finish_task_success_fr,
    process_llm_agent_output,
)

logger = logging.getLogger(__name__)


def fixed_prepare_llm_agent_context(agent: Any, ctx: Context) -> Context:
    """Prepares the context for running an LlmAgent as a node."""
    print(
        f"fixed_prepare_llm_agent_context CALLED for agent {agent.name if hasattr(agent, 'name') else 'unknown'}"
    )
    if not hasattr(ctx, "_invocation_context") or ctx._invocation_context is None:
        return ctx

    ic = ctx._invocation_context.model_copy()
    ic._event_queue = ctx._invocation_context._event_queue
    ic.isolation_scope = ctx.isolation_scope
    agent_ctx = Context(
        invocation_context=ic,
        node_path=ctx.node_path,
        run_id=ctx.run_id,
        resume_inputs=ctx.resume_inputs,
    )
    agent_ctx.isolation_scope = ctx.isolation_scope

    # WORKAROUND: Commented out to prevent stale update markers in DB session
    # ic.session = ic.session.model_copy(deep=False)
    return agent_ctx


async def fixed_prepare_llm_agent_input(
    agent: Any, ctx: Context, node_input: Any
) -> None:
    """Prepares the input for running LlmAgent as a node."""
    print(
        f"fixed_prepare_llm_agent_input CALLED for agent {agent.name if hasattr(agent, 'name') else 'unknown'}"
    )
    if node_input is None or agent.mode != "single_turn":
        return

    branch = ctx._invocation_context.branch
    if branch:
        # WORKAROUND: Skip appending if we already have the user input for this branch.
        # This prevents duplicates on resume.
        exists = any(
            e.author == "user"
            and e.branch == branch
            and not _is_request_confirmation_event(e)
            for e in ctx.session.events
        )
        if exists:
            logger.info(
                "User input already exists for branch %s, skipping append", branch
            )
            return

    agent_input = to_user_content(node_input)
    user_event = Event(author="user", content=agent_input)
    if user_event.content is not None:
        user_event.content.role = "user"
    iso = getattr(ctx, "isolation_scope", None)
    if iso:
        user_event.isolation_scope = iso
    if branch:
        user_event.branch = branch

    # WORKAROUND: Persist the event to DB immediately so it is available on resume
    await ctx._invocation_context.session_service.append_event(
        session=ctx.session, event=user_event
    )


async def fixed_run_llm_agent_as_node(
    agent: Any,
    *,
    ctx: Context,
    node_input: Any,
) -> AsyncGenerator[Any, None]:
    """Runs an LlmAgent as a workflow node (with patched async prepare_input)."""
    print(
        f"fixed_run_llm_agent_as_node CALLED for agent {agent.name if hasattr(agent, 'name') else 'unknown'}"
    )
    # As a node in a workflow, agent is by default single_turn.

    if agent.mode is None:
        agent.mode = "single_turn"

    if agent.mode not in ("task", "single_turn", "chat"):
        raise ValueError(
            f"LlmAgent as node only supports task, single_turn, and chat mode,"
            f" but agent '{agent.name}' has mode='{agent.mode}'."
        )

    include_contents_explicit = "include_contents" in agent.model_fields_set
    if agent.mode == "single_turn" and not include_contents_explicit:
        agent.include_contents = "none"

    agent_ctx = fixed_prepare_llm_agent_context(agent, ctx)
    # WORKAROUND: Await the patched async function
    await fixed_prepare_llm_agent_input(agent, agent_ctx, node_input)

    ic = agent_ctx.get_invocation_context()
    update = {"agent": agent}
    _agent_iso = getattr(agent_ctx, "isolation_scope", None)
    if agent.mode in ("task", "single_turn") and _agent_iso:
        update["isolation_scope"] = _agent_iso
    if agent.mode == "task" and node_input is not None:
        update["user_content"] = to_user_content(node_input)
    ic = ic.model_copy(update=update)

    from google.adk.agents.live_request_queue import LiveRequestQueue

    is_live = (
        isinstance(getattr(ic, "live_request_queue", None), LiveRequestQueue)
        and agent.mode != "single_turn"
    )

    if agent.mode == "single_turn":
        async with aclosing(agent.run_async(ic)) as run_iter:
            async for event in run_iter:
                process_llm_agent_output(agent, ctx, event)
                yield event
        return

    if agent.mode == "chat":
        tools_dict = _safe_canonical_tools_dict(agent)
        pending = _find_unresolved_task_delegations(
            ctx.session,
            owner=agent.name,
            tools_dict=tools_dict,
        )
        for fc in pending:
            output = await _dispatch_task_fc(agent, fc, ctx)
            yield _synthesize_task_fr_event(fc, output)

        while True:
            had_task_fc = False
            transferred = False
            run_method = agent.run_live(ic) if is_live else agent.run_async(ic)
            async with aclosing(run_method) as run_iter:
                async for event in run_iter:
                    yield event
                    task_fcs = _extract_task_delegation_fcs(event, tools_dict)
                    for fc in task_fcs:
                        output = await _dispatch_task_fc(agent, fc, ctx)
                        yield _synthesize_task_fr_event(fc, output)
                    if task_fcs:
                        had_task_fc = True
                        break  # close this run_iter; outer loop re-enters
                    if event.actions.transfer_to_agent:
                        target_name = event.actions.transfer_to_agent

                        from google.adk.agents.llm_agent import LlmAgent

                        if (
                            isinstance(agent, LlmAgent)
                            and ctx._invocation_context.is_resumable
                        ):
                            ctx._invocation_context.set_agent_state(
                                agent.name, end_of_agent=True
                            )
                            yield agent._create_agent_state_event(
                                ctx._invocation_context
                            )
                        transferred = True
                        break
            if not had_task_fc or transferred:
                return

    finish_tool = _find_finish_task_tool(agent)
    pending_fc_args: Optional[dict] = None
    run_method = agent.run_live(ic) if is_live else agent.run_async(ic)
    async with aclosing(run_method) as run_iter:
        async for event in run_iter:
            finish_fc = _extract_finish_task_fc(event)
            if finish_fc is not None:
                pending_fc_args = dict(finish_fc.args or {})
                yield event
                continue

            if pending_fc_args is not None and _is_finish_task_success_fr(event):
                wrapper_key = getattr(finish_tool, "_wrapper_key", None)
                if wrapper_key and wrapper_key in pending_fc_args:
                    event.output = pending_fc_args[wrapper_key]
                else:
                    event.output = pending_fc_args
                if getattr(agent, "output_key", None) and event.output is not None:
                    ctx.actions.state_delta[agent.output_key] = event.output
                yield event
                return

            yield event


# Apply patches
def apply_patches():
    print("PATCHES APPLIED")
    logger.info("Applying ADK workflow patches")
    wrapper.prepare_llm_agent_context = fixed_prepare_llm_agent_context
    wrapper.prepare_llm_agent_input = fixed_prepare_llm_agent_input
    wrapper.run_llm_agent_as_node = fixed_run_llm_agent_as_node
