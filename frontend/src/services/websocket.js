import { toast } from 'sonner';

class WebSocketService {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 5000;
    this.listeners = new Map();
    this.activeRunId = null;
  }

  connect(runId = null) {
    if (this.ws && this.isConnected) {
      return;
    }

    this.activeRunId = runId;
    const wsUrl = `ws://localhost:8001/ws${runId ? `/${runId}` : ''}`;
    
    try {
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.notifyListeners('connected', { runId });
        
        if (runId) {
          toast.success(`Connected to run ${runId.slice(0, 8)}...`);
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        this.isConnected = false;
        this.notifyListeners('disconnected', { code: event.code, reason: event.reason });
        
        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.notifyListeners('error', error);
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      toast.error('Failed to establish real-time connection');
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
      this.isConnected = false;
      this.activeRunId = null;
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
    
    setTimeout(() => {
      if (!this.isConnected) {
        this.connect(this.activeRunId);
      }
    }, this.reconnectInterval);
  }

  handleMessage(data) {
    const { type, payload } = data;
    
    switch (type) {
      case 'run_status_update':
        this.notifyListeners('runStatusUpdate', payload);
        this.showStatusNotification(payload);
        break;
        
      case 'step_update':
        this.notifyListeners('stepUpdate', payload);
        this.showStepNotification(payload);
        break;
        
      case 'log_update':
        this.notifyListeners('logUpdate', payload);
        break;
        
      case 'progress_update':
        this.notifyListeners('progressUpdate', payload);
        break;
        
      case 'error':
        this.notifyListeners('error', payload);
        toast.error(`Run Error: ${payload.message}`);
        break;
        
      default:
        console.log('Unknown WebSocket message type:', type, payload);
    }
  }

  showStatusNotification(payload) {
    const { status, runId } = payload;
    const runIdShort = runId?.slice(0, 8) || '';
    
    switch (status) {
      case 'running':
        toast.info(`Run ${runIdShort}... started`);
        break;
      case 'completed':
        toast.success(`Run ${runIdShort}... completed successfully!`);
        break;
      case 'failed':
        toast.error(`Run ${runIdShort}... failed`);
        break;
      case 'cancelled':
        toast.warning(`Run ${runIdShort}... cancelled`);
        break;
    }
  }

  showStepNotification(payload) {
    const { stepNumber, description, status } = payload;
    
    if (status === 'completed') {
      toast.success(`Step ${stepNumber + 1}: ${description}`, {
        duration: 3000,
      });
    } else if (status === 'failed') {
      toast.error(`Step ${stepNumber + 1} failed: ${description}`);
    }
  }

  // Event listener management
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  notifyListeners(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in WebSocket listener:', error);
        }
      });
    }
  }

  // Send message to server
  send(type, payload) {
    if (this.isConnected && this.ws) {
      try {
        this.ws.send(JSON.stringify({ type, payload }));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
      }
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }
}

// Create singleton instance
const websocketService = new WebSocketService();

export default websocketService;