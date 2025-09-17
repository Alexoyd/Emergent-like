# AI Agent Orchestrator

A comprehensive AI-powered coding agent system that can plan, code, test, fix, and deploy projects automatically. Built with FastAPI backend, React frontend, and MongoDB database.

## 🚀 Features

### Core Capabilities
- **Multi-Step Planning**: AI generates detailed execution plans
- **Automatic Code Generation**: Creates minimal, focused patches
- **Comprehensive Testing**: Runs Pest, PHPStan, Pint, Jest, Playwright tests
- **Smart Retry Logic**: Escalates to more powerful models on failure
- **Cost Management**: Budget tracking and daily limits
- **Real-time Monitoring**: Live timeline and logs

### LLM Router & Escalation
- **Local First**: Starts with Ollama (qwen2.5-coder:7b) - FREE
- **Smart Escalation**: OpenAI GPT-5 → Claude Sonnet 4 on failures
- **Cost Optimization**: Automatic model selection based on complexity
- **Budget Guardrails**: Daily limits and spending alerts

### Supported Stacks
- **Laravel + PHP**: Pest, PHPStan, Pint
- **React + Node.js**: Jest, ESLint, Playwright
- **Vue.js**: Vue Test Utils, Vitest
- **Python**: pytest, mypy, black

## 📋 Prerequisites

### Required
- **Node.js** 18+ and yarn
- **Python** 3.11+ with pip
- **MongoDB** 27017
- **Git** for version control

### Optional (for full functionality)
- **Ollama** for local LLM (recommended)
- **OpenAI API Key** for GPT models
- **Anthropic API Key** for Claude models

## 🛠 Installation

### 1. Install Ollama (Recommended)

#### macOS
```bash
brew install ollama
ollama serve &
ollama pull qwen2.5-coder:7b
```

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
systemctl start ollama
ollama pull qwen2.5-coder:7b
```

#### Windows
Download from [ollama.ai](https://ollama.ai) and install, then:
```bash
ollama pull qwen2.5-coder:7b
```

### 2. Configure Environment

#### Backend Configuration
Edit `/app/backend/.env`:
```env
# Database
MONGO_URL="mongodb://localhost:27017"
DB_NAME="agent_orchestrator"

# LLM API Keys (add your keys here)
OPENAI_API_KEY=""
ANTHROPIC_API_KEY=""

# Ollama Configuration
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen2.5-coder:7b"

# Budget and Limits
DEFAULT_DAILY_BUDGET_EUR=5.0
MAX_STEPS_PER_RUN=20
MAX_RETRIES_PER_STEP=2
```

### 3. Start Services

#### Production Mode (current environment)
```bash
sudo supervisorctl restart all
```

#### Check Status
```bash
sudo supervisorctl status
```

## 🎯 Usage

### Basic Usage

1. **Open the Web Interface**
   - The frontend is already running and accessible
   - The AI Agent Orchestrator dashboard will load

2. **Create a New Run**
   - Enter your goal in the text area
   - Specify project path (optional)
   - Select your stack (Laravel, React, etc.)
   - Click "Start Agent"

3. **Monitor Progress**
   - Watch the real-time timeline
   - View code changes in the diff viewer  
   - Monitor logs and costs
   - Retry failed steps if needed

### Example Goals

#### Laravel Projects
```
Create a Laravel API for user management with authentication, 
including registration, login, logout, and profile endpoints.
Add proper validation and tests.
```

#### React Projects  
```
Build a React dashboard with user authentication, data tables, 
charts, and responsive design. Include TypeScript and proper 
error handling.
```

#### Bug Fixes
```
Fix the authentication bug in the Laravel project where users 
can't log in after password reset. Add proper error handling 
and tests.
```

## 🧪 Testing the System

### Quick API Test
```bash
# Test the API is running
curl -X GET https://codeforge-agent.preview.emergentagent.com/api/

# Create a test run
curl -X POST https://codeforge-agent.preview.emergentagent.com/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Create a simple Hello World Laravel route",
    "stack": "laravel",
    "max_steps": 5,
    "daily_budget_eur": 1.0
  }'
```

### Check Services
```bash
# Check if all services are running
sudo supervisorctl status

# Check backend logs
tail -f /var/log/supervisor/backend.*.log

# Check frontend
curl -I https://codeforge-agent.preview.emergentagent.com/
```

## 🔧 Configuration

### Add Your API Keys

To enable the full LLM escalation system, add your API keys to `/app/backend/.env`:

```bash
# Edit the environment file
nano /app/backend/.env

# Add your keys (replace with actual keys)
OPENAI_API_KEY="sk-your-openai-key-here"
ANTHROPIC_API_KEY="sk-ant-your-claude-key-here"

# Restart backend to apply changes
sudo supervisorctl restart backend
```

### Budget and Limits

Adjust in `/app/backend/.env`:
```env
DEFAULT_DAILY_BUDGET_EUR=10.0  # Increase daily budget
MAX_STEPS_PER_RUN=30           # Allow more steps
MAX_RETRIES_PER_STEP=3         # More retries per step
```

## 🐛 Troubleshooting

### Check System Status
```bash
# Overall system status
sudo supervisorctl status

# Backend logs
tail -n 50 /var/log/supervisor/backend.*.log

# Test API connectivity
curl https://codeforge-agent.preview.emergentagent.com/api/
```

### Common Issues

#### 1. Backend Not Starting
```bash
# Check backend logs for errors
tail -f /var/log/supervisor/backend.err.log

# Common fix: Missing dependencies
cd /app/backend
pip install -r requirements.txt
sudo supervisorctl restart backend
```

#### 2. Database Connection Issues
```bash
# Check MongoDB status
sudo systemctl status mongod

# Test MongoDB connection
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017')
print('MongoDB connected:', client.admin.command('ismaster'))
"
```

#### 3. Frontend Build Issues
```bash
# Check if dependencies are installed
cd /app/frontend
yarn install

# Restart frontend
sudo supervisorctl restart frontend
```

## 📊 System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React UI      │    │  FastAPI        │    │   MongoDB       │
│   Timeline      │◄──►│  Orchestrator   │◄──►│   State Store   │
│   Diff Viewer   │    │   LLM Router    │    │   Logs & Costs  │
│   Cost Meter    │    │   Tool Manager  │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  LLM Providers  │              │
         │              │                 │              │
         └──────────────┤  • Ollama       │──────────────┘
                        │  • OpenAI GPT-5 │
                        │  • Claude       │
                        └─────────────────┘
```

## 🎉 Quick Start Example

The system is ready to use! Try this example:

1. **Open the frontend** (it should be running already)
2. **Create a new run** with this goal:

```
Create a simple Laravel API endpoint that returns "Hello World" 
with proper routing and a basic test.
```

3. **Watch the magic happen**:
   - The agent will plan the steps
   - Generate the Laravel code
   - Create tests
   - Run validation
   - Fix any issues automatically

**Expected Result**: You'll get working Laravel code with:
- A clean route definition
- Proper controller structure  
- PHPUnit/Pest tests
- Code that passes PHPStan and Pint checks

## 🚀 Next Steps

1. **Add your API keys** for full LLM escalation
2. **Install Ollama** for free local LLM usage
3. **Try more complex projects** - Laravel APIs, React apps, etc.
4. **Monitor costs** and adjust budgets as needed
5. **Explore the timeline** and diff viewer features

Happy coding with your AI agent! 🤖✨
