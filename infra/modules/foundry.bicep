@description('Prefix used when generating resource names')
param namePrefix string

@description('Azure region for all resources')
param location string

@description('Unique token for resource name generation')
param resourceToken string

@description('Array of model deployments. Each object must have: name (string), version (string), capacity (int). The deployment name will match the model name.')
param modelDeployments array

@description('Name of the primary model deployment (used as MODEL_DEPLOYMENT_NAME in app config)')
param primaryModelName string

@description('Tags to apply to all resources')
param tags object

@description('Resource ID of Log Analytics Workspace for diagnostics')
param logAnalyticsWorkspaceId string

@description('Application Insights connection string for agent tracing')
param appInsightsConnectionString string

@description('Application Insights resource ID for Foundry connection')
param appInsightsResourceId string

var aiServicesName = 'aif-${namePrefix}-${resourceToken}'
var aiProjectName = 'proj-${namePrefix}-${resourceToken}'

// --- Azure AI Services account (this IS the Foundry resource) ---
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: aiServicesName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    allowProjectManagement: true
  }
}

// --- Model Deployments (on the AI Services account) ---
// NOTE: Model availability varies by region. Verify with:
//   az cognitiveservices model list --location <region> -o table
@batchSize(1)
resource modelDeploy 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = [
  for model in modelDeployments: {
    parent: aiServices
    name: model.name
    sku: {
      name: 'GlobalStandard'
      capacity: model.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: model.name
        version: model.version
      }
    }
  }
]

// --- Foundry Project (child of the AI Services account) ---
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: aiProjectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
  dependsOn: [
    modelDeploy
  ]
}

// --- App Insights Connection for Agent Tracing in Foundry Portal ---
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = {
  parent: aiProject
  name: 'appinsights'
  properties: {
    category: 'AppInsights'
    target: appInsightsResourceId
    authType: 'ApiKey'
    credentials: {
      key: appInsightsConnectionString
    }
    metadata: {
      ConnectionString: appInsightsConnectionString
    }
  }
}

// --- Diagnostic Settings for AI Services ---
resource aiServicesDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${aiServicesName}-diag'
  scope: aiServices
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// --- Outputs ---
@description('Project endpoint for the AI Foundry SDK v2')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('Endpoint of the AI Services account')
output aiServicesEndpoint string = aiServices.properties.endpoint

@description('Name of the primary model deployment (for app config)')
output modelDeploymentName string = primaryModelName

@description('Names of all model deployments')
output allModelDeploymentNames array = [for (model, i) in modelDeployments: modelDeploy[i].name]

@description('Resource ID of the AI Services account (for RBAC)')
output aiServicesId string = aiServices.id

@description('Connection string for AIProjectClient')
output projectConnectionString string = '${aiServicesName}.services.ai.azure.com;${subscription().subscriptionId};${resourceGroup().name};${aiProjectName}'
