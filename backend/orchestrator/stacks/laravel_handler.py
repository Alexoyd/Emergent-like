# stacks/laravel_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import json
import re

from .base_handler import StackHandler
from .registry import StackRegistry
from ..utils import json_utils

class LaravelHandler(StackHandler):
    name = "laravel"
    # 🔥 FIXED: Non-interactive test command to prevent hanging
    default_test_command: List[str] = ["vendor/bin/pest", "--no-interaction", "--stop-on-failure"]

    @staticmethod
    def sanitize_composer_name(name: Optional[str]) -> str:
        """Validate/correct a Composer package name to vendor/project."""
        if not name or not isinstance(name, str):
            return "default/project"
        split_camel = re.sub(r"([a-z0-9])([A-Z])", r"1-\2", name)
        sanitized = split_camel.replace(" ", "-").lower()
        sanitized = re.sub(r"[^a-z0-9._/-]+", "-", sanitized)
        sanitized = re.sub(r"-+", "-", sanitized)
        parts = sanitized.split("/", 1)
        if len(parts) == 1:
            vendor, project = "default", parts[0]
        else:
            vendor, project = parts[0], parts[1]
        vendor = re.sub(r"^[^a-z0-9]+", "", vendor)
        vendor = re.sub(r"[^a-z0-9]+$", "", vendor)
        project = re.sub(r"^[^a-z0-9]+", "", project)
        project = re.sub(r"[^a-z0-9]+$", "", project)
        if not vendor:
            vendor = "default"
        if not project:
            project = "project"
        normalized = f"{vendor}/{project}"
        if re.match(r"^[a-z0-9]([_.-]?[a-z0-9]+)*/[a-z0-9](([_.]|-{1,2})?[a-z0-9]+)*$", normalized):
            return normalized
        return "default/project"

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """
        🔥 PHASE 4 FIX: Create COMPLETE Laravel project with full validation
        Never fallback to incomplete skeleton - ensure functional Laravel installation
        """
        import subprocess
        import asyncio
        import shutil
        import os
        
        try:
            if self.logger:
                self.logger.info("🚀 Creating REAL Laravel project with composer create-project...")
            
            # 🔥 NEW: Check if we already have a valid Laravel project
            if await self._is_valid_laravel_project(code_path):
                if self.logger:
                    self.logger.info("✅ Valid Laravel project already exists, skipping creation")
                return
            
            # 🔥 CRITICAL: Clean target directory if it exists and is not a valid Laravel project
            if code_path.exists():
                if self.logger:
                    self.logger.info("🧹 Cleaning existing incomplete project directory...")
                shutil.rmtree(code_path)
            
            # Ensure parent directory exists
            code_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.logger:
                self.logger.info(f"📦 Running: composer create-project laravel/laravel {code_path} --prefer-dist --no-interaction")
            
            # 🔥 FIXED: Create Laravel project DIRECTLY in target directory
            create_cmd = [
                "composer", "create-project", 
                "laravel/laravel", str(code_path),
                "--prefer-dist", "--no-interaction", "--no-progress"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *create_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(code_path.parent)  # Run from parent directory
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)  # 10 minutes timeout
            
            if process.returncode == 0:
                if self.logger:
                    self.logger.info("✅ Laravel project created successfully with composer")
                    self.logger.info(f"📁 Project created at: {code_path}")
                
                # 🔥 NEW: Verify the installation is complete
                if await self._verify_laravel_installation(code_path):
                    if self.logger:
                        self.logger.info("✅ Laravel installation verification passed")
                    
                    # 🔥 NEW: Initialize Laravel project
                    await self._initialize_laravel_project(code_path)
                        
                    # Create phpstan.neon.dist for static analysis
                    phpstan_config = code_path / "phpstan.neon.dist"
                    phpstan_config.write_text("""parameters:
    paths:
        - app
    level: 5
    ignoreErrors:
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Builder#'
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Collection#'
    excludePaths:
        - 'vendor/*'
        - 'bootstrap/cache/*'
        - 'storage/*'
""")
                    
                    if self.logger:
                        self.logger.info("🎉 Laravel project creation and initialization completed successfully!")
                    return
                else:
                    if self.logger:
                        self.logger.error("❌ Laravel installation verification failed after creation")
                    # 🔥 NEW: Try to fix the installation
                    if await self._retry_laravel_installation(code_path):
                        if self.logger:
                            self.logger.info("✅ Laravel installation fixed on retry")
                        return
                    else:
                        if self.logger:
                            self.logger.error("❌ Laravel installation retry also failed")
            else:
                if self.logger:
                    self.logger.error(f"❌ Composer create-project failed with return code {process.returncode}")
                    self.logger.error(f"STDOUT: {stdout.decode()}")
                    self.logger.error(f"STDERR: {stderr.decode()}")
                        
        except asyncio.TimeoutError:
            if self.logger:
                self.logger.error("❌ Laravel project creation timed out (10 minutes)")
            raise Exception("Laravel project creation timed out - composer create-project took too long")
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Failed to create Laravel project: {e}")
            raise Exception(f"Laravel project creation failed: {e}")
        
        # 🔥 CRITICAL: Never use fallback skeleton - it creates incomplete projects
        # If we reach here, it means composer create-project succeeded but verification failed
        if self.logger:
            self.logger.error("❌ FATAL: Laravel project creation completed but is incomplete")
            self.logger.error("❌ This should never happen - composer create-project should create a complete project")
        
        raise Exception("Laravel project creation failed verification - project is incomplete")
    
    async def _is_valid_laravel_project(self, code_path: Path) -> bool:
        """🔥 NEW: Check if we already have a valid Laravel project"""
        try:
            # Check essential Laravel files
            essential_files = ["artisan", "composer.json", "bootstrap/app.php", "vendor/autoload.php"]
            for file_path in essential_files:
                if not (code_path / file_path).exists():
                    return False
            
            # Check if artisan is executable
            artisan_path = code_path / "artisan"
            if not os.access(artisan_path, os.X_OK):
                return False
            
            # Test if artisan works
            try:
                result = await self.run_command(
                    ["php", "artisan", "--version"],
                    cwd=str(code_path)
                )
                return result.returncode == 0
            except:
                return False
                
        except Exception:
            return False
    
    async def _verify_laravel_installation(self, project_path: Path) -> bool:
        """🔥 ENHANCED: Comprehensive Laravel installation verification with detailed logging"""
        try:
            if self.logger:
                self.logger.info("🔍 Verifying Laravel installation completeness...")
                self.logger.info(f"📁 Checking project at: {project_path}")
            
            # Check essential files exist
            essential_files = [
                "artisan", 
                "composer.json", 
                "bootstrap/app.php", 
                "vendor/autoload.php", 
                "config/app.php", 
                "routes/web.php",
                "vendor/laravel/framework"  # Laravel framework must be installed
            ]
            
            missing_files = []
            existing_files = []
            
            for file_path in essential_files:
                full_path = project_path / file_path
                if full_path.exists():
                    existing_files.append(file_path)
                    if self.logger:
                        self.logger.info(f"✅ Found: {file_path}")
                else:
                    missing_files.append(file_path)
                    if self.logger:
                        self.logger.error(f"❌ Missing: {file_path}")
            
            if missing_files:
                if self.logger:
                    self.logger.error(f"❌ Missing essential Laravel files: {missing_files}")
                    self.logger.info(f"✅ Existing files: {existing_files}")
                return False
            
            # Check if artisan is executable
            artisan_path = project_path / "artisan"
            if not os.access(artisan_path, os.X_OK):
                if self.logger:
                    self.logger.warning("⚠️ Making artisan executable...")
                os.chmod(artisan_path, 0o755)
            
            # Test if artisan works
            try:
                if self.logger:
                    self.logger.info("🧪 Testing artisan command...")
                result = await self.run_command(
                    ["php", "artisan", "--version"],
                    cwd=str(project_path)
                )
                if result.returncode != 0:
                    if self.logger:
                        self.logger.error(f"❌ Artisan test failed: {result.stderr}")
                    return False
                
                if self.logger:
                    self.logger.info(f"✅ Artisan test passed: {result.stdout.strip()}")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ Artisan test error: {e}")
                return False
            
            # Test composer autoloader
            try:
                if self.logger:
                    self.logger.info("🧪 Testing composer autoloader...")
                result = await self.run_command(
                    ["php", "-r", "require 'vendor/autoload.php'; echo 'Autoloader OK';"],
                    cwd=str(project_path)
                )
                if result.returncode != 0 or "Autoloader OK" not in result.stdout:
                    if self.logger:
                        self.logger.error("❌ Composer autoloader test failed")
                        self.logger.error(f"STDOUT: {result.stdout}")
                        self.logger.error(f"STDERR: {result.stderr}")
                    return False
                
                if self.logger:
                    self.logger.info("✅ Composer autoloader test passed")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ Composer autoloader test error: {e}")
                return False
            
            # Test Laravel bootstrap
            try:
                if self.logger:
                    self.logger.info("🧪 Testing Laravel bootstrap...")
                result = await self.run_command(
                    ["php", "-r", "require 'vendor/autoload.php'; require 'bootstrap/app.php'; echo 'Bootstrap OK';"],
                    cwd=str(project_path)
                )
                if result.returncode != 0 or "Bootstrap OK" not in result.stdout:
                    if self.logger:
                        self.logger.error("❌ Laravel bootstrap test failed")
                        self.logger.error(f"STDOUT: {result.stdout}")
                        self.logger.error(f"STDERR: {result.stderr}")
                    return False
                
                if self.logger:
                    self.logger.info("✅ Laravel bootstrap test passed")
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ Laravel bootstrap test error: {e}")
                return False
            
            if self.logger:
                self.logger.info("🎉 Laravel installation verification completed successfully!")
                self.logger.info(f"📋 All essential files present: {essential_files}")
            return True
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Installation verification error: {e}")
            return False
    
    async def _retry_laravel_installation(self, code_path: Path) -> bool:
        """🔥 NEW: Retry Laravel installation if verification fails"""
        try:
            if self.logger:
                self.logger.info("🔄 Retrying Laravel installation...")
            
            # Check what's missing and try to fix it
            essential_files = [
                "artisan", 
                "composer.json", 
                "bootstrap/app.php", 
                "vendor/autoload.php", 
                "config/app.php", 
                "routes/web.php",
                "vendor/laravel/framework"
            ]
            
            missing_files = []
            for file_path in essential_files:
                if not (code_path / file_path).exists():
                    missing_files.append(file_path)
            
            if not missing_files:
                # All files exist, maybe just need to run composer install
                if self.logger:
                    self.logger.info("📦 All files exist, running composer install...")
                
                result = await self.run_command(
                    ["composer", "install", "--no-interaction", "--no-progress"],
                    cwd=str(code_path)
                )
                
                if result.returncode == 0:
                    if self.logger:
                        self.logger.info("✅ Composer install completed")
                    return await self._verify_laravel_installation(code_path)
                else:
                    if self.logger:
                        self.logger.error(f"❌ Composer install failed: {result.stderr}")
                    return False
            
            # If critical files are missing, we need to recreate
            critical_files = ["artisan", "composer.json", "bootstrap/app.php"]
            missing_critical = [f for f in missing_files if f in critical_files]
            
            if missing_critical:
                if self.logger:
                    self.logger.warning(f"⚠️ Critical files missing: {missing_critical}, recreating project...")
                
                # Remove the incomplete project and recreate
                import shutil
                if code_path.exists():
                    shutil.rmtree(code_path)
                
                # Recreate the project
                create_cmd = [
                    "composer", "create-project", 
                    "laravel/laravel", str(code_path),
                    "--prefer-dist", "--no-interaction", "--no-progress"
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *create_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(code_path.parent)
                )
                
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
                
                if process.returncode == 0:
                    if self.logger:
                        self.logger.info("✅ Laravel project recreated successfully")
                    return await self._verify_laravel_installation(code_path)
                else:
                    if self.logger:
                        self.logger.error(f"❌ Laravel project recreation failed: {stderr.decode()}")
                    return False
            
            return False
                        
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Retry Laravel installation error: {e}")
            return False
    
    async def _initialize_laravel_project(self, code_path: Path) -> None:
        """🔥 ENHANCED: Comprehensive Laravel project initialization with detailed logging"""
        try:
            if self.logger:
                self.logger.info("🔧 Initializing Laravel project...")
                self.logger.info(f"📁 Project path: {code_path}")
            
            # 1. Setup .env file
            env_file = code_path / ".env"
            if not env_file.exists():
                env_example = code_path / ".env.example"
                if env_example.exists():
                    # Copy .env.example to .env
                    import shutil
                    shutil.copy2(env_example, env_file)
                    if self.logger:
                        self.logger.info("✅ Created .env from .env.example")
                else:
                    if self.logger:
                        self.logger.warning("⚠️ No .env.example found, creating basic .env")
                    # Create basic .env file
                    env_file.write_text("""APP_NAME=Laravel
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost

LOG_CHANNEL=stack
LOG_LEVEL=debug

DB_CONNECTION=sqlite
DB_DATABASE=database.sqlite

BROADCAST_DRIVER=log
CACHE_DRIVER=file
FILESYSTEM_DISK=local
QUEUE_CONNECTION=sync
SESSION_DRIVER=file
SESSION_LIFETIME=120

MEMCACHED_HOST=127.0.0.1

REDIS_HOST=127.0.0.1
REDIS_PASSWORD=null
REDIS_PORT=6379

MAIL_MAILER=smtp
MAIL_HOST=mailpit
MAIL_PORT=1025
MAIL_USERNAME=null
MAIL_PASSWORD=null
MAIL_ENCRYPTION=null
MAIL_FROM_ADDRESS="hello@example.com"
MAIL_FROM_NAME="${APP_NAME}"

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET=
AWS_USE_PATH_STYLE_ENDPOINT=false

PUSHER_APP_ID=
PUSHER_APP_KEY=
PUSHER_APP_SECRET=
PUSHER_HOST=
PUSHER_PORT=443
PUSHER_SCHEME=https
PUSHER_APP_CLUSTER=mt1

VITE_APP_NAME="${APP_NAME}"
VITE_PUSHER_APP_KEY="${PUSHER_APP_KEY}"
VITE_PUSHER_HOST="${PUSHER_HOST}"
VITE_PUSHER_PORT="${PUSHER_PORT}"
VITE_PUSHER_SCHEME="${PUSHER_SCHEME}"
VITE_PUSHER_APP_CLUSTER="${PUSHER_APP_CLUSTER}"
""")
            else:
                if self.logger:
                    self.logger.info("✅ .env file already exists")
            
            # 2. Generate application key
            try:
                if self.logger:
                    self.logger.info("🔑 Generating application key...")
                result = await self.run_command(
                    ["php", "artisan", "key:generate", "--no-interaction"],
                    cwd=str(code_path)
                )
                if result.returncode == 0:
                    if self.logger:
                        self.logger.info("✅ Generated application key")
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ Key generation failed: {result.stderr}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ Key generation error: {e}")
            
            # 3. Install dev dependencies
            try:
                if self.logger:
                    self.logger.info("📦 Installing dev dependencies (pest, phpstan, pint)...")
                result = await self.run_command(
                    ["composer", "require", "--dev", "--no-interaction", "--no-progress",
                     "pestphp/pest", "phpstan/phpstan", "laravel/pint"],
                    cwd=str(code_path)
                )
                if result.returncode == 0:
                    if self.logger:
                        self.logger.info("✅ Installed dev dependencies (pest, phpstan, pint)")
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ Dev dependencies installation failed: {result.stderr}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ Dev dependencies error: {e}")
            
            # 4. Create storage directories and set permissions
            try:
                if self.logger:
                    self.logger.info("📁 Creating storage and cache directories...")
                storage_dirs = [
                    "storage/app",
                    "storage/framework/cache",
                    "storage/framework/sessions", 
                    "storage/framework/views",
                    "storage/logs",
                    "bootstrap/cache"
                ]
                
                for dir_path in storage_dirs:
                    full_path = code_path / dir_path
                    full_path.mkdir(parents=True, exist_ok=True)
                    if self.logger:
                        self.logger.info(f"✅ Created directory: {dir_path}")
                
                if self.logger:
                    self.logger.info("✅ All storage and cache directories created")
                    
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ Storage directories creation error: {e}")
            
            # 5. Final verification
            try:
                if self.logger:
                    self.logger.info("🧪 Running final verification...")
                result = await self.run_command(
                    ["php", "artisan", "--version"],
                    cwd=str(code_path)
                )
                if result.returncode == 0:
                    if self.logger:
                        self.logger.info(f"🎉 Laravel project initialization completed: {result.stdout.strip()}")
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ Final verification failed: {result.stderr}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"⚠️ Final verification error: {e}")
            
            # 6. Verify essential files are still present
            essential_files = ["artisan", "composer.json", "bootstrap/app.php", "vendor/autoload.php"]
            for file_path in essential_files:
                if (code_path / file_path).exists():
                    if self.logger:
                        self.logger.info(f"✅ Verified: {file_path}")
                else:
                    if self.logger:
                        self.logger.error(f"❌ Missing after initialization: {file_path}")
            
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Laravel initialization error: {e}")
    
    async def _create_enhanced_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """🔥 ENHANCED: Create a more complete Laravel skeleton as fallback"""
        if self.logger:
            self.logger.info("🔧 Creating enhanced Laravel skeleton as fallback...")
            
        # Create complete Laravel directory structure
        dirs = [
            "app/Http/Controllers",
            "app/Http/Middleware", 
            "app/Models", 
            "app/Providers",
            "app/Console/Commands",
            "bootstrap/cache",
            "config",
            "database/migrations",
            "database/seeders",
            "database/factories",
            "public",
            "resources/views",
            "resources/css",
            "resources/js",
            "routes",
            "storage/app",
            "storage/framework/cache",
            "storage/framework/sessions",
            "storage/framework/views",
            "storage/logs",
            "tests/Feature",
            "tests/Unit",
        ]
        
        for d in dirs:
            (code_path / d).mkdir(parents=True, exist_ok=True)

        # Create essential Laravel files
        files = {
            "artisan": self._get_artisan_stub(),
            "composer.json": self._get_composer_json_stub(project_name),
            "bootstrap/app.php": self._get_bootstrap_app_stub(),
            "config/app.php": self._get_config_app_stub(),
            "routes/web.php": self._get_routes_web_stub(),
            "routes/api.php": self._get_routes_api_stub(),
            "app/Http/Kernel.php": self._get_http_kernel_stub(),
            "app/Console/Kernel.php": self._get_console_kernel_stub(),
            "app/Exceptions/Handler.php": self._get_exception_handler_stub(),
            "app/Providers/AppServiceProvider.php": self._get_app_service_provider_stub(),
            ".env.example": self._get_env_example_stub(),
            "phpstan.neon.dist": self._get_phpstan_config_stub(),
            "tests/Pest.php": self._get_pest_config_stub(),
            "tests/Feature/ExampleTest.php": self._get_example_test_stub(),
        }
        
        for fp, content in files.items():
            p = code_path / fp
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            
            # Make artisan executable
            if fp == "artisan":
                os.chmod(p, 0o755)
        
        if self.logger:
            self.logger.info("✅ Enhanced Laravel skeleton created")
    
    def _get_artisan_stub(self) -> str:
        """Get Laravel artisan file content"""
        return '''#!/usr/bin/env php
<?php

define('LARAVEL_START', microtime(true));

require __DIR__.'/vendor/autoload.php';

$app = require_once __DIR__.'/bootstrap/app.php';

$kernel = $app->make(Illuminate\\Contracts\\Console\\Kernel::class);

$status = $kernel->handle(
    $input = new Symfony\\Component\\Console\\Input\\ArgvInput,
    new Symfony\\Component\\Console\\Output\\ConsoleOutput
);

$kernel->terminate($input, $status);

exit($status);
'''

    def _get_composer_json_stub(self, project_name: Optional[str] = None) -> str:
        """Get complete composer.json for Laravel"""
        name = project_name or "emergent/project"
        return f'''{{
    "name": "{name}",
    "type": "project",
    "description": "Laravel application created by Emergent AI",
    "keywords": ["laravel", "framework"],
    "license": "MIT",
    "require": {{
        "php": "^8.1",
        "laravel/framework": "^10.0",
        "laravel/sanctum": "^3.2",
        "laravel/tinker": "^2.8"
    }},
    "require-dev": {{
        "fakerphp/faker": "^1.9.1",
        "laravel/pint": "^1.0",
        "laravel/sail": "^1.18",
        "mockery/mockery": "^1.4.4",
        "nunomaduro/collision": "^7.0",
        "phpunit/phpunit": "^10.1",
        "spatie/laravel-ignition": "^2.0",
        "pestphp/pest": "^2.0",
        "phpstan/phpstan": "^1.0"
    }},
    "autoload": {{
        "psr-4": {{
            "App\\\": "app/",
            "Database\\\\Factories\\\": "database/factories/",
            "Database\\\\Seeders\\\": "database/seeders/"
        }}
    }},
    "autoload-dev": {{
        "psr-4": {{
            "Tests\\\": "tests/"
        }}
    }},
    "scripts": {{
        "post-autoload-dump": [
            "Illuminate\\\\Foundation\\\\ComposerScripts::postAutoloadDump",
            "@php artisan package:discover --ansi"
        ],
        "post-update-cmd": [
            "@php artisan vendor:publish --tag=laravel-assets --ansi --force"
        ],
        "post-root-package-install": [
            "@php -r \"file_exists('.env') || copy('.env.example', '.env');\""
        ],
        "post-create-project-cmd": [
            "@php artisan key:generate --ansi"
        ]
    }},
    "extra": {{
        "laravel": {{
            "dont-discover": []
        }}
    }},
    "config": {{
        "optimize-autoloader": true,
        "preferred-install": "dist",
        "sort-packages": true,
        "allow-plugins": {{
            "pestphp/pest-plugin": true,
            "php-http/discovery": true
        }}
    }},
    "minimum-stability": "stable",
    "prefer-stable": true
}}'''

    def _get_bootstrap_app_stub(self) -> str:
        """Get Laravel bootstrap/app.php content"""
        return '''<?php

use Illuminate\\Foundation\\Application;
use Illuminate\\Foundation\\Configuration\\Exceptions;
use Illuminate\\Foundation\\Configuration\\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        //
    })
    ->withExceptions(function (Exceptions $exceptions) {
        //
    })->create();
'''

    def _get_config_app_stub(self) -> str:
        """Get Laravel config/app.php content"""
        return '''<?php

return [
    'name' => env('APP_NAME', 'Laravel'),
    'env' => env('APP_ENV', 'production'),
    'debug' => (bool) env('APP_DEBUG', false),
    'url' => env('APP_URL', 'http://localhost'),
    'asset_url' => env('ASSET_URL'),
    'timezone' => 'UTC',
    'locale' => 'en',
    'fallback_locale' => 'en',
    'faker_locale' => 'en_US',
    'key' => env('APP_KEY'),
    'cipher' => 'AES-256-CBC',
    'maintenance' => [
        'driver' => 'file',
    ],
    'providers' => [
        Illuminate\\Auth\\AuthServiceProvider::class,
        Illuminate\\Broadcasting\\BroadcastServiceProvider::class,
        Illuminate\\Bus\\BusServiceProvider::class,
        Illuminate\\Cache\\CacheServiceProvider::class,
        Illuminate\\Foundation\\Providers\\ConsoleSupportServiceProvider::class,
        Illuminate\\Cookie\\CookieServiceProvider::class,
        Illuminate\\Database\\DatabaseServiceProvider::class,
        Illuminate\\Encryption\\EncryptionServiceProvider::class,
        Illuminate\\Filesystem\\FilesystemServiceProvider::class,
        Illuminate\\Foundation\\Providers\\FoundationServiceProvider::class,
        Illuminate\\Hashing\\HashServiceProvider::class,
        Illuminate\\Mail\\MailServiceProvider::class,
        Illuminate\\Notifications\\NotificationServiceProvider::class,
        Illuminate\\Pagination\\PaginationServiceProvider::class,
        Illuminate\\Pipeline\\PipelineServiceProvider::class,
        Illuminate\\Queue\\QueueServiceProvider::class,
        Illuminate\\Redis\\RedisServiceProvider::class,
        Illuminate\\Auth\\Passwords\\PasswordResetServiceProvider::class,
        Illuminate\\Session\\SessionServiceProvider::class,
        Illuminate\\Translation\\TranslationServiceProvider::class,
        Illuminate\\Validation\\ValidationServiceProvider::class,
        Illuminate\\View\\ViewServiceProvider::class,
        App\\Providers\\AppServiceProvider::class,
    ],
    'aliases' => [
        'App' => Illuminate\\Support\\Facades\\App::class,
        'Arr' => Illuminate\\Support\\Arr::class,
        'Artisan' => Illuminate\\Support\\Facades\\Artisan::class,
        'Auth' => Illuminate\\Support\\Facades\\Auth::class,
        'Blade' => Illuminate\\Support\\Facades\\Blade::class,
        'Broadcast' => Illuminate\\Support\\Facades\\Broadcast::class,
        'Bus' => Illuminate\\Support\\Facades\\Bus::class,
        'Cache' => Illuminate\\Support\\Facades\\Cache::class,
        'Config' => Illuminate\\Support\\Facades\\Config::class,
        'Cookie' => Illuminate\\Support\\Facades\\Cookie::class,
        'Crypt' => Illuminate\\Support\\Facades\\Crypt::class,
        'Date' => Illuminate\\Support\\Facades\\Date::class,
        'DB' => Illuminate\\Support\\Facades\\DB::class,
        'Eloquent' => Illuminate\\Database\\Eloquent\\Model::class,
        'Event' => Illuminate\\Support\\Facades\\Event::class,
        'File' => Illuminate\\Support\\Facades\\File::class,
        'Gate' => Illuminate\\Support\\Facades\\Gate::class,
        'Hash' => Illuminate\\Support\\Facades\\Hash::class,
        'Http' => Illuminate\\Support\\Facades\\Http::class,
        'Js' => Illuminate\\Support\\Js::class,
        'Lang' => Illuminate\\Support\\Facades\\Lang::class,
        'Log' => Illuminate\\Support\\Facades\\Log::class,
        'Mail' => Illuminate\\Support\\Facades\\Mail::class,
        'Notification' => Illuminate\\Support\\Facades\\Notification::class,
        'Password' => Illuminate\\Support\\Facades\\Password::class,
        'Process' => Illuminate\\Support\\Facades\\Process::class,
        'Queue' => Illuminate\\Support\\Facades\\Queue::class,
        'RateLimiter' => Illuminate\\Support\\Facades\\RateLimiter::class,
        'Redirect' => Illuminate\\Support\\Facades\\Redirect::class,
        'Request' => Illuminate\\Support\\Facades\\Request::class,
        'Response' => Illuminate\\Support\\Facades\\Response::class,
        'Route' => Illuminate\\Support\\Facades\\Route::class,
        'Schema' => Illuminate\\Support\\Facades\\Schema::class,
        'Session' => Illuminate\\Support\\Facades\\Session::class,
        'Storage' => Illuminate\\Support\\Facades\\Storage::class,
        'Str' => Illuminate\\Support\\Str::class,
        'URL' => Illuminate\\Support\\Facades\\URL::class,
        'Validator' => Illuminate\\Support\\Facades\\Validator::class,
        'View' => Illuminate\\Support\\Facades\\View::class,
        'Vite' => Illuminate\\Support\\Facades\\Vite::class,
    ],
];
'''

    def _get_routes_web_stub(self) -> str:
        """Get Laravel routes/web.php content"""
        return '''<?php

use Illuminate\\Support\\Facades\\Route;

Route::get('/', function () {
    return view('welcome');
});
'''

    def _get_routes_api_stub(self) -> str:
        """Get Laravel routes/api.php content"""
        return '''<?php

use Illuminate\\Http\\Request;
use Illuminate\\Support\\Facades\\Route;

Route::get('/user', function (Request $request) {
    return $request->user();
})->middleware('auth:sanctum');
'''

    def _get_http_kernel_stub(self) -> str:
        """Get Laravel HTTP Kernel content"""
        return '''<?php

namespace App\\Http;

use Illuminate\\Foundation\\Http\\Kernel as HttpKernel;

class Kernel extends HttpKernel
{
    protected $middleware = [
        // \\App\\Http\\Middleware\\TrustHosts::class,
        \\App\\Http\\Middleware\\TrustProxies::class,
        \\Illuminate\\Http\\Middleware\\HandleCors::class,
        \\App\\Http\\Middleware\\PreventRequestsDuringMaintenance::class,
        \\Illuminate\\Foundation\\Http\\Middleware\\ValidatePostSize::class,
        \\App\\Http\\Middleware\\TrimStrings::class,
        \\Illuminate\\Foundation\\Http\\Middleware\\ConvertEmptyStringsToNull::class,
    ];

    protected $middlewareGroups = [
        'web' => [
            \\App\\Http\\Middleware\\EncryptCookies::class,
            \\Illuminate\\Cookie\\Middleware\\AddQueuedCookiesToResponse::class,
            \\Illuminate\\Session\\Middleware\\StartSession::class,
            \\Illuminate\\View\\Middleware\\ShareErrorsFromSession::class,
            \\App\\Http\\Middleware\\VerifyCsrfToken::class,
            \\Illuminate\\Routing\\Middleware\\SubstituteBindings::class,
        ],

        'api' => [
            // \\Laravel\\Sanctum\\Http\\Middleware\\EnsureFrontendRequestsAreStateful::class,
            \\Illuminate\\Routing\\Middleware\\ThrottleRequests::class.':api',
            \\Illuminate\\Routing\\Middleware\\SubstituteBindings::class,
        ],
    ];

    protected $middlewareAliases = [
        'auth' => \\App\\Http\\Middleware\\Authenticate::class,
        'auth.basic' => \\Illuminate\\Auth\\Middleware\\AuthenticateWithBasicAuth::class,
        'auth.session' => \\Illuminate\\Session\\Middleware\\AuthenticateSession::class,
        'cache.headers' => \\Illuminate\\Http\\Middleware\\SetCacheHeaders::class,
        'can' => \\Illuminate\\Auth\\Middleware\\Authorize::class,
        'guest' => \\App\\Http\\Middleware\\RedirectIfAuthenticated::class,
        'password.confirm' => \\Illuminate\\Auth\\Middleware\\RequirePassword::class,
        'signed' => \\App\\Http\\Middleware\\ValidateSignature::class,
        'throttle' => \\Illuminate\\Routing\\Middleware\\ThrottleRequests::class,
        'verified' => \\Illuminate\\Auth\\Middleware\\EnsureEmailIsVerified::class,
    ];
}
'''

    def _get_console_kernel_stub(self) -> str:
        """Get Laravel Console Kernel content"""
        return '''<?php

namespace App\\Console;

use Illuminate\\Console\\Scheduling\\Schedule;
use Illuminate\\Foundation\\Console\\Kernel as ConsoleKernel;

class Kernel extends ConsoleKernel
{
    protected $commands = [
        //
    ];

    protected function schedule(Schedule $schedule): void
    {
        // $schedule->command('inspire')->hourly();
    }

    protected function commands(): void
    {
        $this->load(__DIR__.'/Commands');

        require base_path('routes/console.php');
    }
}
'''

    def _get_exception_handler_stub(self) -> str:
        """Get Laravel Exception Handler content"""
        return '''<?php

namespace App\\Exceptions;

use Illuminate\\Foundation\\Exceptions\\Handler as ExceptionHandler;
use Throwable;

class Handler extends ExceptionHandler
{
    protected $dontReport = [
        //
    ];

    protected $dontFlash = [
        'current_password',
        'password',
        'password_confirmation',
    ];

    public function register(): void
    {
        $this->reportable(function (Throwable $e) {
            //
        });
    }
}
'''

    def _get_app_service_provider_stub(self) -> str:
        """Get Laravel App Service Provider content"""
        return '''<?php

namespace App\\Providers;

use Illuminate\\Support\\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        //
    }
}
'''

    def _get_env_example_stub(self) -> str:
        """Get Laravel .env.example content"""
        return '''APP_NAME=Laravel
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost

LOG_CHANNEL=stack
LOG_DEPRECATIONS_CHANNEL=null
LOG_LEVEL=debug

DB_CONNECTION=sqlite
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=database.sqlite
DB_USERNAME=root
DB_PASSWORD=

BROADCAST_DRIVER=log
CACHE_DRIVER=file
FILESYSTEM_DISK=local
QUEUE_CONNECTION=sync
SESSION_DRIVER=file
SESSION_LIFETIME=120

MEMCACHED_HOST=127.0.0.1

REDIS_HOST=127.0.0.1
REDIS_PASSWORD=null
REDIS_PORT=6379

MAIL_MAILER=smtp
MAIL_HOST=mailpit
MAIL_PORT=1025
MAIL_USERNAME=null
MAIL_PASSWORD=null
MAIL_ENCRYPTION=null
MAIL_FROM_ADDRESS="hello@example.com"
MAIL_FROM_NAME="${APP_NAME}"

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
AWS_BUCKET=
AWS_USE_PATH_STYLE_ENDPOINT=false

PUSHER_APP_ID=
PUSHER_APP_KEY=
PUSHER_APP_SECRET=
PUSHER_HOST=
PUSHER_PORT=443
PUSHER_SCHEME=https
PUSHER_APP_CLUSTER=mt1

VITE_APP_NAME="${APP_NAME}"
VITE_PUSHER_APP_KEY="${PUSHER_APP_KEY}"
VITE_PUSHER_HOST="${PUSHER_HOST}"
VITE_PUSHER_PORT="${PUSHER_PORT}"
VITE_PUSHER_SCHEME="${PUSHER_SCHEME}"
VITE_PUSHER_APP_CLUSTER="${PUSHER_APP_CLUSTER}"
'''

    def _get_phpstan_config_stub(self) -> str:
        """Get PHPStan configuration content"""
        return '''parameters:
    paths:
        - app
    level: 5
    ignoreErrors:
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Builder#'
        - '#Call to an undefined method Illuminate\\\\Database\\\\Eloquent\\\\Collection#'
    excludePaths:
        - 'vendor/*'
        - 'bootstrap/cache/*'
        - 'storage/*'
'''

    def _get_pest_config_stub(self) -> str:
        """Get Pest configuration content"""
        return '''<?php

use Tests\\TestCase;
use Illuminate\\Foundation\\Testing\\RefreshDatabase;

uses(TestCase::class, RefreshDatabase::class)->in('Feature');
uses(TestCase::class)->in('Unit');
'''

    def _get_example_test_stub(self) -> str:
        """Get example Pest test content"""
        return '''<?php

test('application returns a successful response', function () {
    $response = $this->get('/');
    $response->assertStatus(200);
});

test('basic example', function () {
    expect(true)->toBeTrue();
});
'''

    async def install_dependencies(self, code_path: Path) -> bool:
        # sanitize composer.json if exists
        composer_file = code_path / "composer.json"
        if composer_file.exists():
            try:
                composer_data = json.loads(composer_file.read_text())
                original_name = composer_data.get("name")
                corrected = self.sanitize_composer_name(original_name)
                if original_name != corrected:
                    composer_data["name"] = corrected
                    composer_file.write_text(json_utils.dumps(composer_data, indent=2))
                    if self.logger:
                        self.logger.info(f"Sanitized composer name: {original_name!r} -> {corrected!r}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error sanitizing composer.json: {e}")
        
        # 🔥 FIXED: composer install with proper flags to avoid hanging
        result = await self.run_command(
            ["composer", "install", "--no-interaction", "--no-progress", "--prefer-dist"], 
            cwd=str(code_path)
        )
        if result.returncode != 0 and self.logger:
            self.logger.warning(f"Composer install failed: {result.stderr}")
        
        # 🔥 FIXED: dev deps with non-interactive flags
        dev = await self.run_command(
            ["composer", "require", "--dev", "--no-interaction", 
             "phpstan/phpstan", "laravel/pint", "pestphp/pest"],
            cwd=str(code_path)
        )
        if dev.returncode != 0 and self.logger:
            self.logger.warning(f"Laravel dev deps failed: {dev.stderr}")
        
        return True

# auto-register
StackRegistry.register(LaravelHandler.name, LaravelHandler)
