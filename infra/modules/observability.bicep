@description('Prefix used when generating resource names')
param namePrefix string

@description('Azure region for all resources')
param location string

@description('Unique token for resource name generation')
param resourceToken string

@description('Tags to apply to all resources')
param tags object

var logAnalyticsName = 'la-${namePrefix}-${resourceToken}'
var appInsightsName = 'in-${namePrefix}-${resourceToken}'

// --- Log Analytics Workspace ---
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// --- Application Insights ---
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// --- Outputs ---
@description('Resource ID of the Log Analytics Workspace')
output logAnalyticsWorkspaceId string = logAnalytics.id

@description('Connection string for Application Insights')
output appInsightsConnectionString string = appInsights.properties.ConnectionString

@description('Instrumentation key for Application Insights')
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
