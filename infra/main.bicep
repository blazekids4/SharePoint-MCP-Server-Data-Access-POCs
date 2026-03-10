// Main Bicep template for the Vantiva MCP Server on Azure Container Apps
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (used to generate resource names)')
param environmentName string

@minLength(1)
@description('Primary Azure region for all resources')
param location string

@description('SharePoint tenant ID for Graph API auth')
@secure()
param sharepointTenantId string = ''

@description('SharePoint client ID for Graph API auth')
@secure()
param sharepointClientId string = ''

@description('SharePoint client secret for Graph API auth')
@secure()
param sharepointClientSecret string = ''

@description('SharePoint host name (e.g. yourtenant.sharepoint.com)')
param sharepointHost string = ''

// Generate a unique token for resource naming
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

// Resource group
resource rg 'Microsoft.Resources/resourceGroups@2024-11-01' = {
  name: 'rg-${environmentName}'
  location: location
}

// Container Apps environment + app
module containerApp 'modules/containerapp.bicep' = {
  name: 'containerapp'
  scope: rg
  params: {
    location: location
    resourceToken: resourceToken
    sharepointTenantId: sharepointTenantId
    sharepointClientId: sharepointClientId
    sharepointClientSecret: sharepointClientSecret
    sharepointHost: sharepointHost
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerApp.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerApp.outputs.registryName
output AZURE_CONTAINER_APP_NAME string = containerApp.outputs.containerAppName
output AZURE_CONTAINER_APP_URL string = containerApp.outputs.containerAppUrl
output SERVICE_API_ENDPOINTS array = ['${containerApp.outputs.containerAppUrl}/mcp']
