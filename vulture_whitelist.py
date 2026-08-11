# vulture_whitelist.py
# This file is used by Vulture to ignore false positives of unused code.

import app.logger
import app.main
import app.patches
import tests.test_agent
import tests.test_evaluation
import tests.test_secrets
import google.adk.workflow._llm_agent_wrapper as wrapper

# Whitelist FastAPI endpoints
app.main.health_check
app.main.query_endpoint

# Whitelist log formatter
app.logger.JsonFormatter.format

# Whitelist wrapper monkey-patch attributes
wrapper.prepare_llm_agent_context
wrapper.prepare_llm_agent_input
wrapper.run_llm_agent_as_node

# Whitelist patches attributes & variables
app.patches.fixed_prepare_llm_agent_input
app.patches.fixed_prepare_llm_agent_context

# Whitelist pytest fixtures
tests.test_agent.clean_database
tests.test_secrets.clean_env

# Whitelist simulator interface methods
tests.test_evaluation._find_unanswered_confirmation
tests.test_evaluation.HITLUserSimulator.get_next_user_message
tests.test_evaluation.HITLUserSimulator.get_simulation_evaluator
tests.test_evaluation.CustomUserSimulatorProvider.provide

# Whitelist write-only attributes/variables by reading them from a dummy object
class Dummy:
    def __init__(self):
        self.role = None
        self.include_contents = None
        self.target_name = None
        self.return_value = None
        self.side_effect = None

d = Dummy()
d.role
d.include_contents
d.target_name
d.return_value
d.side_effect
