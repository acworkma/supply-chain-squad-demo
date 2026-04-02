# Azure Deployment

How to deploy the demo to Azure using Azure Developer CLI (azd), Azure AI Foundry, and Azure Container Apps.

## Prerequisites

| Tool | Install |
|------|---------|
| Azure CLI | [Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) — `az --version` |
| Azure Developer CLI (azd) | [Install](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd) — `azd version` |
| Azure subscription | With permission to create AI Services, Container Apps, and Container Registry |
| Docker | Required for building the container image |

## One-Command Deployment

```bash
az login
azd auth login
azd up
```

That's it. `azd up` does three things:

1. **Provisions infrastructure** — creates all Azure resources via Bicep templates
2. **Builds AI agents** — runs `scripts/build_agents.py` to create the 6 Foundry agents
3. **Deploys the app** — builds the Docker image, pushes to Container Registry, deploys to Container Apps

You'll be prompted for:
- **Environment name** — a short name for this deployment (e.g., `supply-closet-demo`)
- **Azure location** — the region (e.g., `eastus2`)
- **Azure subscription** — which subscription to use

## What Gets Created

### Resource Groups

| Resource | Naming | Purpose |
|----------|--------|---------|
| Resource Group | `rg-{env-name}` | Contains all resources |

### Azure AI Foundry

| Resource | Prefix | Purpose |
|----------|--------|---------|
| AI Services | `ai-` | Cognitive services account (hosts model deployments) |
| AI Hub | `ah-` | Foundry hub (groups projects) |
| AI Project | `ap-` | Foundry project (agents live here) |
| Model Deployment | — | GPT-5.2 deployment used by all 5 agents |

### Container Apps

| Resource | Prefix | Purpose |
|----------|--------|---------|
| Container Registry | `cr` | Stores the Docker image |
| Container App Environment | `ae-` | Managed environment for the app |
| Container App | `ca-` | The running application |

### Observability

| Resource | Prefix | Purpose |
|----------|--------|---------|
| Log Analytics Workspace | `la-` | Centralized logging |
| Application Insights | `in-` | Application performance monitoring |

## Environment Variables (Set Automatically)

When deployed via `azd up`, these are configured automatically on the Container App:

| Variable | Source |
|----------|--------|
| `PROJECT_ENDPOINT` | AI Foundry project endpoint (from Bicep output) |
| `MODEL_DEPLOYMENT_NAME` | `gpt-5.2` |

## Post-Provision Hook

After infrastructure is provisioned, `azd` runs the post-provision hook defined in `azure.yaml`:

```bash
pip install azure-identity "azure-ai-projects>=2.0.0"
python scripts/build_agents.py
```

This script:
1. Connects to the AI Foundry project using `DefaultAzureCredential`
2. Creates (or versions) all 6 named agents with their system prompts and tool schemas via `agents.create_version()`
3. Agents are invoked by name at runtime — no ID mapping needed

## Smoke Testing

After deployment, verify the app is running:

```bash
# Basic check (endpoints only)
./scripts/smoke_test.sh https://your-app.azurecontainerapps.io

# Full check (seeds state + runs routine-restock scenario)
./scripts/smoke_test.sh --full https://your-app.azurecontainerapps.io
```

## Authentication

The deployment uses **Entra ID (keyless) authentication** everywhere:

- **Container App → AI Foundry**: Managed Identity with RBAC role assignments (configured in `aca.bicep`)
- **`build_agents.py`**: Uses `DefaultAzureCredential` — works with your `az login` session locally, Managed Identity in CI
- **No API keys** are stored or passed as environment variables

## Updating the Deployment

After making code changes:

```bash
azd deploy    # Rebuild and redeploy (no infra changes)
```

To update infrastructure (Bicep changes):

```bash
azd provision   # Re-run Bicep, then deploy
```

To tear everything down:

```bash
azd down        # Deletes all Azure resources
```

## Infrastructure Details

The Bicep templates live in `infra/`:

```
infra/
├── main.bicep                 # Top-level orchestration
└── modules/
    ├── foundry.bicep          # AI Services + Hub + Project + model deployment
    ├── aca.bicep              # Container Registry + Environment + App + RBAC
    └── observability.bicep    # Log Analytics + App Insights
```

`main.bicep` accepts parameters for location, environment name, and model deployment name, then wires the modules together with outputs flowing between them (e.g., AI Foundry endpoint → Container App environment variable).

## CI/CD

The repo includes a GitHub Actions workflow at `.github/workflows/deploy.yml` that deploys on push to `main`:

1. Checks out code
2. Installs `azd`
3. Authenticates via OIDC (federated credentials)
4. Runs `azd provision` + `azd deploy`

Required GitHub secrets:
- `AZURE_CLIENT_ID` — Service principal / federated identity client ID
- `AZURE_TENANT_ID` — Azure AD tenant
- `AZURE_SUBSCRIPTION_ID` — Target subscription
- `AZURE_ENV_NAME` — azd environment name
- `AZURE_LOCATION` — Azure region

## Troubleshooting

**`azd up` fails at provisioning:**
- Check your subscription has quota for AI Services in the selected region
- Some regions don't support all AI Foundry features — try `eastus2` or `westus3`

**`build_agents.py` fails:**
- Ensure `az login` is current: `az account show`
- Verify the AI Foundry project was created: check the Azure Portal

**App deploys but shows simulated mode:**
- Check Container App environment variables in the Portal — `PROJECT_ENDPOINT` should be set
- Verify `build_agents.py` ran successfully during post-provision

**Container App not starting:**
- Check logs: `az containerapp logs show -n {app-name} -g {rg-name}`
- Verify the Docker image was pushed to the Container Registry
