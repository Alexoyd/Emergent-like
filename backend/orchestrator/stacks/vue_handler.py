# stacks/vue_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List

from .base_handler import StackHandler
from .registry import StackRegistry

class VueHandler(StackHandler):
    name = "vue"
    default_test_command: List[str] = ["npm", "run", "test"]

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """
        Complete Vue.js project with Vite (modern setup)
        """
        dirs = [
            "src/components",
            "src/views",
            "src/router",
            "src/store",
            "src/assets",
            "public",
            "tests/unit",
        ]
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)
        
        files = {
            # Root index.html (required by Vite)
            "index.html": f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <link rel="icon" type="image/svg+xml" href="/vite.svg">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name or 'Vue App'}</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
""",

            # Modern package.json with Vite and proper scripts
            "package.json": f"""{{
  "name": "{project_name or 'vue-project'}",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint src/ --ext .js,.vue",
    "lint:fix": "eslint src/ --ext .js,.vue --fix"
  }},
  "dependencies": {{
    "vue": "^3.4.0",
    "vue-router": "^4.2.0"
  }},
  "devDependencies": {{
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0",
    "@vue/test-utils": "^2.4.0",
    "eslint": "^8.56.0",
    "eslint-plugin-vue": "^9.19.0",
    "jsdom": "^23.0.0"
  }}
}}""",

            # Vite config (required for Vue)
            "vite.config.js": """import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true
  },
  test: {
    environment: 'jsdom',
    globals: true
  }
})
""",

            # Main App component with router-view
            "src/App.vue": """<template>
  <div id="app">
    <nav>
      <router-link to="/">Home</router-link> |
      <router-link to="/about">About</router-link>
    </nav>
    <router-view />
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  text-align: center;
  color: #2c3e50;
  margin-top: 20px;
}
nav {
  padding: 20px;
}
nav a {
  font-weight: bold;
  color: #2c3e50;
  text-decoration: none;
  margin: 0 10px;
}
nav a.router-link-exact-active {
  color: #42b983;
}
</style>
""",

            # Main.js entry point with router
            "src/main.js": """import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(router)
app.mount('#app')
""",

            # Router configuration
            "src/router/index.js": """import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('../views/About.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
""",

            # Home view
            "src/views/Home.vue": """<template>
  <div class="home">
    <h1>Welcome to Vue.js 3 + Vite</h1>
    <p>This is a modern Vue.js application with Vue Router.</p>
    <Counter />
  </div>
</template>

<script>
import Counter from '../components/Counter.vue'

export default {
  name: 'Home',
  components: {
    Counter
  }
}
</script>

<style scoped>
.home {
  padding: 20px;
}
</style>
""",

            # About view
            "src/views/About.vue": """<template>
  <div class="about">
    <h1>About</h1>
    <p>This is an about page built with Vue.js 3 and Vite.</p>
  </div>
</template>

<script>
export default {
  name: 'About'
}
</script>

<style scoped>
.about {
  padding: 20px;
}
</style>
""",

            # Counter component (FIXED: single version with increment/decrement)
            "src/components/Counter.vue": """<template>
  <div class="counter">
    <button @click="decrement">-</button>
    <span>{{ count }}</span>
    <button @click="increment">+</button>
  </div>
</template>

<script>
import { ref } from 'vue'

export default {
  name: 'Counter',
  setup() {
    const count = ref(0)
    
    const increment = () => count.value++
    const decrement = () => count.value--
    
    return {
      count,
      increment,
      decrement
    }
  }
}
</script>

<style scoped>
.counter {
  margin: 20px;
}
button {
  font-size: 18px;
  margin: 0 10px;
  padding: 5px 15px;
  cursor: pointer;
}
span {
  font-size: 24px;
  font-weight: bold;
}
</style>
""",

            # ESLint config
            ".eslintrc.cjs": """module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true
  },
  extends: [
    'eslint:recommended',
    'plugin:vue/vue3-recommended'
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  rules: {
    'vue/multi-word-component-names': 'off'
  }
}
""",

            # Vitest setup (aligned with Counter.vue)
            "tests/unit/Counter.spec.js": """import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import Counter from '../../src/components/Counter.vue'

describe('Counter', () => {
  it('renders properly', () => {
    const wrapper = mount(Counter)
    expect(wrapper.text()).toContain('0')
  })
  
  it('increments count when + clicked', async () => {
    const wrapper = mount(Counter)
    const buttons = wrapper.findAll('button')
    await buttons[1].trigger('click')
    expect(wrapper.text()).toContain('1')
  })
  
  it('decrements count when - clicked', async () => {
    const wrapper = mount(Counter)
    const buttons = wrapper.findAll('button')
    await buttons[0].trigger('click')
    expect(wrapper.text()).toContain('-1')
  })
})
""",

            # README
            "README.md": f"""# {project_name or 'Vue Project'}

Modern Vue.js 3 application with Vite.

## Setup
```bash
npm install
```

## Development
```bash
npm run dev
```

## Build
```bash
npm run build
```

## Test
```bash
npm run test
```
"""
        }

        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

        if self.logger:
            self.logger.info(f"✅ Created complete Vue.js 3 + Vite structure at {code_path}")

    async def install_dependencies(self, code_path: Path) -> bool:
        """
        Install Vue.js dependencies with Vite
        """
        if self.logger:
            self.logger.info("Installing Vue.js + Vite dependencies with npm...")
        
        npm = await self.run_command(["npm", "install"], cwd=str(code_path))
        success = npm.returncode == 0
        
        if not success:
            if self.logger:
                self.logger.warning(f"npm install failed: {npm.stderr}, trying yarn...")
            res = await self.run_command(["yarn", "install"], cwd=str(code_path))
            success = res.returncode == 0
        
        if success and self.logger:
            self.logger.info("✅ Vue.js + Vite dependencies installed successfully")
        elif self.logger:
            self.logger.error("❌ Failed to install Vue.js dependencies")
        
        return success

StackRegistry.register(VueHandler.name, VueHandler)