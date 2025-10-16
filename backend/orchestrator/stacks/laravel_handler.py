# stacks/laravel_handler.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import json
import re
import os
import asyncio

from .base_handler import StackHandler
from .registry import StackRegistry
from ..utils import json_utils

class LaravelHandler(StackHandler):
    name = "laravel"
    # 🔥 FIXED: Pest test command without --no-interaction (unsupported)
    default_test_command: List[str] = ["vendor/bin/pest", "--stop-on-failure"]

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

    async def _detect_php_version(self, code_path: Path) -> Optional[str]:
        """🔍 Detect PHP version dynamically"""
        try:
            result = await self.run_command(["php", "-v"], cwd=str(code_path))
            if result.returncode == 0 and result.stdout:
                # Extract PHP version from output like "PHP 8.3.26 (cli) ..."
                import re
                match = re.search(r'PHP (\d+\.\d+)', result.stdout)
                if match:
                    version = match.group(1)
                    if self.logger:
                        self.logger.info(f"🔍 Detected PHP version: {version}")
                    return version
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Failed to detect PHP version: {e}")
        return None

    async def _detect_laravel_version(self, code_path: Path) -> Optional[str]:
        """🔍 Detect Laravel framework version dynamically"""
        try:
            result = await self.run_command(
                ["composer", "show", "laravel/framework", "--format=json"],
                cwd=str(code_path)
            )
            if result.returncode == 0 and result.stdout:
                import json
                data = json.loads(result.stdout)
                version = data.get('versions', [None])[0]
                if version:
                    if self.logger:
                        self.logger.info(f"🔍 Detected Laravel version: {version}")
                    return version
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Failed to detect Laravel version: {e}")
        return None

    def _get_compatible_dev_dependencies(self, php_version: Optional[str] = None, laravel_version: Optional[str] = None) -> dict:
        """🧠 Get compatible dev dependency versions based on PHP/Laravel versions"""
        
        # Default versions (stable and compatible with Laravel 12 + PHP 8.3)
        defaults = {
            "pestphp/pest": "^3.8",
            "phpstan/phpstan": "^2.0", 
            "laravel/pint": "^1.14"
        }
        
        if self.logger:
            self.logger.info(f"🧠 Determining compatible versions for PHP {php_version or 'unknown'}, Laravel {laravel_version or 'unknown'}")
        
        # Matrix de compatibilité basée sur les versions détectées
        compatibility_matrix = {
            # PHP 8.3 + Laravel 12.x
            ("8.3", "12"): {
                "pestphp/pest": "^3.8",  # Compatible avec PHPUnit 11.x
                "phpstan/phpstan": "^2.0",  # Dernière version stable
                "laravel/pint": "^1.17"     # Version optimisée pour Laravel 12
            },
            # PHP 8.2 + Laravel 12.x
            ("8.2", "12"): {
                "pestphp/pest": "^3.6",
                "phpstan/phpstan": "^1.12",
                "laravel/pint": "^1.14"
            },
            # PHP 8.1 + Laravel 11.x
            ("8.1", "11"): {
                "pestphp/pest": "^3.0",
                "phpstan/phpstan": "^1.10",
                "laravel/pint": "^1.10"
            },
            # PHP 8.3 + Laravel 11.x (rétrocompatibilité)
            ("8.3", "11"): {
                "pestphp/pest": "^3.5",
                "phpstan/phpstan": "^1.12",
                "laravel/pint": "^1.13"
            }
        }
        
        # Essayer de trouver une correspondance exacte
        if php_version and laravel_version:
            php_major_minor = php_version  # e.g., "8.3"
            laravel_major = laravel_version.split('.')[0] if laravel_version else None  # e.g., "12"
            
            key = (php_major_minor, laravel_major)
            if key in compatibility_matrix:
                selected = compatibility_matrix[key]
                if self.logger:
                    self.logger.info(f"🎯 Found exact match for PHP {php_major_minor} + Laravel {laravel_major}: {selected}")
                return selected
        
        # Fallback basé sur PHP uniquement
        if php_version:
            if php_version.startswith("8.3"):
                fallback = {
                    "pestphp/pest": "^3.8",
                    "phpstan/phpstan": "^2.0",
                    "laravel/pint": "^1.17"
                }
            elif php_version.startswith("8.2"):
                fallback = {
                    "pestphp/pest": "^3.6",
                    "phpstan/phpstan": "^1.12", 
                    "laravel/pint": "^1.14"
                }
            elif php_version.startswith("8.1"):
                fallback = {
                    "pestphp/pest": "^3.0",
                    "phpstan/phpstan": "^1.10",
                    "laravel/pint": "^1.10"
                }
            else:
                fallback = defaults
            
            if self.logger:
                self.logger.info(f"🔄 Using PHP-based fallback for {php_version}: {fallback}")
            return fallback
        
        # Dernier recours: versions par défaut
        if self.logger:
            self.logger.info(f"🔄 Using default versions: {defaults}")
        return defaults

    async def _install_dev_dependencies_intelligent(self, code_path: Path) -> None:
        """🚀 Install development dependencies with intelligent version detection"""
        try:
            if self.logger:
                self.logger.info("🧠 Starting intelligent dev dependencies installation...")
            
            # Étape 1: Détecter les versions
            php_version = await self._detect_php_version(code_path)
            laravel_version = await self._detect_laravel_version(code_path)
            
            if self.logger:
                self.logger.info(f"📊 Environment detected: PHP {php_version or 'unknown'}, Laravel {laravel_version or 'unknown'}")
            
            # Étape 2: Obtenir les versions compatibles
            dependencies = self._get_compatible_dev_dependencies(php_version, laravel_version)
            
            # Étape 3: Construire la commande composer
            composer_packages = [f"{pkg}:{version}" for pkg, version in dependencies.items()]
            composer_cmd = [
                "composer", "require", "--dev", 
                "--no-interaction", "--no-progress", "--with-all-dependencies"
            ] + composer_packages
            
            if self.logger:
                self.logger.info(f"📦 Installing dev dependencies: {' '.join(composer_packages)}")
                self.logger.info(f"🔧 Command: {' '.join(composer_cmd)}")
            
            # Étape 4: Exécuter l'installation
            result = await self.run_command(composer_cmd, cwd=str(code_path))
            
            if result.returncode == 0:
                if self.logger:
                    self.logger.info("✅ Dev dependencies installed successfully")
                    self.logger.info(f"📋 Installed packages: {list(dependencies.keys())}")
                
                # Étape 5: Vérifier les versions exactes installées
                await self._log_installed_versions(code_path, dependencies.keys())
                
            else:
                if self.logger:
                    self.logger.warning(f"⚠️ Dev dependency installation failed: {result.stderr}")
                    self.logger.warning(f"💡 Attempted command: {' '.join(composer_cmd)}")
                    self.logger.warning("🔄 Continuing with Laravel project creation...")
        
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Dev dependencies installation error: {e}")
                self.logger.warning("🔄 Continuing with Laravel project creation...")

    async def _log_installed_versions(self, code_path: Path, package_names: list) -> None:
        """📋 Log the exact versions of installed dev dependencies"""
        try:
            if self.logger:
                self.logger.info("📋 Checking installed dev dependency versions...")
            
            for package in package_names:
                try:
                    result = await self.run_command(
                        ["composer", "show", package, "--format=json"],
                        cwd=str(code_path)
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        import json
                        data = json.loads(result.stdout)
                        version = data.get('versions', [None])[0]
                        if version and self.logger:
                            self.logger.info(f"✅ {package}: {version}")
                    else:
                        if self.logger:
                            self.logger.warning(f"⚠️ Could not verify version for {package}")
                
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"⚠️ Error checking {package} version: {e}")
        
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Error logging installed versions: {e}")

    async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
        """
        🚀 Create a REAL Laravel 12 project using the official composer installation process.
        Based on: https://laravel.com/docs/12.x/installation
        """
        import subprocess
        import shutil

        try:
            if self.logger:
                self.logger.info(f"🚀 Starting official Laravel installation at: {code_path}")

            # Clean target directory if it already exists
            if code_path.exists():
                if self.logger:
                    self.logger.info("🧹 Removing existing directory before installation...")
                shutil.rmtree(code_path)

            code_path.parent.mkdir(parents=True, exist_ok=True)

            # 1️⃣ Install Laravel via Composer (official method)
            create_cmd = [
                "composer", "create-project",
                "laravel/laravel", str(code_path),
                "--prefer-dist", "--no-interaction", "--no-progress"
            ]

            if self.logger:
                self.logger.info("📦 Running: " + " ".join(create_cmd))

            process = await asyncio.create_subprocess_exec(
                *create_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(code_path.parent)
            )

            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=900)

            if process.returncode != 0:
                raise Exception(f"Composer installation failed:\n{stderr.decode()}")

            if self.logger:
                self.logger.info("✅ Laravel installed successfully via Composer")
                self.logger.info(stdout.decode())

            # 2️⃣ Generate application key
            if self.logger:
                self.logger.info("🔑 Generating application key...")
            keygen = await self.run_command(
                ["php", "artisan", "key:generate", "--no-interaction"],
                cwd=str(code_path)
            )
            if keygen.returncode != 0:
                raise Exception(f"Failed to generate app key: {keygen.stderr}")

            # 3️⃣ Install optional developer tools (PHPStan, Pest, Pint) with intelligent version detection
            await self._install_dev_dependencies_intelligent(code_path)

            # 4️⃣ Install Vite and build assets (Laravel 12+ requirement)
            await self._install_and_build_vite(code_path)

            # 5️⃣ Create fallback CSS in public/css for compatibility
            await self._create_fallback_public_css(code_path)

            # 6️⃣ Verify the installation
            if not await self._verify_laravel_installation(code_path):
                raise Exception("❌ Laravel installation verification failed")

            if self.logger:
                self.logger.info("🎉 Laravel 12 project is ready and verified!")

        except asyncio.TimeoutError:
            raise Exception("Laravel installation timed out after 15 minutes.")
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Laravel installation failed: {e}")
            raise
    
    async def _install_and_build_vite(self, code_path: Path) -> None:
        """
        ⚡ Install Vite dependencies and build assets for Laravel 12+
        
        Laravel 12 uses Vite by default for asset compilation. This method:
        1. Checks if package.json exists (should exist in fresh Laravel install)
        2. Installs npm dependencies (including vite and laravel-vite-plugin)
        3. Runs npm run build to compile assets to public/build/
        
        This ensures @vite() directive in Blade templates works immediately.
        """
        try:
            package_json = code_path / "package.json"
            
            if not package_json.exists():
                if self.logger:
                    self.logger.warning("⚠️ package.json not found, skipping Vite setup")
                return
            
            # Check if npm is available
            npm_check = await self.run_command(["which", "npm"], cwd=str(code_path))
            if npm_check.returncode != 0:
                if self.logger:
                    self.logger.warning("⚠️ npm not found, skipping Vite setup")
                return
            
            if self.logger:
                self.logger.info("📦 Installing npm dependencies (Vite + Laravel Vite Plugin)...")
            
            # Install npm dependencies
            npm_install = await self.run_command(
                ["npm", "install"],
                cwd=str(code_path),
                timeout=180  # 3 minutes for npm install
            )
            
            if npm_install.returncode != 0:
                if self.logger:
                    self.logger.warning(f"⚠️ npm install failed: {npm_install.stderr}")
                    self.logger.info("Continuing without Vite build...")
                return
            
            if self.logger:
                self.logger.info("✅ npm dependencies installed")
                self.logger.info("🔨 Building Vite assets (npm run build)...")
            
            # Build Vite assets
            npm_build = await self.run_command(
                ["npm", "run", "build"],
                cwd=str(code_path),
                timeout=180  # 3 minutes for build
            )
            
            if npm_build.returncode != 0:
                if self.logger:
                    self.logger.warning(f"⚠️ npm run build failed: {npm_build.stderr}")
                    self.logger.info("Continuing without Vite build (fallback CSS will be used)...")
                return
            
            # Verify build output
            build_dir = code_path / "public" / "build"
            manifest_file = build_dir / "manifest.json"
            
            if manifest_file.exists():
                if self.logger:
                    self.logger.info(f"✅ Vite assets built successfully at {build_dir}")
                    self.logger.info("✅ @vite() directive will work in Blade templates")
            else:
                if self.logger:
                    self.logger.warning("⚠️ Vite build completed but manifest.json not found")
            
        except asyncio.TimeoutError:
            if self.logger:
                self.logger.warning("⚠️ Vite installation/build timed out, continuing without it...")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Could not install/build Vite: {e}")
                self.logger.info("Continuing without Vite (fallback CSS will be used)...")
            # Non-blocking - don't fail the installation for this
    
    
    async def _create_fallback_public_css(self, code_path: Path) -> None:
        """
        🎨 Create fallback CSS in public/css/app.css
        
        This ensures compatibility when views use {{ asset('css/app.css') }}
        instead of the modern @vite() directive.
        
        The CSS is copied from resources/css/app.css if it exists,
        or a minimal default stylesheet is created.
        """
        try:
            resources_css = code_path / "resources" / "css" / "app.css"
            public_css_dir = code_path / "public" / "css"
            public_css_file = public_css_dir / "app.css"
            
            # Create public/css directory
            public_css_dir.mkdir(parents=True, exist_ok=True)
            
            if resources_css.exists():
                # Copy from resources/css/app.css
                import shutil
                shutil.copy2(resources_css, public_css_file)
                if self.logger:
                    self.logger.info(f"✅ Copied {resources_css} → {public_css_file}")
            else:
                # Create minimal default CSS
                default_css = """/* Laravel Auto-Generated Fallback CSS */
/* This file provides basic styling when @vite() directive is not used */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    background-color: #f8f9fa;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    padding: 30px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

h1, h2, h3, h4, h5, h6 {
    margin-bottom: 20px;
    color: #2c3e50;
    font-weight: 600;
}

h1 { font-size: 2.5rem; }
h2 { font-size: 2rem; }
h3 { font-size: 1.5rem; }

p {
    margin-bottom: 15px;
}

a {
    color: #3490dc;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* Forms */
form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

label {
    font-weight: 600;
    margin-bottom: 5px;
    display: block;
    color: #374151;
}

input[type="text"],
input[type="email"],
input[type="password"],
input[type="number"],
input[type="tel"],
input[type="url"],
textarea,
select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    font-size: 14px;
    transition: border-color 0.2s, box-shadow 0.2s;
}

input:focus,
textarea:focus,
select:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

textarea {
    min-height: 100px;
    resize: vertical;
}

/* Buttons */
button,
.btn {
    background-color: #3b82f6;
    color: white;
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 16px;
    font-weight: 600;
    transition: background-color 0.2s;
    display: inline-block;
}

button:hover,
.btn:hover {
    background-color: #2563eb;
}

button[type="submit"] {
    background-color: #10b981;
}

button[type="submit"]:hover {
    background-color: #059669;
}

button:disabled {
    background-color: #9ca3af;
    cursor: not-allowed;
}

/* Alerts */
.alert {
    padding: 15px 20px;
    border-radius: 6px;
    margin-bottom: 20px;
    border-left: 4px solid;
}

.alert-success {
    background-color: #d1fae5;
    color: #065f46;
    border-left-color: #10b981;
}

.alert-error,
.alert-danger {
    background-color: #fee2e2;
    color: #991b1b;
    border-left-color: #ef4444;
}

.alert-warning {
    background-color: #fef3c7;
    color: #92400e;
    border-left-color: #f59e0b;
}

.alert-info {
    background-color: #dbeafe;
    color: #1e40af;
    border-left-color: #3b82f6;
}

/* Tables */
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}

th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #e5e7eb;
}

th {
    background-color: #f3f4f6;
    font-weight: 600;
    color: #374151;
}

tr:hover {
    background-color: #f9fafb;
}

/* Cards */
.card {
    background: white;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 20px;
    margin-bottom: 20px;
}

.card-title {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 10px;
}

/* Utilities */
.text-center { text-align: center; }
.text-right { text-align: right; }
.mt-20 { margin-top: 20px; }
.mb-20 { margin-bottom: 20px; }
.hidden { display: none; }

/* Responsive */
@media (max-width: 768px) {
    body {
        padding: 10px;
    }
    
    .container {
        padding: 15px;
    }
    
    h1 { font-size: 2rem; }
    h2 { font-size: 1.5rem; }
}
"""
            public_css_file.write_text(default_css)
            if self.logger:
                self.logger.info(f"✅ Created default fallback CSS at {public_css_file}")
    
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ Could not create fallback CSS: {e}")
            # Non-blocking - don't fail the installation for this

    
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
            except Exception:
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
        """
        Get Laravel routes/web.php content
        🔥 PHASE 4: Route / with intelligent fallback
        """
        return '''<?php

use Illuminate\\Support\\Facades\\Route;

Route::get('/', function () {
    // 🔥 PHASE 4: Try views created by steps first, then fallback to welcome
    // Order: home → index → welcome
    if (view()->exists('home')) {
        return view('home');
    } elseif (view()->exists('index')) {
        return view('index');
    } elseif (view()->exists('welcome')) {
        return view('welcome');
    }
    
    // Final fallback: basic response
    return response()->view('welcome', [], 200);
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
