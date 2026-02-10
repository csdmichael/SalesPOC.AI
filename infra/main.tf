# Terraform configuration to provision Azure AI Foundry resources
# for the Arrow Sales Agent

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 2.0"
    }
  }
  required_version = ">= 1.0"
}

provider "azurerm" {
  features {}
}

provider "azapi" {}

# ──────────────────────────────────────────────
# Variables
# ──────────────────────────────────────────────

variable "resource_group_name" {
  description = "Name of the existing resource group"
  type        = string
  default     = "ai-myaacoub"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "East US"
}

variable "ai_account_name" {
  description = "Azure AI Services / Cognitive Services account name"
  type        = string
  default     = "001-ai-poc"
}

variable "ai_project_name" {
  description = "Azure AI Foundry project name"
  type        = string
  default     = "001-ai-proj"
}

variable "model_deployment_name" {
  description = "Name of the model deployment (e.g. gpt-4o)"
  type        = string
  default     = "gpt-4o"
}

variable "model_name" {
  description = "Name of the OpenAI model to deploy"
  type        = string
  default     = "gpt-4o"
}

variable "model_version" {
  description = "Version of the OpenAI model"
  type        = string
  default     = "2024-11-20"
}

variable "agent_name" {
  description = "Name of the AI agent"
  type        = string
  default     = "arrow-sales-agent"
}

# ──────────────────────────────────────────────
# Data – reference existing resource group
# ──────────────────────────────────────────────

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

# ──────────────────────────────────────────────
# Azure AI Services account (Cognitive Services)
# ──────────────────────────────────────────────

resource "azurerm_cognitive_account" "ai_services" {
  name                  = var.ai_account_name
  location              = data.azurerm_resource_group.main.location
  resource_group_name   = data.azurerm_resource_group.main.name
  kind                  = "AIServices"
  sku_name              = "S0"
  custom_subdomain_name = var.ai_account_name

  identity {
    type = "SystemAssigned"
  }

  tags = {
    environment = "production"
    application = "SalesPOC.AI"
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

# ──────────────────────────────────────────────
# Model deployment (GPT-4o)
# ──────────────────────────────────────────────

resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = var.model_deployment_name
  cognitive_account_id = azurerm_cognitive_account.ai_services.id

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = 10
  }
}

# ──────────────────────────────────────────────
# Azure AI Hub / Project (via AzAPI)
# ──────────────────────────────────────────────

resource "azapi_resource" "ai_hub" {
  type      = "Microsoft.MachineLearningServices/workspaces@2024-10-01"
  name      = "${var.ai_account_name}-hub"
  location  = data.azurerm_resource_group.main.location
  parent_id = data.azurerm_resource_group.main.id

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "Hub"
    properties = {
      friendlyName = "Sales POC AI Hub"
      description  = "Azure AI Hub for Arrow Sales Agent"
    }
  }

  tags = {
    environment = "production"
    application = "SalesPOC.AI"
  }
}

resource "azapi_resource" "ai_project" {
  type      = "Microsoft.MachineLearningServices/workspaces@2024-10-01"
  name      = var.ai_project_name
  location  = data.azurerm_resource_group.main.location
  parent_id = data.azurerm_resource_group.main.id

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "Project"
    properties = {
      friendlyName = "Sales POC AI Project"
      description  = "Azure AI Foundry project for Arrow Sales Agent"
      hubResourceId = azapi_resource.ai_hub.id
    }
  }

  tags = {
    environment = "production"
    application = "SalesPOC.AI"
  }
}

# ──────────────────────────────────────────────
# Outputs
# ──────────────────────────────────────────────

output "ai_services_endpoint" {
  description = "Azure AI Services endpoint"
  value       = azurerm_cognitive_account.ai_services.endpoint
}

output "ai_services_id" {
  description = "Azure AI Services resource ID"
  value       = azurerm_cognitive_account.ai_services.id
}

output "ai_project_id" {
  description = "Azure AI Foundry project resource ID"
  value       = azapi_resource.ai_project.id
}

output "project_endpoint" {
  description = "Azure AI Foundry project endpoint for the agent SDK"
  value       = "https://${var.ai_account_name}.services.ai.azure.com/api/projects/${var.ai_project_name}"
}

output "agent_name" {
  description = "The configured agent name"
  value       = var.agent_name
}
