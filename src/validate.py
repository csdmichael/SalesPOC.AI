"""
Validation module — verifies agent deployment and connectivity.
Used by CI/CD pipelines after deployment to confirm the agent is working.
"""

from __future__ import annotations

import json
import sys

from azure.ai.projects import AIProjectClient
from azure.ai.projects.openai import ProjectResponsesClient
from azure.identity import DefaultAzureCredential

from config import AgentDefinition, AzureConfig


def validate_agent(config: AzureConfig, agent_def: AgentDefinition) -> bool:
    """
    Validate that the agent exists, is reachable, and responds to a test prompt.
    Returns True if validation passes.
    """
    credential = DefaultAzureCredential(
        exclude_visual_studio_credential=True,
        exclude_visual_studio_code_credential=True,
        exclude_azure_developer_cli_credential=True,
        exclude_interactive_browser_credential=True,
        exclude_shared_token_cache_credential=True,
        tenant_id=config.tenant_id or None,
    )
    client = AIProjectClient(
        endpoint=config.project_endpoint,
        credential=credential,
    )

    print(f"Validating agent '{agent_def.name}'...")

    # Step 1: Check agent exists
    try:
        agent_record = client.agents.get_agent(agent_def.name)
        print(f"  [PASS] Agent found: id={agent_record.id}, model={agent_record.model}")
    except Exception as e:
        print(f"  [FAIL] Agent not found: {e}")
        return False

    # Step 2: Send a test prompt
    try:
        response_client = client.openai.get_project_responses_client_for_agent(agent_record)
        response = response_client.create_response("Hello, are you operational?")
        output = response.get_output_text()
        if output and len(output) > 0:
            print(f"  [PASS] Agent responded: {output[:80]}...")
        else:
            print("  [FAIL] Agent returned empty response.")
            return False
    except Exception as e:
        print(f"  [FAIL] Agent communication error: {e}")
        return False

    print("Validation passed!")
    return True


def main():
    config = AzureConfig.from_env()
    config.validate()

    agent_def = AgentDefinition.from_yaml()

    success = validate_agent(config, agent_def)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
