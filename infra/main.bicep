@description('Name of the Azure Developer CLI environment')
@minLength(1)
@maxLength(64)
param environmentName string

@description('Primary location for all resources')
param location string = resourceGroup().location

@description('Name of the AI model to deploy')
param modelName string = 'gpt-4.1'

@description('Array of model deployments: each object has name (string), version (string), capacity (int)')
param modelDeployments array = [
  { name: 'gpt-5.2', version: '2025-12-11', capacity: 100 }
]

var resourceToken = uniqueString(resourceGroup().id)
var tags = {
  environment: environmentName
  project: 'bed-management-demo'
}

// --- Observability ---
module observability 'modules/observability.bicep' = {
  name: 'observability-${resourceToken}'
  params: {
    namePrefix: environmentName
    location: location
    resourceToken: resourceToken
    tags: tags
  }
}

// --- AI Foundry ---
module foundry 'modules/foundry.bicep' = {
  name: 'foundry-${resourceToken}'
  params: {
    namePrefix: environmentName
    location: location
    resourceToken: resourceToken
    modelDeployments: modelDeployments
    primaryModelName: modelName
    tags: tags
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
  }
}

// --- Azure Container Apps ---
module aca 'modules/aca.bicep' = {
  name: 'aca-${resourceToken}'
  params: {
    namePrefix: environmentName
    location: location
    resourceToken: resourceToken
    logAnalyticsWorkspaceId: observability.outputs.logAnalyticsWorkspaceId
    appInsightsConnectionString: observability.outputs.appInsightsConnectionString
    foundryProjectEndpoint: foundry.outputs.projectEndpoint
    aiServicesId: foundry.outputs.aiServicesId
    modelDeploymentName: foundry.outputs.modelDeploymentName
    projectConnectionString: foundry.outputs.projectConnectionString
    tags: tags
  }
}

// --- Outputs ---
@description('The URL of the deployed Container App')
output acaEndpointUrl string = aca.outputs.appUrl

@description('The ACR login server hostname')
output acrLoginServer string = aca.outputs.acrLoginServer

@description('ACR endpoint for azd container image push')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = aca.outputs.acrLoginServer

@description('The AI Foundry project endpoint (agents endpoint for SDK v2)')
output PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint

@description('The name of the deployed AI model')
output MODEL_DEPLOYMENT_NAME string = foundry.outputs.modelDeploymentName

@description('All deployed model names (for eval harness / multi-model comparison)')
output ALL_MODEL_DEPLOYMENT_NAMES array = foundry.outputs.allModelDeploymentNames

@description('Project connection string for build_agents.py post-provision hook')
output PROJECT_CONNECTION_STRING string = foundry.outputs.projectConnectionString

@description('The name of the deployed Container App')
output appName string = aca.outputs.appName
