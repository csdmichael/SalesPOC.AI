"""
Deal-Strategy Agent — Deployment, Management, and Chat

This module provides functions to create, manage, and interact with the
Deal-Strategy Agent in Azure AI Foundry.

Usage:
    # Deploy (create or update) the agent
    python src/deal_strategy_agent.py deploy

    # Chat with the agent interactively
    python src/deal_strategy_agent.py chat

    # Get agent info
    python src/deal_strategy_agent.py info

    # Delete the agent
    python src/deal_strategy_agent.py delete
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from config import AzureConfig

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

CONFIG_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "deal_strategy_config.yaml"


@dataclass
class DealStrategyAgentDefinition:
    """Parsed agent definition from deal_strategy_config.yaml."""

    name: str = "Deal-Strategy"
    model: str = "gpt-4o"
    instructions: str = ""
    temperature: float = 0.4
    top_p: float = 0.95
    tools: list = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path | None = None) -> "DealStrategyAgentDefinition":
        yaml_path = path or DEFAULT_CONFIG_PATH
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        agent = data.get("agent", {})
        return cls(
            name=agent.get("name", "Deal-Strategy"),
            model=agent.get("model", "gpt-4o"),
            instructions=agent.get("instructions", ""),
            temperature=agent.get("temperature", 0.4),
            top_p=agent.get("top_p", 0.95),
            tools=agent.get("tools", []),
        )


# ──────────────────────────────────────────────
# Client Helpers
# ──────────────────────────────────────────────


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
            sdk_tools.append({
                "type": "bing_grounding",
                "bing_grounding": {
                    "connection_id": tool.get("connection_name", ""),
                },
            })
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
        for agent in client.agents.list_agents():
            if agent.name == agent_name:
                return agent.id
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# Deploy
# ──────────────────────────────────────────────


def deploy_agent(
    config: AzureConfig,
    agent_def: DealStrategyAgentDefinition,
    *,
    force_recreate: bool = False,
) -> dict:
    """
    Deploy (create or update) the Deal-Strategy agent in Azure AI Foundry.
    Returns a dict with agent metadata.
    """
    client = get_project_client(config)
    existing_id = find_existing_agent(client, agent_def.name)
    tool_defs = _build_tool_definitions(agent_def.tools)

    if existing_id and not force_recreate:
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
    print(f"\nAgent {action} successfully!")
    print(json.dumps(result, indent=2))
    return result


# ──────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────


def delete_agent(config: AzureConfig, agent_name: str) -> bool:
    """Delete the Deal-Strategy agent by name. Returns True if deleted."""
    client = get_project_client(config)
    agent_id = find_existing_agent(client, agent_name)
    if not agent_id:
        print(f"Agent '{agent_name}' not found.")
        return False
    client.agents.delete_agent(agent_id)
    print(f"Agent '{agent_name}' (id={agent_id}) deleted.")
    return True


# ──────────────────────────────────────────────
# Info
# ──────────────────────────────────────────────


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
        "instructions": (
            agent.instructions[:200] + "..."
            if agent.instructions and len(agent.instructions) > 200
            else agent.instructions
        ),
        "tools": [t.get("type") for t in (agent.tools or [])],
        "created_at": str(agent.created_at),
    }
    print(json.dumps(info, indent=2))
    return info


# ──────────────────────────────────────────────
# Chat  (interactive conversation with the agent)
# ──────────────────────────────────────────────


def chat_with_agent(config: AzureConfig, agent_name: str) -> None:
    """
    Start an interactive chat session with the Deal-Strategy agent.
    Uses the Agents SDK thread/run model.
    """
    client = get_project_client(config)
    agent_id = find_existing_agent(client, agent_name)
    if not agent_id:
        print(f"Agent '{agent_name}' not found. Deploy it first with: python src/deal_strategy_agent.py deploy")
        return

    agent = client.agents.get_agent(agent_id)
    print(f"\n{'='*60}")
    print(f"  Deal-Strategy Agent  (model: {agent.model})")
    print(f"  Type 'quit' or 'exit' to end the session.")
    print(f"{'='*60}\n")

    # Create a conversation thread
    thread = client.agents.create_thread()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Session ended.")
            break

        # Add user message to thread
        client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=user_input,
        )

        # Create a run and poll until completion
        run = client.agents.create_run(
            thread_id=thread.id,
            agent_id=agent.id,
        )

        # Poll for completion
        while run.status in ("queued", "in_progress"):
            time.sleep(1)
            run = client.agents.get_run(thread_id=thread.id, run_id=run.id)

        if run.status == "completed":
            # Retrieve the latest assistant message
            messages = client.agents.list_messages(thread_id=thread.id)
            for msg in messages:
                if msg.role == "assistant":
                    # Get text content from the message
                    for content_part in msg.content:
                        if hasattr(content_part, "text"):
                            print(f"\nAgent: {content_part.text.value}\n")
                    break
        elif run.status == "failed":
            print(f"\n[Error] Run failed: {run.last_error}\n")
        else:
            print(f"\n[Warning] Unexpected run status: {run.status}\n")


# ──────────────────────────────────────────────
# Single-query mode (non-interactive)
# ──────────────────────────────────────────────


def ask_agent(config: AzureConfig, agent_name: str, question: str) -> str | None:
    """
    Send a single question to the Deal-Strategy agent and return the response.
    Useful for programmatic integration.
    """
    client = get_project_client(config)
    agent_id = find_existing_agent(client, agent_name)
    if not agent_id:
        print(f"Agent '{agent_name}' not found.")
        return None

    agent = client.agents.get_agent(agent_id)

    # Create thread, message, and run
    thread = client.agents.create_thread()
    client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content=question,
    )
    run = client.agents.create_run(
        thread_id=thread.id,
        agent_id=agent.id,
    )

    # Poll for completion
    while run.status in ("queued", "in_progress"):
        time.sleep(1)
        run = client.agents.get_run(thread_id=thread.id, run_id=run.id)

    if run.status == "completed":
        messages = client.agents.list_messages(thread_id=thread.id)
        for msg in messages:
            if msg.role == "assistant":
                for content_part in msg.content:
                    if hasattr(content_part, "text"):
                        return content_part.text.value
    else:
        print(f"Run ended with status: {run.status}")
        if run.last_error:
            print(f"Error: {run.last_error}")

    # Clean up thread
    try:
        client.agents.delete_thread(thread.id)
    except Exception:
        pass

    return None


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Manage the Deal-Strategy Agent in Azure AI Foundry"
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
        help="Path to deal_strategy_config.yaml",
    )

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete the agent")
    delete_parser.add_argument("--name", default=None, help="Agent name to delete")

    # info
    info_parser = subparsers.add_parser("info", help="Get agent information")
    info_parser.add_argument("--name", default=None, help="Agent name to query")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Interactive chat with the agent")
    chat_parser.add_argument("--name", default=None, help="Agent name to chat with")

    # ask (single question)
    ask_parser = subparsers.add_parser("ask", help="Ask the agent a single question")
    ask_parser.add_argument("question", type=str, help="Question to ask")
    ask_parser.add_argument("--name", default=None, help="Agent name")

    args = parser.parse_args()

    # Load configs
    azure_config = AzureConfig.from_env()
    azure_config.validate()

    agent_def = DealStrategyAgentDefinition.from_yaml(
        args.config if hasattr(args, "config") and args.config else None
    )

    if args.command == "deploy":
        deploy_agent(azure_config, agent_def, force_recreate=args.force_recreate)

    elif args.command == "delete":
        name = args.name or agent_def.name
        delete_agent(azure_config, name)

    elif args.command == "info":
        name = args.name or agent_def.name
        get_agent_info(azure_config, name)

    elif args.command == "chat":
        name = args.name or agent_def.name
        chat_with_agent(azure_config, name)

    elif args.command == "ask":
        name = args.name or agent_def.name
        answer = ask_agent(azure_config, name, args.question)
        if answer:
            print(f"\n{answer}")


if __name__ == "__main__":
    main()
