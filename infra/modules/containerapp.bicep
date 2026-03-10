// Azure Container Apps environment and app for the Vantiva MCP Server
param location string
param resourceToken string

@secure()
param sharepointTenantId string
@secure()
param sharepointClientId string
@secure()
param sharepointClientSecret string
param sharepointHost string

// Log Analytics workspace for Container Apps environment
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${resourceToken}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Container Apps environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${resourceToken}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Container Registry for the app image
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'cr${resourceToken}'
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'vantiva-mcp-${resourceToken}'
  location: location
  tags: {
    'azd-service-name': 'api'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      secrets: [
        { name: 'sp-tenant-id', value: sharepointTenantId }
        { name: 'sp-client-id', value: sharepointClientId }
        { name: 'sp-client-secret', value: sharepointClientSecret }
        { name: 'registry-password', value: containerRegistry.listCredentials().passwords[0].value }
      ]
      registries: [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'registry-password'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'vantiva-mcp-server'
          // azd will replace this image reference during deployment
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'MCP_TRANSPORT', value: 'streamable-http' }
            { name: 'PORT', value: '8080' }
            { name: 'SHAREPOINT_TENANT_ID', secretRef: 'sp-tenant-id' }
            { name: 'SHAREPOINT_CLIENT_ID', secretRef: 'sp-client-id' }
            { name: 'SHAREPOINT_CLIENT_SECRET', secretRef: 'sp-client-secret' }
            { name: 'SHAREPOINT_HOST', value: sharepointHost }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output registryLoginServer string = containerRegistry.properties.loginServer
output registryName string = containerRegistry.name
output containerAppName string = containerApp.name
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
