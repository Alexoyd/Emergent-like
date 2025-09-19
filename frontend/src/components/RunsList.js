import React from 'react';
import { motion } from 'framer-motion';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  Pause,
  Play,
  History,
  TrendingUp,
  ExternalLink,
  Eye
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Button } from './ui/button';
import { toast } from 'sonner';

const RunsList = ({ runs, currentRun, onSelectRun, getStatusColor, getStatusIcon }) => {
  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInMinutes = Math.floor((now - time) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  const truncateGoal = (goal, maxLength = 60) => {
    if (goal.length <= maxLength) return goal;
    return goal.substring(0, maxLength) + '...';
  };

  const previewProject = (run, event) => {
    event.stopPropagation(); // Prevent selecting the run
    
    const supportedStacks = ['react', 'vue', 'laravel'];
    
    if (!supportedStacks.includes(run.stack)) {
      toast.error(`Preview non disponible pour le stack ${run.stack}`);
      return;
    }

    // Here you would implement the actual preview logic
    // For now, we'll simulate opening a preview
    const previewUrl = `${process.env.REACT_APP_BACKEND_URL}/api/projects/${run.project_id}/preview`;
    
    try {
      window.open(previewUrl, '_blank', 'width=1200,height=800');
      toast.success('Ouverture de la preview du projet...');
    } catch (error) {
      toast.error('Impossible d\'ouvrir la preview du projet');
    }
  };

  if (runs.length === 0) {
    return (
      <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center text-sm">
            <History className="w-4 h-4 mr-2 text-gray-600" />
            Recent Runs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-gray-100 rounded-full mb-3">
              <History className="w-6 h-6 text-gray-400" />
            </div>
            <p className="text-sm text-gray-600">No runs yet</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center justify-between text-sm">
          <div className="flex items-center">
            <History className="w-4 h-4 mr-2 text-gray-600" />
            Recent Runs
          </div>
          <Badge variant="outline" className="text-xs">
            {runs.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-80">
          <div className="space-y-2 p-4">
            {runs.map((run, index) => (
              <motion.div
                key={run.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => onSelectRun(run)}
                className={`p-3 rounded-lg border cursor-pointer transition-all duration-200 hover:shadow-md ${
                  currentRun?.id === run.id 
                    ? 'border-blue-200 bg-blue-50 shadow-sm' 
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className={`p-1 rounded ${getStatusColor(run.status)} bg-opacity-20`}>
                      {getStatusIcon(run.status)}
                    </div>
                    <Badge 
                      variant="outline" 
                      className={`text-xs h-5 ${getStatusColor(run.status)} border-current text-current`}
                    >
                      {run.status}
                    </Badge>
                  </div>
                  
                  <span className="text-xs text-gray-500">
                    {formatTimeAgo(run.created_at)}
                  </span>
                </div>
                
                <div className="mb-2">
                  <p className="text-sm font-medium text-gray-900 line-clamp-2 leading-tight">
                    {truncateGoal(run.goal)}
                  </p>
                </div>
                
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <div className="flex items-center space-x-2">
                    <span>{run.stack}</span>
                    <span>•</span>
                    <span>Step {run.current_step + 1}/{run.max_steps}</span>
                  </div>
                  
                  {run.cost_used_eur > 0 && (
                    <span className="font-mono">
                      €{run.cost_used_eur.toFixed(3)}
                    </span>
                  )}
                </div>
                
                {/* Progress bar for active runs */}
                {['pending', 'running'].includes(run.status) && (
                  <div className="mt-2">
                    <div className="w-full bg-gray-200 rounded-full h-1">
                      <div 
                        className={`h-1 rounded-full transition-all duration-300 ${
                          run.status === 'running' ? 'bg-blue-500' : 'bg-gray-400'
                        }`}
                        style={{
                          width: `${(run.current_step / run.max_steps) * 100}%`
                        }}
                      />
                    </div>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default RunsList;