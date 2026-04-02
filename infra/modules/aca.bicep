@description('Prefix used when generating resource names')
param namePrefix string

@description('Azure region for all resources')
param location string

@description('Unique token for resource name generation')
param resourceToken string

@description('Resource ID of the Log Analytics Workspace')
param logAnalyticsWorkspaceId string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('AI Foundry project endpoint')
param foundryProjectEndpoint string

@description('Resource ID of the AI Services account for RBAC assignment')
param aiServicesId string

@description('Name of the deployed AI model')
param modelDeploymentName string

@description('Project connection string for AI Foundry SDK')
param projectConnectionString string

@description('Tags to apply to all resources')
param tags object

var acrName = replace('cr${namePrefix}${resourceToken}', '-', '')
var acaEnvName = 'ae-${namePrefix}-${resourceToken}'
var acaAppName = 'ca-${namePrefix}-${resourceToken}'
var uamiName = 'id-${namePrefix}-${resourceToken}'

// Built-in role definition IDs
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var cognitiveServicesUserRoleId = 'a97b65f3-24c7-4388-baec-2e87135dc908'

// --- User-Assigned Managed Identity ---
// Created before the Container App so RBAC can be assigned first,
// breaking the circular dependency with ACR Pull.
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
  tags: tags
}

// --- Azure Container Registry ---
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
  }
}

// --- RBAC: ACR Pull for the managed identity (before Container App) ---
resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, uami.id, acrPullRoleId)
  scope: acr
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// --- RBAC: Cognitive Services User for the managed identity ---
// Uses Microsoft.CognitiveServices/* wildcard which covers OpenAI,
// AIServices/agents/write, and all Foundry data actions.
resource cognitiveServicesRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServicesId, uami.id, cognitiveServicesUserRoleId)
  scope: aiServicesResource
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesUserRoleId)
  }
}

// Reference the AI Services resource for scoped RBAC
resource aiServicesResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(aiServicesId, '/'))
}

// --- ACA Environment ---
resource acaEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: acaEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsWorkspaceId, '2023-09-01').customerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2023-09-01').primarySharedKey
      }
    }
  }
}

// --- Container App ---
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: acaAppName
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'bed-management-api'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'MODEL_DEPLOYMENT_NAME'
              value: modelDeploymentName
            }
            {
              name: 'PROJECT_CONNECTION_STRING'
              value: projectConnectionString
            }
            {
              name: 'APP_THEME'
              value: 'dark'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: uami.properties.clientId
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    acrPullAssignment
    cognitiveServicesRoleAssignment
  ]
}

// --- Outputs ---
@description('FQDN URL of the deployed Container App')
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'

@description('ACR login server hostname')
output acrLoginServer string = acr.properties.loginServer

@description('Name of the deployed Container App')
output appName string = containerApp.name

@description('Principal ID of the managed identity')
output managedIdentityPrincipalId string = uami.properties.principalId
