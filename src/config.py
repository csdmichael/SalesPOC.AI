"""
Configuration module for the Azure AI Foundry agent deployment.
Loads settings from environment variables and agent_config.yaml.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Load .env file if present (for local development)
load_dotenv()

CONFIG_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AzureConfig:
    """Azure AI Foundry connection settings."""

    project_endpoint: str = ""
    subscription_id: str = ""
    resource_group: str = ""
    ai_account_name: str = ""
    tenant_id: str = ""
    model_deployment: str = "gpt-4o"

    @classmethod
    def from_env(cls) -> "AzureConfig":
        return cls(
            project_endpoint=os.environ.get("AZURE_AI_PROJECT_ENDPOINT", ""),
            subscription_id=os.environ.get("AZURE_SUBSCRIPTION_ID", ""),
            resource_group=os.environ.get("AZURE_RESOURCE_GROUP", ""),
            ai_account_name=os.environ.get("AZURE_AI_ACCOUNT_NAME", ""),
            tenant_id=os.environ.get("AZURE_TENANT_ID", ""),
            model_deployment=os.environ.get("AZURE_MODEL_DEPLOYMENT", "gpt-4o"),
        )

    def validate(self) -> None:
        """Raise if required values are missing."""
        required = {
            "AZURE_AI_PROJECT_ENDPOINT": self.project_endpoint,
            "AZURE_SUBSCRIPTION_ID": self.subscription_id,
            "AZURE_RESOURCE_GROUP": self.resource_group,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )


@dataclass
class AgentDefinition:
    """Parsed agent definition from agent_config.yaml."""

    name: str = "arrow-sales-agent"
    model: str = "gpt-4o"
    instructions: str = ""
    temperature: float = 0.3
    top_p: float = 0.95
    tools: list = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path | None = None) -> "AgentDefinition":
        yaml_path = path or (CONFIG_DIR / "agent_config.yaml")
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        agent = data.get("agent", {})
        return cls(
            name=agent.get("name", "arrow-sales-agent"),
            model=agent.get("model", "gpt-4o"),
            instructions=agent.get("instructions", ""),
            temperature=agent.get("temperature", 0.3),
            top_p=agent.get("top_p", 0.95),
            tools=agent.get("tools", []),
        )
