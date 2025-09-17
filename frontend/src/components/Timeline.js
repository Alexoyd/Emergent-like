import React from 'react';
import { motion } from 'framer-motion';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  RefreshCw, 
  Play, 
  Pause,
  AlertCircle,
  Code,
  TestTube,
  GitCommit
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';

const Timeline = ({ run, onRetryStep, getStatusColor }) => {
  const steps = run.steps || [];
  
  const getStepIcon = (status) => {
    const icons = {
      pending: <Clock className="w-5 h-5 text-gray-400" />,
      running: <Play className="w-5 h-5 text-blue-500" />,
      completed: <CheckCircle className="w-5 h-5 text-green-500" />,
      failed: <XCircle className="w-5 h-5 text-red-500" />,
      retrying: <RefreshCw className="w-5 h-5 text-amber-500 animate-spin" />
    };
    return icons[status] || icons.pending;
  };

  const getStepTypeIcon = (description) => {
    if (description.toLowerCase().includes('test')) {
      return <TestTube className="w-4 h-4" />;
    } else if (description.toLowerCase().includes('commit')) {
      return <GitCommit className="w-4 h-4" />;
    } else {
      return <Code className="w-4 h-4" />;
    }
  };

  const formatDuration = (start, end) => {
    if (!start || !end) return '';
    const duration = new Date(end) - new Date(start);
    const seconds = Math.floor(duration / 1000);
    return `${seconds}s`;
  };

  if (steps.length === 0) {
    return (
      <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Clock className="w-5 h-5 mr-2 text-blue-600" />
            Execution Timeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
              <Play className="w-8 h-8 text-blue-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Planning Phase</h3>
            <p className="text-gray-600">The AI agent is analyzing your goal and creating an execution plan...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center">
            <Clock className="w-5 h-5 mr-2 text-blue-600" />
            Execution Timeline
          </div>
          <Badge variant="outline" className="text-xs">
            {steps.length} steps
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="max-h-96 custom-scrollbar overflow-y-auto">
        <div className="space-y-4">
          {steps.map((step, index) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
              className="timeline-step"
            >
              <div className="flex items-start space-x-4">
                {/* Timeline connector */}
                <div className="flex flex-col items-center">
                  <div className={`p-2 rounded-full border-2 ${
                    step.status === 'completed' ? 'bg-green-50 border-green-200' :
                    step.status === 'failed' ? 'bg-red-50 border-red-200' :
                    step.status === 'running' ? 'bg-blue-50 border-blue-200 status-indicator running' :
                    step.status === 'retrying' ? 'bg-amber-50 border-amber-200' :
                    'bg-gray-50 border-gray-200'
                  }`}>
                    {getStepIcon(step.status)}
                  </div>
                  {index < steps.length - 1 && (
                    <div className={`w-0.5 h-12 mt-2 timeline-connector ${
                      step.status === 'completed' ? 'active' : ''
                    }`} />
                  )}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0">
                  <div className="bg-white rounded-lg border border-gray-100 p-4 shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        {getStepTypeIcon(step.description)}
                        <h4 className="font-medium text-gray-900">
                          Step {step.step_number + 1}: {step.description}
                        </h4>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        {step.model_used && (
                          <Badge variant="secondary" className="text-xs">
                            {step.model_used}
                          </Badge>
                        )}
                        
                        {step.status === 'failed' && step.retries < step.max_retries && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onRetryStep(step.step_number)}
                            className="h-7 px-2 text-xs"
                          >
                            <RefreshCw className="w-3 h-3 mr-1" />
                            Retry
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Step details */}
                    <div className="space-y-2 text-sm">
                      {step.output && (
                        <div className="bg-gray-50 rounded p-3 font-mono text-xs">
                          <div className="line-clamp-3">
                            {step.output.substring(0, 200)}
                            {step.output.length > 200 && '...'}
                          </div>
                        </div>
                      )}

                      {step.error && (
                        <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700">
                          <div className="flex items-start space-x-2">
                            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            <div className="text-xs font-mono">
                              {step.error}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Step metadata */}
                      <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-gray-100">
                        <div className="flex items-center space-x-4">
                          {step.prompt_tokens > 0 && (
                            <span>Tokens: {step.prompt_tokens + step.completion_tokens}</span>
                          )}
                          {step.cost_eur > 0 && (
                            <span>Cost: €{step.cost_eur.toFixed(4)}</span>
                          )}
                          {step.retries > 0 && (
                            <span>Retries: {step.retries}</span>
                          )}
                        </div>
                        
                        <div className="flex items-center space-x-2">
                          {step.tests_passed !== undefined && (
                            <Badge variant={step.tests_passed ? "default" : "destructive"} className="text-xs h-5">
                              Tests: {step.tests_passed ? 'PASS' : 'FAIL'}
                            </Badge>
                          )}
                          
                          <span>
                            {formatDuration(step.created_at, step.updated_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}

          {/* Current step indicator */}
          {run.status === 'running' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex items-center space-x-4 py-4"
            >
              <div className="p-2 rounded-full bg-blue-100 border-2 border-blue-200 status-indicator running">
                <Play className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                    <span className="text-sm font-medium text-blue-900">
                      Executing step {run.current_step + 1}...
                    </span>
                  </div>
                  <p className="text-xs text-blue-700 mt-1">
                    The AI agent is working on the next step of your project.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default Timeline;