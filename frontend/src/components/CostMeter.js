import React from 'react';
import { TrendingUp, DollarSign, AlertTriangle } from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';

const CostMeter = ({ used, budget }) => {
  const percentage = Math.min((used / budget) * 100, 100);
  const remaining = Math.max(budget - used, 0);
  
  const getStatusColor = () => {
    if (percentage < 50) return 'text-green-600';
    if (percentage < 80) return 'text-amber-600';
    return 'text-red-600';
  };

  const getStatusBadge = () => {
    if (percentage < 50) return { variant: 'default', text: 'Good', color: 'bg-green-500' };
    if (percentage < 80) return { variant: 'outline', text: 'Warning', color: 'bg-amber-500' };
    return { variant: 'destructive', text: 'Critical', color: 'bg-red-500' };
  };

  const status = getStatusBadge();

  return (
    <Card className="w-64 border-0 shadow-lg bg-white/80 backdrop-blur-sm">
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-blue-100 rounded-md">
              <DollarSign className="w-4 h-4 text-blue-600" />
            </div>
            <span className="text-sm font-medium text-gray-700">Daily Budget</span>
          </div>
          <Badge variant={status.variant} className="text-xs h-5">
            {status.text}
          </Badge>
        </div>
        
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <span>Used: €{used.toFixed(3)}</span>
            <span>Remaining: €{remaining.toFixed(3)}</span>
          </div>
          
          <div className="relative">
            <Progress value={percentage} className="h-2" />
            <div 
              className={`absolute top-0 left-0 h-2 rounded-full cost-meter-fill`}
              style={{ width: `${percentage}%` }}
            />
          </div>
          
          <div className="flex items-center justify-between">
            <span className={`text-xs font-medium ${getStatusColor()}`}>
              {percentage.toFixed(1)}% used
            </span>
            <span className="text-xs text-gray-500">
              €{budget.toFixed(2)} budget
            </span>
          </div>
        </div>

        {percentage > 90 && (
          <div className="mt-3 flex items-start space-x-2 p-2 bg-red-50 border border-red-200 rounded-md">
            <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-red-700">
              <p className="font-medium">Budget Alert</p>
              <p>You're approaching your daily limit. Consider increasing the budget or optimizing prompts.</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default CostMeter;