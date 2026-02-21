# SalesPOC.AI

## Main project

- SalesPOC UI: https://github.com/csdmichael/SalesPOC.UI

Azure AI Foundry agent source code and deployment pipeline for the **Arrow Sales Agent** — the AI-powered chat component consumed by [SalesPOC.API](../SalesPOC.API).

## Overview

This repository manages the lifecycle of the Azure AI Foundry agent that answers natural language questions about sales data. It includes:

- **Agent definition** (`agent_config.yaml`) — model, system prompt, tools, and parameters
- **Deployment scripts** (`src/`) — Python scripts to create/update/delete the agent
- **Infrastructure** (`infra/`) — Terraform to provision Azure AI Services, Hub, and Project
- **CI/CD** (`.github/workflows/`) — GitHub Actions workflow to deploy the agent automatically

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  GitHub Actions (CI/CD)                                      │
│  ┌────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │ Checkout    │→ │ Deploy Agent  │→ │ Validate Deployment │ │
│  └────────────┘  └───────────────┘  └─────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │ Azure OIDC Auth
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Azure AI Foundry                                            │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────┐  │
│  │ AI Services   │  │ AI Hub        │  │ AI Project       │  │
│  │ (gpt-4o)     │  │               │  │ (001-ai-proj)    │  │
│  └──────────────┘  └───────────────┘  └──────┬───────────┘  │
│                                              │               │
│                                    ┌─────────▼─────────┐    │
│                                    │ arrow-sales-agent  │    │
│                                    └─────────┬─────────┘    │
└──────────────────────────────────────────────┼───────────────┘
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │ SalesPOC.API        │
                                    │ ChatController      │
                                    └─────────────────────┘
```

## Project Structure

```
SalesPOC.AI/
├── .github/
│   └── workflows/
│       └── deploy-agent.yml      # GitHub Actions deployment pipeline
├── infra/
│   ├── main.tf                   # Terraform: AI Services, Hub, Project
│   └── terraform.tfvars.example  # Terraform variables template
├── src/
│   ├── agent.py                  # Agent deploy/update/delete CLI
│   ├── config.py                 # Configuration loader (env + YAML)
│   └── validate.py               # Post-deployment validation
├── .env.example                  # Environment variables template
├── .gitignore
├── agent_config.yaml             # Agent definition (instructions, model, tools)
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Prerequisites

- Python 3.12+
- Azure CLI (`az login` for local development)
- Azure subscription with AI Foundry access
- Terraform 1.9+ (only for infrastructure provisioning)

## Quick Start (Local)

### 1. Setup environment

```bash
cd SalesPOC.AI
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Azure AI Foundry settings
```

### 3. Authenticate to Azure

```bash
az login
```

### 4. Deploy the agent

```bash
cd src
python agent.py deploy
```

### 5. Validate the agent

```bash
python validate.py
```

### Other commands

```bash
# Get agent info
python agent.py info

# Delete the agent
python agent.py delete

# Force recreate (delete + create)
python agent.py deploy --force-recreate

# Use custom config file
python agent.py deploy --config /path/to/custom_agent_config.yaml
```

## Agent Configuration

The agent is defined in [`agent_config.yaml`](agent_config.yaml):

| Field          | Description                                    |
|----------------|------------------------------------------------|
| `name`         | Agent name (must match `AzureAgent:AgentName` in SalesPOC.API) |
| `model`        | OpenAI model deployment name                   |
| `instructions` | System prompt with sales domain context         |
| `temperature`  | Response randomness (0.0 – 1.0)                |
| `top_p`        | Nucleus sampling threshold                      |
| `tools`        | Optional tools (Bing grounding, AI Search, etc.)|

### Modifying the Agent

1. Edit `agent_config.yaml` with the desired changes
2. Push to `main` — the GitHub Action will automatically update the agent
3. Or run locally: `python src/agent.py deploy`

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/deploy-agent.yml`) handles:

### Automatic Triggers
- Push to `main` branch when `agent_config.yaml`, `src/**`, or `requirements.txt` change

### Manual Triggers
- **workflow_dispatch** with optional `force_recreate` flag
- Infrastructure provisioning only runs on manual dispatch

### Pipeline Jobs

| Job       | Description                                          |
|-----------|------------------------------------------------------|
| `deploy`  | Install deps → Azure login → Deploy agent → Validate |
| `infra`   | Terraform init → plan → apply (manual trigger only)  |

### Required GitHub Secrets

| Secret                        | Description                                   |
|-------------------------------|-----------------------------------------------|
| `AZURE_CLIENT_ID`            | Service principal / app registration client ID |
| `AZURE_TENANT_ID`            | Azure AD tenant ID                             |
| `AZURE_SUBSCRIPTION_ID`      | Azure subscription ID                          |
| `AZURE_AI_PROJECT_ENDPOINT`  | AI Foundry project endpoint URL                |
| `AZURE_RESOURCE_GROUP`       | Resource group name                            |
| `AZURE_AI_ACCOUNT_NAME`      | AI Services account name                       |

### Required GitHub Variables

| Variable                  | Description              | Default  |
|---------------------------|--------------------------|----------|
| `AZURE_MODEL_DEPLOYMENT` | Model deployment name    | `gpt-4o` |

### Setting Up OIDC Authentication

1. Create an App Registration in Azure AD
2. Add federated credentials for your GitHub repository:
   - Organization: `<your-org>`
   - Repository: `SalesPOC.AI`
   - Entity type: `Branch` → `main`
3. Grant the service principal these roles on the AI Services resource:
   ```bash
   PRINCIPAL_ID="<app-registration-object-id>"
   SCOPE="/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ai-account>"
   
   az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
     --role "Azure AI Developer" --scope "$SCOPE" \
     --assignee-principal-type "ServicePrincipal"
   
   az role assignment create --assignee-object-id "$PRINCIPAL_ID" \
     --role "Cognitive Services OpenAI User" --scope "$SCOPE" \
     --assignee-principal-type "ServicePrincipal"
   ```

## Infrastructure

The `infra/` directory contains Terraform to provision:

- **Azure AI Services** (Cognitive Services account)
- **GPT-4o model deployment** (GlobalStandard SKU)
- **Azure AI Hub** (workspace)
- **Azure AI Project** (linked to hub)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

terraform init
terraform plan
terraform apply
```

## Relationship to SalesPOC.API

The API's `ChatController` connects to this agent via the Azure AI Projects SDK:

```
SalesPOC.API (appsettings.json)
  └── AzureAgent:Endpoint  → AI Foundry project endpoint
  └── AzureAgent:AgentName → "arrow-sales-agent" (must match agent_config.yaml)
```

Any changes to the agent's instructions or model in this repo are automatically deployed and immediately available to the API.

## License

[Specify your license here]
