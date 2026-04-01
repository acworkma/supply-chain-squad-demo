using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'scmd')
param location = readEnvironmentVariable('AZURE_LOCATION', 'eastus2')
param modelName = 'gpt-4.1'

// Model deployments for eval harness — multi-model comparison.
// NOTE: Model availability varies by region. Verify versions with:
//   az cognitiveservices model list --location <region> -o table
param modelDeployments = [
  { name: 'gpt-5.2',    version: '2025-12-11', capacity: 100 }
  { name: 'gpt-4.1',    version: '2025-04-14', capacity: 100 }
  { name: 'gpt-5-mini', version: '2025-08-07', capacity: 100 }
]
