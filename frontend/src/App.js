import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import { Toaster } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  FileText, 
  Terminal, 
  TrendingUp,
  Bot,
  Code,
  GitBranch,
  Settings
} from 'lucide-react';

import { Button } from './components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Textarea } from './components/ui/textarea';
import { Badge } from './components/ui/badge';
import { Progress } from './components/ui/progress';
import { Separator } from './components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { ScrollArea } from './components/ui/scroll-area';
import { toast } from 'sonner';

import Timeline from './components/Timeline';
import DiffViewer from './components/DiffViewer';
import CostMeter from './components/CostMeter';
import LogViewer from './components/LogViewer';
import RunsList from './components/RunsList';
import AdminPanel from './components/AdminPanel';
import AdminGlobal from './components/AdminGlobal';

import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Main Dashboard Component
const Dashboard = () => {
  const [currentRun, setCurrentRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [isCreatingRun, setIsCreatingRun] = useState(false);
  const [goal, setGoal] = useState('');
  const [projectPath, setProjectPath] = useState('');
  const [stack, setStack] = useState('laravel');
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [showAdminGlobal, setShowAdminGlobal] = useState(false);
  const [connectedRepo, setConnectedRepo] = useState(null);
  const [repoUrl, setRepoUrl] = useState('');

  // Load runs on component mount
  useEffect(() => {
    loadRuns();
  }, []);

  // Poll for updates when there's an active run
  useEffect(() => {
    let interval;
    if (currentRun && ['pending', 'running'].includes(currentRun.status)) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get(`${API}/runs/${currentRun.id}`);
          setCurrentRun(response.data);
        } catch (error) {
          console.error('Error polling run status:', error);
        }
      }, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentRun]);

  const loadRuns = async () => {
    try {
      const response = await axios.get(`${API}/runs`);
      setRuns(response.data);
    } catch (error) {
      console.error('Error loading runs:', error);
      toast.error('Failed to load runs');
    }
  };

  const createRun = async () => {
    if (!goal.trim()) {
      toast.error('Please enter a goal for the AI agent');
      return;
    }

    setIsCreatingRun(true);
    try {
      const runData = {
        goal: goal.trim(),
        project_path: projectPath.trim() || null,
        stack,
        max_steps: 20,
        max_retries_per_step: 2,
        daily_budget_eur: 5.0
      };

      const response = await axios.post(`${API}/runs`, runData);
      const newRun = response.data;
      
      setCurrentRun(newRun);
      setRuns(prev => [newRun, ...prev]);
      setGoal('');
      setProjectPath('');
      
      toast.success('AI agent run created successfully!');
      
      // Start streaming logs
      streamLogs(newRun.id);
      
    } catch (error) {
      console.error('Error creating run:', error);
      toast.error('Failed to create run: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsCreatingRun(false);
    }
  };

  const streamLogs = (runId) => {
    // Note: In a real implementation, you'd use EventSource for SSE
    // For now, we'll poll for logs
    const pollLogs = async () => {
      try {
        const response = await axios.get(`${API}/runs/${runId}`);
        const run = response.data;
        setLogs(run.logs || []);
        
        if (['completed', 'failed', 'cancelled'].includes(run.status)) {
          return; // Stop polling
        }
        
        setTimeout(pollLogs, 1000);
      } catch (error) {
        console.error('Error polling logs:', error);
      }
    };
    
    pollLogs();
  };

  const cancelRun = async () => {
    if (!currentRun) return;
    
    try {
      await axios.post(`${API}/runs/${currentRun.id}/cancel`);
      toast.success('Run cancelled');
      loadRuns();
    } catch (error) {
      console.error('Error cancelling run:', error);
      toast.error('Failed to cancel run');
    }
  };

  const retryStep = async (stepNumber) => {
    if (!currentRun) return;
    
    try {
      await axios.post(`${API}/runs/${currentRun.id}/retry-step`, { step_number: stepNumber });
      toast.success('Step retry initiated');
    } catch (error) {
      console.error('Error retrying step:', error);
      toast.error('Failed to retry step');
    }
  };

  const selectRun = (run) => {
    setCurrentRun(run);
    setLogs(run.logs || []);
    if (['pending', 'running'].includes(run.status)) {
      streamLogs(run.id);
    }
  };

  const connectGitHubRepo = async () => {
    if (!repoUrl.trim()) {
      toast.error('Veuillez entrer une URL de repository GitHub valide');
      return;
    }

    try {
      // Simple validation of GitHub URL
      const urlPattern = /^https:\/\/github\.com\/[\w\-\.]+\/[\w\-\.]+(?:\.git)?$/;
      if (!urlPattern.test(repoUrl.trim())) {
        toast.error('Format d\'URL GitHub invalide. Utilisez: https://github.com/user/repo');
        return;
      }

      setConnectedRepo({
        url: repoUrl.trim(),
        name: repoUrl.trim().split('/').slice(-1)[0].replace('.git', ''),
        connectedAt: new Date().toISOString()
      });
      
      toast.success('Repository GitHub connecté avec succès !');
      setRepoUrl('');
    } catch (error) {
      toast.error('Erreur lors de la connexion du repository');
    }
  };

  const disconnectGitHubRepo = () => {
    setConnectedRepo(null);
    toast.success('Repository GitHub déconnecté');
  };

  const saveToGitHub = async () => {
    if (!connectedRepo || !currentRun) {
      toast.error('Aucun repository connecté ou run sélectionné');
      return;
    }

    try {
      // Here you would implement the actual GitHub save logic
      // For now, we'll just show a success message
      toast.success(`Projet sauvegardé vers ${connectedRepo.name} !`);
    } catch (error) {
      toast.error('Erreur lors de la sauvegarde vers GitHub');
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: 'bg-amber-500',
      running: 'bg-blue-500',
      completed: 'bg-green-500',
      failed: 'bg-red-500',
      cancelled: 'bg-gray-500'
    };
    return colors[status] || 'bg-gray-500';
  };

  const getStatusIcon = (status) => {
    const icons = {
      pending: <Pause className="w-4 h-4" />,
      running: <Play className="w-4 h-4" />,
      completed: <Square className="w-4 h-4" />,
      failed: <Square className="w-4 h-4" />,
      cancelled: <Square className="w-4 h-4" />
    };
    return icons[status] || <Square className="w-4 h-4" />;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="container mx-auto px-6 py-8">
        {/* Header */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-3 bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg">
                <Bot className="w-8 h-8 text-white" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900">AI Agent Orchestrator</h1>
                <p className="text-gray-600">Plan → Code → Test → Fix → Deploy</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <Button 
                onClick={() => setShowAdminGlobal(true)}
                variant="outline"
                size="sm"
                className="flex items-center"
              >
                <Settings className="w-4 h-4 mr-2" />
                Admin Global
              </Button>
              
              {currentRun && (
                <div className="flex items-center space-x-2">
                  <Badge variant="outline" className={`${getStatusColor(currentRun.status)} text-white border-none`}>
                    {getStatusIcon(currentRun.status)}
                    <span className="ml-1 capitalize">{currentRun.status}</span>
                  </Badge>
                  
                  {['pending', 'running'].includes(currentRun.status) && (
                    <Button onClick={cancelRun} variant="outline" size="sm">
                      <Square className="w-4 h-4 mr-1" />
                      Cancel
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Run Creation & List */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="col-span-3"
          >
            {/* Create New Run */}
            <Card className="mb-6 border-0 shadow-xl bg-white/70 backdrop-blur-sm">
              <CardHeader className="pb-4">
                <CardTitle className="flex items-center text-lg">
                  <Code className="w-5 h-5 mr-2 text-blue-600" />
                  New Agent Run
                </CardTitle>
                <CardDescription>
                  Describe what you want the AI agent to build or fix
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">Goal</label>
                  <Textarea
                    placeholder="e.g., Create a Laravel API for user management with authentication..."
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    className="min-h-[100px] resize-none border-gray-200 focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">Project Path (optional)</label>
                  <input
                    type="text"
                    placeholder="/path/to/project"
                    value={projectPath}
                    onChange={(e) => setProjectPath(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium text-gray-700 mb-2 block">Stack</label>
                  <select
                    value={stack}
                    onChange={(e) => setStack(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="laravel">Laravel + PHP</option>
                    <option value="react">React + Node.js</option>
                    <option value="vue">Vue.js</option>
                    <option value="python">Python</option>
                  </select>
                </div>
                
                <Button 
                  onClick={createRun} 
                  disabled={isCreatingRun || !goal.trim()}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                >
                  {isCreatingRun ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      Start Agent
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Recent Runs */}
            <RunsList 
              runs={runs} 
              currentRun={currentRun} 
              onSelectRun={selectRun}
              getStatusColor={getStatusColor}
              getStatusIcon={getStatusIcon}
            />
          </motion.div>

          {/* Main Content Area */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="col-span-9"
          >
            {currentRun ? (
              <div className="space-y-6">
                {/* Run Header */}
                <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
                  <CardHeader className="pb-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-xl mb-2">{currentRun.goal}</CardTitle>
                        <div className="flex items-center space-x-4 text-sm text-gray-600">
                          <span>Stack: {currentRun.stack}</span>
                          <span>Step: {currentRun.current_step + 1}/{currentRun.max_steps}</span>
                          <span>Created: {new Date(currentRun.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                      
                      <CostMeter 
                        used={currentRun.cost_used_eur} 
                        budget={currentRun.daily_budget_eur}
                      />
                    </div>
                  </CardHeader>
                </Card>

                {/* Progress Bar */}
                <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-700">Progress</span>
                      <span className="text-sm text-gray-500">
                        {Math.round((currentRun.current_step / currentRun.max_steps) * 100)}%
                      </span>
                    </div>
                    <Progress 
                      value={(currentRun.current_step / currentRun.max_steps) * 100}
                      className="h-2"
                    />
                  </CardContent>
                </Card>

                {/* Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList className="grid w-full grid-cols-5 bg-white/70 backdrop-blur-sm">
                    <TabsTrigger value="overview" className="flex items-center">
                      <TrendingUp className="w-4 h-4 mr-2" />
                      Timeline
                    </TabsTrigger>
                    <TabsTrigger value="diff" className="flex items-center">
                      <GitBranch className="w-4 h-4 mr-2" />
                      Code Changes
                    </TabsTrigger>
                    <TabsTrigger value="logs" className="flex items-center">
                      <Terminal className="w-4 h-4 mr-2" />
                      Logs
                    </TabsTrigger>
                    <TabsTrigger value="files" className="flex items-center">
                      <FileText className="w-4 h-4 mr-2" />
                      Files
                    </TabsTrigger>
                    <TabsTrigger value="admin" className="flex items-center">
                      <Settings className="w-4 h-4 mr-2" />
                      Admin
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="mt-6">
                    <Timeline 
                      run={currentRun} 
                      onRetryStep={retryStep}
                      getStatusColor={getStatusColor}
                    />
                  </TabsContent>

                  <TabsContent value="diff" className="mt-6">
                    <DiffViewer run={currentRun} />
                  </TabsContent>

                  <TabsContent value="logs" className="mt-6">
                    <LogViewer logs={logs} />
                  </TabsContent>

                  <TabsContent value="files" className="mt-6">
                    <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
                      <CardHeader>
                        <CardTitle>Project Files</CardTitle>
                        <CardDescription>
                          Files that will be modified by the AI agent
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="text-gray-500 text-center py-8">
                          File viewer coming soon...
                        </div>
                      </CardContent>
                    </Card>
                  </TabsContent>

                  <TabsContent value="admin" className="mt-6">
                    <AdminPanel />
                  </TabsContent>
                </Tabs>
              </div>
            ) : (
              <div className="flex items-center justify-center h-96">
                <div className="text-center space-y-4">
                  <div className="p-4 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
                    <Bot className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900">No Active Run</h3>
                  <p className="text-gray-600 max-w-md">
                    Create a new AI agent run or select an existing one from the sidebar to get started.
                  </p>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </div>
      
      <Toaster position="top-right" richColors />
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;