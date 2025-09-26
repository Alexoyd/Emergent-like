import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Play, 
  Upload, 
  FileText, 
  X, 
  Eye, 
  Code,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

const CreateRunForm = ({ 
  onCreateRun, 
  isCreating = false,
  onPreviewPlan,
  generatedPlan = null,
  validationErrors = []
}) => {
  const [formData, setFormData] = useState({
    goal: '',
    projectPath: '',
    stack: 'laravel',
    maxSteps: 20,
    maxRetriesPerStep: 2,
    dailyBudgetEur: 5.0
  });
  
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [showPreview, setShowPreview] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const fileInputRef = useRef(null);

  const stacks = [
    { value: 'laravel', label: 'Laravel + PHP', icon: '🐘' },
    { value: 'react', label: 'React + Node.js', icon: '⚛️' },
    { value: 'vue', label: 'Vue.js', icon: '💚' },
    { value: 'python', label: 'Python', icon: '🐍' },
    { value: 'node', label: 'Node.js', icon: '🟢' }
  ];

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFileUpload = (event) => {
    const files = Array.from(event.target.files);
    const validFiles = files.filter(file => {
      // Limite de 5MB par fichier
      if (file.size > 5 * 1024 * 1024) {
        toast.error(`File ${file.name} is too large (max 5MB)`);
        return false;
      }
      
      // Types de fichiers supportés
      const allowedTypes = [
        'text/plain',
        'application/json',
        'text/markdown',
        'application/pdf',
        'image/png',
        'image/jpeg',
        'application/zip'
      ];
      
      if (!allowedTypes.includes(file.type) && !file.name.match(/\.(txt|md|json|pdf|png|jpg|jpeg|zip)$/i)) {
        toast.error(`File type not supported: ${file.name}`);
        return false;
      }
      
      return true;
    });

    if (validFiles.length > 0) {
      setUploadedFiles(prev => [...prev, ...validFiles]);
      toast.success(`${validFiles.length} file(s) uploaded successfully`);
    }
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const validateForm = () => {
    const errors = [];
    
    if (!formData.goal.trim() || formData.goal.length < 10) {
      errors.push('Goal must be at least 10 characters long');
    }
    
    if (formData.goal.length > 2000) {
      errors.push('Goal must be less than 2000 characters');
    }
    
    if (formData.maxSteps < 1 || formData.maxSteps > 50) {
      errors.push('Max steps must be between 1 and 50');
    }
    
    if (formData.dailyBudgetEur < 0.1 || formData.dailyBudgetEur > 100) {
      errors.push('Daily budget must be between €0.10 and €100.00');
    }
    
    return errors;
  };

  const handlePreviewPlan = async () => {
    const errors = validateForm();
    if (errors.length > 0) {
      errors.forEach(error => toast.error(error));
      return;
    }

    setIsValidating(true);
    try {
      if (onPreviewPlan) {
        await onPreviewPlan({
          ...formData,
          files: uploadedFiles
        });
        setShowPreview(true);
      }
    } catch (error) {
      toast.error('Failed to generate plan preview');
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = async () => {
    const errors = validateForm();
    if (errors.length > 0) {
      errors.forEach(error => toast.error(error));
      return;
    }

    try {
      await onCreateRun({
        ...formData,
        files: uploadedFiles
      });
    } catch (error) {
      toast.error('Failed to create run');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <Card className="border-0 shadow-xl bg-white/70 backdrop-blur-sm">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center text-lg">
          <Code className="w-5 h-5 mr-2 text-blue-600" />
          Create New Agent Run
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Goal Input */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Goal *
          </label>
          <Textarea
            placeholder="Describe in detail what you want the AI agent to accomplish. Be specific about requirements, features, and expected outcomes..."
            value={formData.goal}
            onChange={(e) => handleInputChange('goal', e.target.value)}
            className="min-h-[120px] resize-none border-gray-200 focus:border-blue-500 focus:ring-blue-500"
          />
          <div className="flex justify-between mt-1">
            <span className="text-xs text-gray-500">
              {formData.goal.length}/2000 characters
            </span>
            {formData.goal.length >= 10 && (
              <CheckCircle className="w-4 h-4 text-green-500" />
            )}
          </div>
        </div>

        {/* Project Path */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Project Path (optional)
          </label>
          <input
            type="text"
            placeholder="/path/to/existing/project"
            value={formData.projectPath}
            onChange={(e) => handleInputChange('projectPath', e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Stack Selection */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Technology Stack *
          </label>
          <div className="grid grid-cols-2 gap-2">
            {stacks.map((stack) => (
              <button
                key={stack.value}
                type="button"
                onClick={() => handleInputChange('stack', stack.value)}
                className={`p-3 rounded-lg border-2 transition-all ${
                  formData.stack === stack.value
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center space-x-2">
                  <span className="text-lg">{stack.icon}</span>
                  <span className="text-sm font-medium">{stack.label}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* File Upload */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Context Files (optional)
          </label>
          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-600">
              Click to upload files or drag and drop
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Supported: TXT, MD, JSON, PDF, Images, ZIP (max 5MB each)
            </p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileUpload}
            className="hidden"
            accept=".txt,.md,.json,.pdf,.png,.jpg,.jpeg,.zip"
          />
          
          {/* Uploaded Files */}
          {uploadedFiles.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-sm font-medium text-gray-700">
                Uploaded Files ({uploadedFiles.length})
              </p>
              {uploadedFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between bg-gray-50 p-2 rounded">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-gray-500" />
                    <span className="text-sm">{file.name}</span>
                    <Badge variant="secondary" className="text-xs">
                      {formatFileSize(file.size)}
                    </Badge>
                  </div>
                  <button
                    onClick={() => removeFile(index)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Advanced Settings */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Max Steps
            </label>
            <input
              type="number"
              min="1"
              max="50"
              value={formData.maxSteps}
              onChange={(e) => handleInputChange('maxSteps', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block">
              Daily Budget (€)
            </label>
            <input
              type="number"
              min="0.1"
              max="100"
              step="0.1"
              value={formData.dailyBudgetEur}
              onChange={(e) => handleInputChange('dailyBudgetEur', parseFloat(e.target.value))}
              className="w-full px-3 py-2 border border-gray-200 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Validation Errors */}
        {validationErrors.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="flex items-center space-x-2 mb-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium text-red-800">Validation Errors</span>
            </div>
            <ul className="text-sm text-red-700 space-y-1">
              {validationErrors.map((error, index) => (
                <li key={index}>• {error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex space-x-3">
          <Button
            onClick={handlePreviewPlan}
            disabled={isValidating || formData.goal.length < 10}
            variant="outline"
            className="flex-1"
          >
            {isValidating ? (
              <>
                <div className="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin mr-2" />
                Generating...
              </>
            ) : (
              <>
                <Eye className="w-4 h-4 mr-2" />
                Preview Plan
              </>
            )}
          </Button>
          
          <Button
            onClick={handleSubmit}
            disabled={isCreating || formData.goal.length < 10}
            className="flex-1 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
          >
            {isCreating ? (
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
        </div>

        {/* Plan Preview Modal */}
        <AnimatePresence>
          {showPreview && generatedPlan && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
              onClick={() => setShowPreview(false)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                className="bg-white rounded-lg shadow-xl max-w-4xl max-h-[80vh] overflow-hidden"
                onClick={e => e.stopPropagation()}
              >
                <div className="flex items-center justify-between p-6 border-b">
                  <h3 className="text-lg font-semibold">Generated Plan Preview</h3>
                  <button
                    onClick={() => setShowPreview(false)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <X className="w-6 h-6" />
                  </button>
                </div>
                
                <div className="p-6 overflow-y-auto max-h-[60vh]">
                  <pre className="whitespace-pre-wrap font-mono text-sm bg-gray-50 p-4 rounded">
                    {generatedPlan}
                  </pre>
                </div>
                
                <div className="flex justify-end space-x-3 p-6 border-t bg-gray-50">
                  <Button
                    onClick={() => setShowPreview(false)}
                    variant="outline"
                  >
                    Modify
                  </Button>
                  <Button
                    onClick={() => {
                      setShowPreview(false);
                      handleSubmit();
                    }}
                    className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
                  >
                    Approve & Start
                  </Button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
};

export default CreateRunForm;