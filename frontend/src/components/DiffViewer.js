import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  FileText, 
  Plus, 
  Minus, 
  RotateCcw,
  Download,
  Copy,
  Check
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { ScrollArea } from './ui/scroll-area';
import { toast } from 'sonner';

const DiffViewer = ({ run }) => {
  const [copiedIndex, setCopiedIndex] = useState(null);
  
  // Extract patches from steps
  const patches = run.steps?.filter(step => step.patch && step.patch.trim()) || [];
  
  const copyToClipboard = async (content, index) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedIndex(index);
      toast.success('Patch copied to clipboard');
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (error) {
      toast.error('Failed to copy patch');
    }
  };

  const parseDiff = (patch) => {
    const lines = patch.split('\n');
    const files = [];
    let currentFile = null;
    let currentHunk = null;

    for (const line of lines) {
      if (line.startsWith('diff --git') || line.startsWith('+++') || line.startsWith('---')) {
        if (line.startsWith('+++')) {
          const filename = line.substring(4);
          if (filename !== '/dev/null') {
            if (!currentFile) {
              currentFile = { name: filename.replace(/^[ab]\//, ''), hunks: [] };
              files.push(currentFile);
            } else {
              currentFile.name = filename.replace(/^[ab]\//, '');
            }
          }
        }
      } else if (line.startsWith('@@')) {
        currentHunk = { header: line, lines: [] };
        if (currentFile) {
          currentFile.hunks.push(currentHunk);
        }
      } else if (currentHunk && (line.startsWith('+') || line.startsWith('-') || line.startsWith(' '))) {
        const type = line.startsWith('+') ? 'added' : 
                    line.startsWith('-') ? 'removed' : 'context';
        currentHunk.lines.push({
          type,
          content: line.substring(1),
          raw: line
        });
      }
    }

    return files;
  };

  const renderDiffLine = (line, index) => {
    const bgColor = line.type === 'added' ? 'bg-green-50 border-l-4 border-green-400' :
                   line.type === 'removed' ? 'bg-red-50 border-l-4 border-red-400' :
                   'bg-gray-50 border-l-4 border-gray-200';
    
    const textColor = line.type === 'added' ? 'text-green-800' :
                     line.type === 'removed' ? 'text-red-800' :
                     'text-gray-700';

    const icon = line.type === 'added' ? <Plus className="w-3 h-3 text-green-600" /> :
                line.type === 'removed' ? <Minus className="w-3 h-3 text-red-600" /> :
                null;

    return (
      <div key={index} className={`px-4 py-1 font-mono text-sm ${bgColor} ${textColor}`}>
        <div className="flex items-center space-x-2">
          <div className="w-4 flex justify-center">
            {icon}
          </div>
          <span className="flex-1">{line.content}</span>
        </div>
      </div>
    );
  };

  if (patches.length === 0) {
    return (
      <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="flex items-center">
            <FileText className="w-5 h-5 mr-2 text-blue-600" />
            Code Changes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4">
              <FileText className="w-8 h-8 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No Changes Yet</h3>
            <p className="text-gray-600">Code changes will appear here as the AI agent modifies files.</p>
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
            <FileText className="w-5 h-5 mr-2 text-blue-600" />
            Code Changes
          </div>
          <Badge variant="outline" className="text-xs">
            {patches.length} patches
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="0" className="w-full">
          <TabsList className="grid grid-cols-1 w-full mb-4">
            {patches.map((step, index) => (
              <TabsTrigger 
                key={index} 
                value={index.toString()} 
                className="flex items-center justify-between text-left"
              >
                <span>Step {step.step_number + 1}</span>
                <Badge variant="secondary" className="ml-2 text-xs">
                  {step.model_used || 'Unknown'}
                </Badge>
              </TabsTrigger>
            ))}
          </TabsList>

          {patches.map((step, patchIndex) => {
            const files = parseDiff(step.patch);
            
            return (
              <TabsContent key={patchIndex} value={patchIndex.toString()}>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge variant="outline" className="text-xs">
                        Step {step.step_number + 1}
                      </Badge>
                      {step.tests_passed !== undefined && (
                        <Badge variant={step.tests_passed ? "default" : "destructive"} className="text-xs">
                          Tests: {step.tests_passed ? 'PASS' : 'FAIL'}
                        </Badge>
                      )}
                    </div>
                    
                    <div className="flex items-center space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyToClipboard(step.patch, patchIndex)}
                        className="h-8 px-3 text-xs"
                      >
                        {copiedIndex === patchIndex ? (
                          <>
                            <Check className="w-3 h-3 mr-1" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3 mr-1" />
                            Copy Patch
                          </>
                        )}
                      </Button>
                    </div>
                  </div>

                  {files.length > 0 ? (
                    <div className="space-y-4">
                      {files.map((file, fileIndex) => (
                        <motion.div
                          key={fileIndex}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: fileIndex * 0.1 }}
                          className="border border-gray-200 rounded-lg overflow-hidden"
                        >
                          <div className="bg-gray-50 px-4 py-2 border-b border-gray-200">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2">
                                <FileText className="w-4 h-4 text-gray-600" />
                                <span className="font-mono text-sm font-medium text-gray-900">
                                  {file.name}
                                </span>
                              </div>
                              <Badge variant="outline" className="text-xs">
                                {file.hunks.length} change{file.hunks.length !== 1 ? 's' : ''}
                              </Badge>
                            </div>
                          </div>
                          
                          <ScrollArea className="max-h-96">
                            <div className="divide-y divide-gray-100">
                              {file.hunks.map((hunk, hunkIndex) => (
                                <div key={hunkIndex} className="p-2">
                                  <div className="bg-blue-50 px-3 py-1 text-xs text-blue-800 font-mono mb-2 rounded">
                                    {hunk.header}
                                  </div>
                                  <div className="space-y-0">
                                    {hunk.lines.map((line, lineIndex) => 
                                      renderDiffLine(line, lineIndex)
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </ScrollArea>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <div className="bg-gray-50 rounded-lg p-8 text-center">
                      <div className="font-mono text-sm text-gray-600 bg-white rounded border p-4 text-left max-h-64 overflow-y-auto">
                        <pre className="whitespace-pre-wrap">{step.patch}</pre>
                      </div>
                    </div>
                  )}

                  {step.output && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Step Output</h4>
                      <div className="text-xs text-gray-600 font-mono bg-white rounded p-3 max-h-32 overflow-y-auto">
                        {step.output}
                      </div>
                    </div>
                  )}
                </div>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
};

export default DiffViewer;