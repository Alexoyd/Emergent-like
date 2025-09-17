import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Terminal, 
  Info, 
  AlertCircle, 
  CheckCircle, 
  XCircle,
  Download,
  Trash2
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';

const LogViewer = ({ logs }) => {
  const scrollAreaRef = useRef(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [logs]);

  const getLogIcon = (type) => {
    const icons = {
      info: <Info className="w-4 h-4 text-blue-500" />,
      success: <CheckCircle className="w-4 h-4 text-green-500" />,
      warning: <AlertCircle className="w-4 h-4 text-amber-500" />,
      error: <XCircle className="w-4 h-4 text-red-500" />,
      plan: <Terminal className="w-4 h-4 text-purple-500" />
    };
    return icons[type] || icons.info;
  };

  const getLogClass = (type) => {
    const classes = {
      info: 'log-entry info',
      success: 'log-entry success',
      warning: 'log-entry warning',
      error: 'log-entry error',
      plan: 'log-entry info'
    };
    return classes[type] || 'log-entry';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const downloadLogs = () => {
    const logText = logs.map(log => 
      `[${formatTimestamp(log.timestamp)}] ${log.type.toUpperCase()}: ${log.content}`
    ).join('\n');
    
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (logs.length === 0) {
    return (
      <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Terminal className="w-5 h-5 mr-2 text-blue-600" />
            Execution Logs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
              <Terminal className="w-8 h-8 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Logs Yet</h3>
            <p className="text-gray-600">Execution logs will appear here as the AI agent works.</p>
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
            <Terminal className="w-5 h-5 mr-2 text-blue-600" />
            Execution Logs
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="text-xs">
              {logs.length} entries
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={downloadLogs}
              className="h-8 px-3 text-xs"
            >
              <Download className="w-3 h-3 mr-1" />
              Download
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea ref={scrollAreaRef} className="h-96 log-viewer">
          <div className="space-y-1">
            <AnimatePresence>
              {logs.map((log, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                  className={getLogClass(log.type)}
                >
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {getLogIcon(log.type)}
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <Badge 
                          variant="outline" 
                          className="text-xs h-5 mb-1 capitalize"
                        >
                          {log.type}
                        </Badge>
                        <span className="text-xs text-gray-500">
                          {formatTimestamp(log.timestamp)}
                        </span>
                      </div>
                      
                      <div className="text-sm text-gray-900 break-words">
                        {log.type === 'plan' ? (
                          <div className="bg-purple-50 border border-purple-200 rounded p-3 mt-1">
                            <pre className="whitespace-pre-wrap font-mono text-xs">
                              {log.content}
                            </pre>
                          </div>
                        ) : (
                          <div className="whitespace-pre-wrap">
                            {log.content}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default LogViewer;