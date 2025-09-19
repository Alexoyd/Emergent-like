import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Progress } from './ui/progress';
import { Alert, AlertDescription } from './ui/alert';
import { ScrollArea } from './ui/scroll-area';
import { 
  TrendingUp, 
  Settings, 
  Users, 
  Terminal, 
  Eye,
  EyeOff,
  RefreshCw,
  Database,
  DollarSign,
  Activity,
  Clock,
  Filter
} from 'lucide-react';

const AdminGlobal = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState('stats');
  const [globalStats, setGlobalStats] = useState(null);
  const [globalLogs, setGlobalLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showApiKeys, setShowApiKeys] = useState(false);
  const [logFilter, setLogFilter] = useState('');
  const [selectedProjectId, setSelectedProjectId] = useState('');

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:3001';

  useEffect(() => {
    if (isOpen) {
      loadGlobalData();
    }
  }, [isOpen]);

  const loadGlobalData = async () => {
    try {
      setLoading(true);
      
      // Load global admin stats
      const statsResponse = await axios.get(`${backendUrl}/api/admin/global-stats`);
      setGlobalStats(statsResponse.data);
      
      // Load global logs
      const logsResponse = await axios.get(`${backendUrl}/api/admin/global-logs`);
      setGlobalLogs(logsResponse.data.logs || []);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearCache = async () => {
    try {
      await axios.post(`${backendUrl}/api/admin/cache/clear`);
      loadGlobalData(); // Reload to show updated cache stats
    } catch (err) {
      setError('Erreur lors du nettoyage du cache');
    }
  };

  const formatCurrency = (amount) => {
    return `€${(amount || 0).toFixed(4)}`;
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const filteredLogs = globalLogs.filter(log => {
    const matchesFilter = !logFilter || log.content.toLowerCase().includes(logFilter.toLowerCase());
    const matchesProject = !selectedProjectId || log.project_id === selectedProjectId;
    return matchesFilter && matchesProject;
  });

  const uniqueProjectIds = [...new Set(globalLogs.map(log => log.project_id).filter(Boolean))];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl max-h-[90vh] w-full m-4 overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center">
            <Settings className="w-6 h-6 mr-2 text-blue-600" />
            Administration Globale
          </h2>
          <Button onClick={onClose} variant="outline" size="sm">
            ✕ Fermer
          </Button>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="p-6">
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="stats" className="flex items-center">
                  <TrendingUp className="w-4 h-4 mr-2" />
                  Statistiques
                </TabsTrigger>
                <TabsTrigger value="system" className="flex items-center">
                  <Database className="w-4 h-4 mr-2" />
                  Système
                </TabsTrigger>
                <TabsTrigger value="account" className="flex items-center">
                  <Users className="w-4 h-4 mr-2" />
                  Compte
                </TabsTrigger>
                <TabsTrigger value="logs" className="flex items-center">
                  <Terminal className="w-4 h-4 mr-2" />
                  Logs Globaux
                </TabsTrigger>
              </TabsList>

              {/* Statistiques Tab */}
              <TabsContent value="stats" className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Total Projets</CardTitle>
                      <Activity className="w-4 h-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {globalStats?.total_projects || 0}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Tous statuts confondus
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
                      <Clock className="w-4 h-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {globalStats?.total_runs || 0}
                      </div>
                      <p className="text-xs text-green-600">
                        {globalStats?.completed_runs || 0} terminés
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Coûts Cumulés</CardTitle>
                      <DollarSign className="w-4 h-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">
                        {formatCurrency(globalStats?.total_costs)}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Toutes périodes
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Économies Cache</CardTitle>
                      <TrendingUp className="w-4 h-4 text-green-600" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-green-600">
                        {formatCurrency(globalStats?.cache_savings?.total_saved)}
                      </div>
                      <p className="text-xs text-green-600">
                        {globalStats?.cache_savings?.percentage || 0}% d'économies
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Cache Statistics */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      Statistiques du Cache Prompt
                      <Button onClick={clearCache} variant="outline" size="sm">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Vider Cache
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">
                          {globalStats?.cache_stats?.total_entries || 0}
                        </div>
                        <p className="text-sm text-gray-600">Entrées en cache</p>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">
                          {globalStats?.cache_stats?.hit_rate || 0}%
                        </div>
                        <p className="text-sm text-gray-600">Taux de succès</p>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">
                          {globalStats?.cache_stats?.total_usage || 0}
                        </div>
                        <p className="text-sm text-gray-600">Utilisations totales</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Budget Progress */}
                <Card>
                  <CardHeader>
                    <CardTitle>Budget Quotidien Global</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Utilisé aujourd'hui</span>
                        <span>{formatCurrency(globalStats?.daily_usage?.today)}</span>
                      </div>
                      <Progress 
                        value={(globalStats?.daily_usage?.today || 0) / (globalStats?.daily_budget || 1) * 100} 
                        className="h-2"
                      />
                      <div className="flex justify-between text-xs text-gray-600">
                        <span>Budget: {formatCurrency(globalStats?.daily_budget)}</span>
                        <span>Restant: {formatCurrency((globalStats?.daily_budget || 0) - (globalStats?.daily_usage?.today || 0))}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Système Tab */}
              <TabsContent value="system" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      Variables d'Environnement
                      <Button 
                        onClick={() => setShowApiKeys(!showApiKeys)} 
                        variant="outline" 
                        size="sm"
                      >
                        {showApiKeys ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        {showApiKeys ? 'Masquer' : 'Afficher'} Clés
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label className="text-sm font-medium">OpenAI API Key</Label>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant={globalStats?.env_status?.openai_key ? "default" : "destructive"}>
                            {globalStats?.env_status?.openai_key ? "Configurée" : "Manquante"}
                          </Badge>
                          {showApiKeys && globalStats?.env_status?.openai_key && (
                            <span className="text-xs text-gray-500 font-mono">
                              sk-...{globalStats?.env_status?.openai_key_suffix}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <Label className="text-sm font-medium">Anthropic API Key</Label>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant={globalStats?.env_status?.anthropic_key ? "default" : "destructive"}>
                            {globalStats?.env_status?.anthropic_key ? "Configurée" : "Manquante"}
                          </Badge>
                          {showApiKeys && globalStats?.env_status?.anthropic_key && (
                            <span className="text-xs text-gray-500 font-mono">
                              sk-ant-...{globalStats?.env_status?.anthropic_key_suffix}
                            </span>
                          )}
                        </div>
                      </div>

                      <div>
                        <Label className="text-sm font-medium">GitHub Token</Label>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant={globalStats?.env_status?.github_token ? "default" : "secondary"}>
                            {globalStats?.env_status?.github_token ? "Configuré" : "Optionnel"}
                          </Badge>
                        </div>
                      </div>

                      <div>
                        <Label className="text-sm font-medium">MongoDB URL</Label>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant={globalStats?.env_status?.mongo_url ? "default" : "destructive"}>
                            {globalStats?.env_status?.mongo_url ? "Configurée" : "Manquante"}
                          </Badge>
                        </div>
                      </div>
                    </div>

                    <div className="border-t pt-4 mt-4">
                      <h4 className="font-medium mb-3">Paramètres Système</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <Label className="text-sm">Budget Quotidien</Label>
                          <Input 
                            value={`€${globalStats?.system_config?.daily_budget || 5}`}
                            disabled
                            className="mt-1"
                          />
                          <p className="text-xs text-gray-500 mt-1">DEFAULT_DAILY_BUDGET_EUR</p>
                        </div>

                        <div>
                          <Label className="text-sm">Tentatives Locales Max</Label>
                          <Input 
                            value={globalStats?.system_config?.max_local_retries || 3}
                            disabled
                            className="mt-1"
                          />
                          <p className="text-xs text-gray-500 mt-1">MAX_LOCAL_RETRIES</p>
                        </div>

                        <div>
                          <Label className="text-sm">Étapes Max par Run</Label>
                          <Input 
                            value={globalStats?.system_config?.max_steps || 20}
                            disabled
                            className="mt-1"
                          />
                          <p className="text-xs text-gray-500 mt-1">MAX_STEPS_PER_RUN</p>
                        </div>

                        <div>
                          <Label className="text-sm">Auto-création Structures</Label>
                          <Input 
                            value={globalStats?.system_config?.auto_create ? "Activé" : "Désactivé"}
                            disabled
                            className="mt-1"
                          />
                          <p className="text-xs text-gray-500 mt-1">AUTO_CREATE_STRUCTURES</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Compte Tab */}
              <TabsContent value="account" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Informations du Compte Administrateur</CardTitle>
                    <CardDescription>
                      Gestion du compte administrateur principal
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="admin-username">Nom d'utilisateur</Label>
                        <Input 
                          id="admin-username"
                          defaultValue="administrator"
                          disabled
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          Configuré via les variables d'environnement
                        </p>
                      </div>

                      <div>
                        <Label htmlFor="admin-email">Email</Label>
                        <Input 
                          id="admin-email"
                          type="email"
                          placeholder="admin@example.com"
                          disabled
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          À configurer via ADMIN_EMAIL
                        </p>
                      </div>
                    </div>

                    <Alert>
                      <AlertDescription>
                        La gestion complète des utilisateurs sera disponible dans une prochaine version.
                        Pour l'instant, l'authentification est gérée via les variables d'environnement.
                      </AlertDescription>
                    </Alert>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Logs Globaux Tab */}
              <TabsContent value="logs" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      Logs Globaux du Système
                      <Button onClick={loadGlobalData} variant="outline" size="sm">
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Actualiser
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {/* Filtres */}
                    <div className="flex gap-4 mb-4">
                      <div className="flex-1">
                        <Label htmlFor="log-filter" className="text-sm">Filtrer les logs</Label>
                        <Input 
                          id="log-filter"
                          placeholder="Rechercher dans les logs..."
                          value={logFilter}
                          onChange={(e) => setLogFilter(e.target.value)}
                        />
                      </div>
                      <div>
                        <Label htmlFor="project-filter" className="text-sm">Project ID</Label>
                        <select 
                          id="project-filter"
                          value={selectedProjectId}
                          onChange={(e) => setSelectedProjectId(e.target.value)}
                          className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500"
                        >
                          <option value="">Tous les projets</option>
                          {uniqueProjectIds.map(id => (
                            <option key={id} value={id}>{id}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Logs */}
                    <ScrollArea className="h-96">
                      <div className="space-y-2">
                        {filteredLogs.length > 0 ? (
                          filteredLogs.map((log, index) => (
                            <div key={index} className="p-3 border rounded-lg bg-gray-50">
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center space-x-2">
                                  <Badge variant="outline" className="text-xs">
                                    {log.type || 'info'}
                                  </Badge>
                                  {log.project_id && (
                                    <Badge variant="secondary" className="text-xs">
                                      {log.project_id}
                                    </Badge>
                                  )}
                                </div>
                                <span className="text-xs text-gray-500">
                                  {formatDate(log.timestamp)}
                                </span>
                              </div>
                              <div className="text-sm text-gray-900 font-mono">
                                {log.content}
                              </div>
                            </div>
                          ))
                        ) : (
                          <div className="text-center py-8 text-gray-500">
                            Aucun log trouvé avec les filtres actuels
                          </div>
                        )}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminGlobal;