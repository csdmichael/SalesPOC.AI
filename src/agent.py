"""
Azure AI Foundry Agent - Deployment and Management

This module provides functions to create, update, and manage the
Arrow Sales Agent in Azure AI Foundry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from config import AgentDefinition, AzureConfig


def get_project_client(config: AzureConfig) -> AIProjectClient:
    """Create an authenticated AIProjectClient."""
    credential = DefaultAzureCredential(
        exclude_visual_studio_credential=True,
        exclude_visual_studio_code_credential=True,
        exclude_azure_developer_cli_credential=True,
        exclude_interactive_browser_credential=True,
        exclude_shared_token_cache_credential=True,
        tenant_id=config.tenant_id or None,
    )
    return AIProjectClient(
        endpoint=config.project_endpoint,
        credential=credential,
    )


def _build_tool_definitions(tools: list) -> list[dict]:
    """Convert YAML tool specs into SDK-ready tool definitions."""
    sdk_tools = []
    for tool in tools:
        tool_type = tool.get("type", "")
        if tool_type == "bing_grounding":
            sdk_tools.append({"type": "bing_grounding", "bing_grounding": {"connection_id": tool.get("connection_name", "")}})
        elif tool_type == "azure_ai_search":
            sdk_tools.append({
                "type": "azure_ai_search",
                "azure_ai_search": {
                    "index_name": tool.get("index_name", ""),
                    "connection_id": tool.get("connection_name", ""),
                },
            })
        elif tool_type == "code_interpreter":
            sdk_tools.append({"type": "code_interpreter"})
        elif tool_type == "file_search":
            sdk_tools.append({"type": "file_search"})
    return sdk_tools


def find_existing_agent(client: AIProjectClient, agent_name: str) -> str | None:
    """Return the agent ID if an agent with the given name already exists."""
    try:
        agents = client.agents.list_agents()
        for agent in agents.data:
            if agent.name == agent_name:
                return agent.id
    except Exception:
        pass
    return None


def deploy_agent(
    config: AzureConfig,
    agent_def: AgentDefinition,
    *,
    force_recreate: bool = False,
) -> dict:
    """
    Deploy (create or update) the AI agent in Azure AI Foundry.

    Returns a dict with agent metadata.
    """
    client = get_project_client(config)

    existing_id = find_existing_agent(client, agent_def.name)

    tool_defs = _build_tool_definitions(agent_def.tools)

    if existing_id and not force_recreate:
        # Update the existing agent
        print(f"Updating existing agent '{agent_def.name}' (id={existing_id})...")
        agent = client.agents.update_agent(
            assistant_id=existing_id,
            model=agent_def.model,
            name=agent_def.name,
            instructions=agent_def.instructions,
            temperature=agent_def.temperature,
            top_p=agent_def.top_p,
            tools=tool_defs if tool_defs else None,
        )
        action = "updated"
    else:
        if existing_id and force_recreate:
            print(f"Deleting existing agent '{agent_def.name}' (id={existing_id})...")
            client.agents.delete_agent(existing_id)

        print(f"Creating new agent '{agent_def.name}'...")
        agent = client.agents.create_agent(
            model=agent_def.model,
            name=agent_def.name,
            instructions=agent_def.instructions,
            temperature=agent_def.temperature,
            top_p=agent_def.top_p,
            tools=tool_defs if tool_defs else None,
        )
        action = "created"

    result = {
        "action": action,
        "agent_id": agent.id,
        "agent_name": agent.name,
        "model": agent.model,
    }

    print(f"Agent {action} successfully!")
    print(json.dumps(result, indent=2))
    return result


def delete_agent(config: AzureConfig, agent_name: str) -> bool:
    """Delete an agent by name. Returns True if deleted."""
    client = get_project_client(config)
    agent_id = find_existing_agent(client, agent_name)
    if not agent_id:
        print(f"Agent '{agent_name}' not found.")
        return False
    client.agents.delete_agent(agent_id)
    print(f"Agent '{agent_name}' (id={agent_id}) deleted.")
    return True


def get_agent_info(config: AzureConfig, agent_name: str) -> dict | None:
    """Retrieve agent details by name."""
    client = get_project_client(config)
    agent_id = find_existing_agent(client, agent_name)
    if not agent_id:
        print(f"Agent '{agent_name}' not found.")
        return None
    agent = client.agents.get_agent(agent_id)
    info = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "model": agent.model,
        "instructions": agent.instructions[:100] + "..." if len(agent.instructions) > 100 else agent.instructions,
        "created_at": str(agent.created_at),
    }
    print(json.dumps(info, indent=2))
    return info


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Arrow Sales Agent in Azure AI Foundry"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # deploy
    deploy_parser = subparsers.add_parser("deploy", help="Create or update the agent")
    deploy_parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Delete and recreate the agent instead of updating",
    )
    deploy_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to agent_config.yaml",
    )

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete the agent")
    delete_parser.add_argument("--name", default=None, help="Agent name to delete")

    # info
    info_parser = subparsers.add_parser("info", help="Get agent information")
    info_parser.add_argument("--name", default=None, help="Agent name to query")

    args = parser.parse_args()

    azure_config = AzureConfig.from_env()
    azure_config.validate()

    agent_def = AgentDefinition.from_yaml(args.config if hasattr(args, "config") and args.config else None)

    if args.command == "deploy":
        deploy_agent(azure_config, agent_def, force_recreate=args.force_recreate)
    elif args.command == "delete":
        name = args.name or agent_def.name
        delete_agent(azure_config, name)
    elif args.command == "info":
        name = args.name or agent_def.name
        get_agent_info(azure_config, name)


if __name__ == "__main__":
    main()
