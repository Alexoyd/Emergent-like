import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Label } from './ui/label';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Switch } from './ui/switch';
import { 
  Cpu, 
  Zap, 
  RefreshCw, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Settings,
  Brain,
  Code,
  Search,
  DollarSign
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const LLMSettingsPanel = ({ projectId = null }) => {
  const [settings, setSettings] = useState(null);
  const [providers, setProviders] = useState({});
  const [models, setModels] = useState([]);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [testingProvider, setTestingProvider] = useState(null);

  // Role icons mapping
  const roleIcons = {
    planner: <Brain className="h-4 w-4" />,
    developer: <Code className="h-4 w-4" />,
    reviewer: <Search className="h-4 w-4" />,
    default: <Settings className="h-4 w-4" />
  };

  // Role labels
  const roleLabels = {
    planner: 'Planificateur',
    developer: 'Développeur',
    reviewer: 'Reviewer',
    default: 'Par défaut'
  };

  // Status badge styling
  const statusBadge = (status) => {
    const styles = {
      connected: { variant: 'default', icon: <CheckCircle className="h-3 w-3" />, label: 'Connecté' },
      disconnected: { variant: 'secondary', icon: <AlertTriangle className="h-3 w-3" />, label: 'Déconnecté' },
      unconfigured: { variant: 'outline', icon: <XCircle className="h-3 w-3" />, label: 'Non configuré' },
      error: { variant: 'destructive', icon: <XCircle className="h-3 w-3" />, label: 'Erreur' },
      disabled: { variant: 'secondary', icon: <XCircle className="h-3 w-3" />, label: 'Désactivé' }
    };
    const style = styles[status] || styles.unconfigured;
    return (
      <Badge variant={style.variant} className="flex items-center gap-1">
        {style.icon} {style.label}
      </Badge>
    );
  };

  // Load all data
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [settingsRes, providersRes, modelsRes, usageRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/llm/settings`, { params: { project_id: projectId } }),
        axios.get(`${BACKEND_URL}/api/llm/providers`),
        axios.get(`${BACKEND_URL}/api/llm/models`),
        axios.get(`${BACKEND_URL}/api/llm/usage`, { params: { period: 'day' } })
      ]);

      setSettings(settingsRes.data.settings);
      setProviders(providersRes.data.providers);
      setModels(modelsRes.data.models);
      setUsage(usageRes.data.usage);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Test provider connection
  const testProvider = async (providerId) => {
    setTestingProvider(providerId);
    try {
      const response = await axios.post(`${BACKEND_URL}/api/llm/providers/${providerId}/test`);
      // Refresh providers to get updated status
      const providersRes = await axios.get(`${BACKEND_URL}/api/llm/providers`);
      setProviders(providersRes.data.providers);
    } catch (err) {
      setError(`Test échoué pour ${providerId}: ${err.message}`);
    } finally {
      setTestingProvider(null);
    }
  };

  // Update role assignment
  const updateRoleAssignment = async (role, provider, modelId) => {
    setSaving(true);
    try {
      await axios.put(`${BACKEND_URL}/api/llm/role-assignments/${role}`, null, {
        params: {
          provider,
          model_id: modelId,
          project_id: projectId
        }
      });
      // Refresh settings
      const settingsRes = await axios.get(`${BACKEND_URL}/api/llm/settings`, {
        params: { project_id: projectId }
      });
      setSettings(settingsRes.data.settings);
    } catch (err) {
      setError(`Erreur de mise à jour: ${err.response?.data?.detail || err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Toggle model enabled/disabled
  const toggleModel = async (modelId, enabled) => {
    try {
      await axios.put(`${BACKEND_URL}/api/llm/models/${modelId}/enable`, null, {
        params: { enabled }
      });
      // Refresh models
      const modelsRes = await axios.get(`${BACKEND_URL}/api/llm/models`);
      setModels(modelsRes.data.models);
    } catch (err) {
      setError(`Erreur: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Reset settings
  const resetSettings = async () => {
    if (!window.confirm('Réinitialiser les paramètres LLM aux valeurs par défaut ?')) return;
    
    try {
      await axios.post(`${BACKEND_URL}/api/llm/settings/reset`, null, {
        params: { scope: projectId ? 'project' : 'global', project_id: projectId }
      });
      loadData();
    } catch (err) {
      setError(`Erreur: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Get models for a specific provider
  const getModelsForProvider = (providerId) => {
    return models.filter(m => m.provider === providerId && m.enabled);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Cpu className="h-6 w-6" />
            Paramètres LLM
          </h2>
          <p className="text-gray-500 text-sm">
            {projectId ? `Configuration pour le projet ${projectId}` : 'Configuration globale'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Actualiser
          </Button>
          <Button variant="outline" onClick={resetSettings}>
            Réinitialiser
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Provider Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries(providers).map(([id, provider]) => (
          <Card key={id} className={`${!provider.enabled ? 'opacity-60' : ''}`}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <CardTitle className="text-base font-semibold">{provider.name}</CardTitle>
                {statusBadge(provider.status)}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Activé</span>
                <Switch 
                  checked={provider.enabled} 
                  disabled={id === 'ollama'}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">Clé API</span>
                <Badge variant={provider.api_key_configured ? 'default' : 'secondary'}>
                  {provider.api_key_configured ? '✓ Configurée' : '✗ Manquante'}
                </Badge>
              </div>
              <div className="text-sm text-gray-500">
                {provider.models?.length || 0} modèle(s) disponible(s)
              </div>
              <Button 
                size="sm" 
                variant="outline" 
                className="w-full"
                onClick={() => testProvider(id)}
                disabled={testingProvider === id || !provider.enabled}
              >
                {testingProvider === id ? (
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Zap className="h-4 w-4 mr-2" />
                )}
                Tester la connexion
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Role Assignments */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Attribution des Modèles par Rôle
          </CardTitle>
          <CardDescription>
            Configurez quel modèle utiliser pour chaque type d'agent
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Object.entries(settings?.role_assignments || {}).map(([role, assignment]) => (
              <div key={role} className="space-y-3 p-4 border rounded-lg">
                <div className="flex items-center gap-2 font-semibold">
                  {roleIcons[role]}
                  {roleLabels[role] || role}
                </div>
                
                {/* Provider selection */}
                <div className="space-y-1">
                  <Label className="text-xs text-gray-500">Provider</Label>
                  <Select
                    value={assignment.provider}
                    onValueChange={(value) => updateRoleAssignment(role, value, assignment.model_id)}
                    disabled={saving}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(providers).filter(([_, p]) => p.enabled).map(([id, provider]) => (
                        <SelectItem key={id} value={id}>
                          <div className="flex items-center gap-2">
                            {provider.name}
                            {provider.status === 'connected' && <CheckCircle className="h-3 w-3 text-green-500" />}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Model selection */}
                <div className="space-y-1">
                  <Label className="text-xs text-gray-500">Modèle</Label>
                  <Select
                    value={assignment.model_id}
                    onValueChange={(value) => updateRoleAssignment(role, assignment.provider, value)}
                    disabled={saving}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {getModelsForProvider(assignment.provider).map((model) => (
                        <SelectItem key={model.id} value={model.model_id}>
                          <div className="flex flex-col">
                            <span>{model.label}</span>
                            {model.input_cost_per_1k > 0 && (
                              <span className="text-xs text-gray-500">
                                €{model.input_cost_per_1k}/1K in • €{model.output_cost_per_1k}/1K out
                              </span>
                            )}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Fallback info */}
                {assignment.fallback_provider && (
                  <div className="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                    Fallback: {providers[assignment.fallback_provider]?.name} → {assignment.fallback_model_id}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Usage Statistics */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5" />
              Utilisation (Aujourd'hui)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold">{usage.total_requests}</div>
                <div className="text-xs text-gray-500">Requêtes</div>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold">{usage.successful_requests}</div>
                <div className="text-xs text-gray-500">Succès</div>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold">{(usage.total_tokens / 1000).toFixed(1)}K</div>
                <div className="text-xs text-gray-500">Tokens</div>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <div className="text-2xl font-bold text-green-600">€{usage.total_cost_eur.toFixed(4)}</div>
                <div className="text-xs text-gray-500">Coût</div>
              </div>
            </div>

            {/* Usage by provider */}
            {Object.keys(usage.by_provider || {}).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold mb-2">Par Provider</h4>
                <div className="space-y-2">
                  {Object.entries(usage.by_provider).map(([provider, stats]) => (
                    <div key={provider} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                      <span className="font-medium">{providers[provider]?.name || provider}</span>
                      <div className="flex gap-4 text-sm text-gray-600">
                        <span>{stats.requests} req</span>
                        <span>{(stats.tokens / 1000).toFixed(1)}K tok</span>
                        <span className="text-green-600">€{stats.cost.toFixed(4)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Models List */}
      <Card>
        <CardHeader>
          <CardTitle>Modèles Disponibles</CardTitle>
          <CardDescription>Activez ou désactivez les modèles selon vos besoins</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {models.map((model) => (
              <div 
                key={model.id} 
                className={`flex items-center justify-between p-3 border rounded-lg ${!model.enabled ? 'opacity-50' : ''}`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{model.label}</span>
                    <Badge variant="outline" className="text-xs">
                      {providers[model.provider]?.name}
                    </Badge>
                  </div>
                  <div className="flex gap-2 mt-1">
                    {model.capabilities?.slice(0, 4).map((cap) => (
                      <Badge key={cap} variant="secondary" className="text-xs">
                        {cap}
                      </Badge>
                    ))}
                  </div>
                  {model.description && (
                    <p className="text-xs text-gray-500 mt-1">{model.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  {model.input_cost_per_1k > 0 && (
                    <span className="text-xs text-gray-500">
                      €{model.input_cost_per_1k}/1K
                    </span>
                  )}
                  <Switch 
                    checked={model.enabled} 
                    onCheckedChange={(checked) => toggleModel(model.id, checked)}
                  />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LLMSettingsPanel;
