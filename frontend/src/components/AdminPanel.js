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
import { Trash2, Eye, GitBranch, Download, Upload } from 'lucide-react';

const AdminPanel = () => {
  const [stats, setStats] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [githubToken, setGithubToken] = useState('');
  const [repos, setRepos] = useState([]);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:3001';

  useEffect(() => {
    loadAdminData();
  }, []);

  const loadAdminData = async () => {
    try {
      setLoading(true);
      
      // Load admin stats
      const statsResponse = await axios.get(`${backendUrl}/api/admin/stats`);
      setStats(statsResponse.data);
      
      // Load projects
      const projectsResponse = await axios.get(`${backendUrl}/api/projects`);
      setProjects(projectsResponse.data.projects);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadGithubRepos = async () => {
    try {
      if (!githubToken) return;
      
      const response = await axios.get(`${backendUrl}/api/github/repositories`, {
        params: { access_token: githubToken }
      });
      setRepos(response.data.repositories);
    } catch (err) {
      setError('Erreur lors du chargement des repos GitHub');
    }
  };

  const cloneRepository = async (repoUrl) => {
    try {
      const response = await axios.post(`${backendUrl}/api/github/clone`, {
        repo_url: repoUrl,
        access_token: githubToken
      });
      
      alert(`Repository cloné avec succès: ${response.data.project_id}`);
      loadAdminData(); // Reload projects
    } catch (err) {
      setError('Erreur lors du clonage du repository');
    }
  };

  const deleteProject = async (projectId) => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer ce projet ?')) return;
    
    try {
      await axios.delete(`${backendUrl}/api/projects/${projectId}`);
      loadAdminData(); // Reload projects
    } catch (err) {
      setError('Erreur lors de la suppression du projet');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-gray-900">Admin Panel</h1>
        <Button onClick={loadAdminData} variant="outline">
          Actualiser
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">Vue d'ensemble</TabsTrigger>
          <TabsTrigger value="projects">Projets</TabsTrigger>
          <TabsTrigger value="github">GitHub</TabsTrigger>
          <TabsTrigger value="settings">Paramètres</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats?.run_stats?.status_distribution?.completed || 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  Runs terminés
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Coût Quotidien</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  €{stats?.daily_cost?.total_cost?.toFixed(2) || '0.00'}
                </div>
                <p className="text-xs text-muted-foreground">
                  Aujourd'hui
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Projets Actifs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.project_count || 0}</div>
                <p className="text-xs text-muted-foreground">
                  Total projets
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Budget Quotidien</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  €{stats?.settings?.default_daily_budget || 5}
                </div>
                <Progress 
                  value={(stats?.daily_cost?.total_cost || 0) / (stats?.settings?.default_daily_budget || 5) * 100} 
                  className="mt-2"
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Configuration Système</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex justify-between">
                <span>Tentatives Locales Max:</span>
                <Badge variant="secondary">{stats?.settings?.max_local_retries}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Étapes Max par Run:</span>
                <Badge variant="secondary">{stats?.settings?.max_steps_per_run}</Badge>
              </div>
              <div className="flex justify-between">
                <span>Auto-création Structures:</span>
                <Badge variant={stats?.settings?.auto_create_structures ? "default" : "secondary"}>
                  {stats?.settings?.auto_create_structures ? 'Activé' : 'Désactivé'}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Projects Tab */}
        <TabsContent value="projects" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Gestion des Projets</CardTitle>
              <CardDescription>
                Liste de tous les projets avec leurs détails et actions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {projects.map((project) => (
                  <div key={project.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex-1">
                      <h3 className="font-semibold">{project.name}</h3>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline">{project.stack}</Badge>
                        <Badge variant={project.status === 'completed' ? 'default' : 'secondary'}>
                          {project.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        Créé le {new Date(project.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        onClick={() => deleteProject(project.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                
                {projects.length === 0 && (
                  <p className="text-center text-gray-500 py-8">
                    Aucun projet trouvé
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* GitHub Tab */}
        <TabsContent value="github" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Intégration GitHub</CardTitle>
              <CardDescription>
                Connectez et gérez vos repositories GitHub
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input 
                  placeholder="Token d'accès GitHub"
                  type="password"
                  value={githubToken}
                  onChange={(e) => setGithubToken(e.target.value)}
                  className="flex-1"
                />
                <Button onClick={loadGithubRepos}>
                  <GitBranch className="h-4 w-4 mr-2" />
                  Charger Repos
                </Button>
              </div>

              {repos.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-semibold">Repositories Disponibles</h4>
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {repos.slice(0, 10).map((repo) => (
                      <div key={repo.id} className="flex items-center justify-between p-3 border rounded">
                        <div>
                          <h5 className="font-medium">{repo.name}</h5>
                          <p className="text-sm text-gray-500">{repo.description}</p>
                          <div className="flex gap-1 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {repo.language}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              ⭐ {repo.stargazers_count}
                            </Badge>
                          </div>
                        </div>
                        <Button 
                          size="sm"
                          onClick={() => cloneRepository(repo.clone_url)}
                        >
                          <Download className="h-4 w-4 mr-1" />
                          Cloner
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Paramètres Système</CardTitle>
              <CardDescription>
                Configuration avancée du système
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="max-retries">Tentatives Locales Max</Label>
                  <Input 
                    id="max-retries"
                    type="number" 
                    defaultValue={stats?.settings?.max_local_retries || 3}
                    disabled
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Configuré via .env (MAX_LOCAL_RETRIES)
                  </p>
                </div>

                <div>
                  <Label htmlFor="daily-budget">Budget Quotidien (€)</Label>
                  <Input 
                    id="daily-budget"
                    type="number" 
                    step="0.1"
                    defaultValue={stats?.settings?.default_daily_budget || 5.0}
                    disabled
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Configuré via .env (DEFAULT_DAILY_BUDGET_EUR)
                  </p>
                </div>

                <div>
                  <Label htmlFor="max-steps">Étapes Max par Run</Label>
                  <Input 
                    id="max-steps"
                    type="number" 
                    defaultValue={stats?.settings?.max_steps_per_run || 20}
                    disabled
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Configuré via .env (MAX_STEPS_PER_RUN)
                  </p>
                </div>
              </div>

              <Alert>
                <AlertDescription>
                  Pour modifier ces paramètres, éditez le fichier .env du backend et redémarrez le service.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdminPanel;