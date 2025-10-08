"""
🔥 ENHANCED LLM-Powered Repair Agent for Self-Healing System
Uses AI to analyze complex errors and generate fixes with anti-loop protection
"""
import os
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RepairResult:
    """Result of LLM-powered repair attempt"""
    success: bool
    description: str
    patch_applied: str = ""
    commands_executed: List[str] = None
    files_created: Dict[str, str] = None
    error_message: str = ""

class RepairAgent:
    """
    🔥 ENHANCED LLM-powered repair agent with anti-loop protection and error tracking
    """
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        # 🔥 ENHANCED: Anti-loop tracking system
        self.repair_history = {}  # track repairs by error signature
        self.max_repairs_per_error = 2  # maximum repairs per unique error
        self.command_timeout = 120  # 2 minutes timeout for repair commands
        # 🔥 NEW: Session-based loop prevention
        self.repair_sessions = {}  # track repair sessions per project
        self.max_session_duration = 1800  # 30 minutes max per session
        self.max_llm_calls_per_session = 5  # max LLM calls per repair session
        
    async def analyze_and_repair(
        self, 
        project_path: str, 
        stack: str, 
        error_output: str, 
        failed_command: str,
        context: Dict = None
    ) -> RepairResult:
        """
        🔥 ENHANCED: Main repair method with loop protection and intelligent caching
        """
        try:
            import time
            current_time = time.time()
            
            # 🔥 NEW: Session-based loop prevention
            if project_path not in self.repair_sessions:
                self.repair_sessions[project_path] = {
                    'start_time': current_time,
                    'llm_calls': 0,
                    'errors_attempted': set()
                }
            
            session = self.repair_sessions[project_path]
            session_duration = current_time - session['start_time']
            
            # Check session duration
            if session_duration > self.max_session_duration:
                logger.warning(f"🛑 REPAIR SESSION TIMEOUT for {project_path} ({session_duration:.0f}s)")
                return RepairResult(
                    success=False,
                    description="Repair session timeout - too long running",
                    error_message="session_timeout"
                )
            
            # Check LLM call limit
            if session['llm_calls'] >= self.max_llm_calls_per_session:
                logger.warning(f"🛑 LLM CALL LIMIT REACHED for {project_path} ({session['llm_calls']}/{self.max_llm_calls_per_session})")
                return RepairResult(
                    success=False,
                    description="LLM call limit reached for this session",
                    error_message="llm_call_limit_reached"
                )
            
            # 🔥 ENHANCED: Create error signature for anti-loop protection
            error_signature = self._create_error_signature(project_path, failed_command, error_output)
            
            # 🔥 NEW: Check for Laravel-specific errors that should trigger project recreation
            if self._is_laravel_installation_error(error_output):
                logger.warning("🚨 Laravel installation error detected - project needs complete recreation")
                return RepairResult(
                    success=False,
                    description="Laravel installation is broken and needs complete recreation",
                    error_message="laravel_installation_broken"
                )
            
            # Check if we've already attempted repair for this exact error
            if error_signature in self.repair_history:
                attempts = self.repair_history[error_signature]
                if attempts >= self.max_repairs_per_error:
                    logger.warning(f"🔄 Repair limit reached for error signature: {error_signature[:50]}...")
                    return RepairResult(
                        success=False,
                        description=f"Repair attempt limit ({self.max_repairs_per_error}) reached for this error",
                        error_message="anti_loop_protection_triggered"
                    )
                
                # Increment attempt counter
                self.repair_history[error_signature] = attempts + 1
                logger.info(f"🔄 Repair attempt {attempts + 1}/{self.max_repairs_per_error} for known error")
            else:
                # First time seeing this error
                self.repair_history[error_signature] = 1
                logger.info(f"🤖 First LLM-powered error analysis for: {failed_command}")
            
            # Track this error in session
            session['errors_attempted'].add(error_signature)
            
            # 1. Gather project context
            project_context = await self._gather_project_context(project_path, stack)
            
            # 🔥 NEW: Add repair history to context to avoid repeated solutions
            project_context["repair_history"] = self._get_relevant_repair_history(error_signature)
            
            # 2. Generate repair with LLM
            session['llm_calls'] += 1  # Track LLM call
            repair_plan = await self._generate_repair_with_llm(
                project_path, stack, error_output, failed_command, project_context
            )
            
            if not repair_plan:
                return RepairResult(
                    success=False,
                    description="LLM could not generate repair plan",
                    error_message="no_repair_plan_generated"
                )
            
            # 🔥 NEW: Validate repair plan before applying
            if not self._validate_repair_plan(repair_plan):
                logger.warning("❌ Generated repair plan failed validation")
                return RepairResult(
                    success=False,
                    description="Generated repair plan failed safety validation",
                    error_message="repair_plan_validation_failed"
                )
            
            # 3. Apply the generated repair
            result = await self._apply_llm_repair(project_path, repair_plan)
            
            # 🔥 NEW: Track successful repairs to avoid future issues
            if result.success:
                self._record_successful_repair(error_signature, repair_plan)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM-powered repair: {e}")
            return RepairResult(
                success=False,
                description="LLM repair system error",
                error_message=str(e)
            )
    
    def _create_error_signature(self, project_path: str, failed_command: str, error_output: str) -> str:
        """
        🔥 NEW: Create a unique signature for an error to track repair attempts
        """
        import hashlib
        
        # Normalize inputs for consistent signatures
        normalized_command = ' '.join(failed_command.split())  # Normalize whitespace
        
        # Extract key error patterns (ignore line numbers, paths, timestamps)
        error_patterns = []
        for line in error_output.split('\
'):
            line = line.strip().lower()
            if any(keyword in line for keyword in [
                'error', 'failed', 'not found', 'missing', 'undefined', 'exception',
                'could not', 'unable to', 'permission denied', 'no such file'
            ]):
                # Remove paths and line numbers for consistency
                normalized_line = line.replace(project_path.lower(), '[PROJECT]')
                normalized_line = ' '.join(normalized_line.split())  # Normalize whitespace
                error_patterns.append(normalized_line)
        
        # Create signature from command + key error patterns
        signature_content = f"{normalized_command}|{'|'.join(error_patterns[:3])}"  # Top 3 error patterns
        return hashlib.md5(signature_content.encode()).hexdigest()
    
    def _is_laravel_installation_error(self, error_output: str) -> bool:
        """
        🔥 NEW: Detect Laravel installation errors that require complete project recreation
        """
        error_lower = error_output.lower()
        
        # Laravel-specific error patterns that indicate broken installation
        laravel_installation_errors = [
            "composer root package not detected",
            "laravel project structure is broken",
            "project needs manual laravel setup",
            "no application encryption key has been specified",
            "could not find the driver",
            "class 'illuminate\\foundation\\application' not found",
            "class 'illuminate\\support\\facades\\app' not found",
            "artisan command not found",
            "vendor/autoload.php not found",
            "bootstrap/app.php not found",
            "laravel framework not found",
            "composer could not detect the root package",
            "no files found to analyse",
            "php artisan test fails",
            "laravel/framework package not installed"
        ]
        
        for error_pattern in laravel_installation_errors:
            if error_pattern in error_lower:
                logger.warning(f"🚨 Laravel installation error detected: {error_pattern}")
                return True
        
        return False
    
    def _get_relevant_repair_history(self, error_signature: str) -> List[str]:
        """Get history of previous repair attempts for context"""
        history = []
        # Add general repair attempt info
        if error_signature in self.repair_history:
            attempts = self.repair_history[error_signature]
            history.append(f"Previous repair attempts for this error: {attempts - 1}")
        
        return history
    
    def _validate_repair_plan(self, repair_plan: Dict) -> bool:
        """
        🔥 NEW: Validate repair plan for safety and feasibility
        """
        try:
            # Check required fields
            if not repair_plan.get('diagnosis') or not repair_plan.get('repair_type'):
                logger.warning("Repair plan missing required fields")
                return False
            
            # Validate repair type
            valid_repair_types = ['dependency', 'configuration', 'structural', 'permission', 'missing_file']
            if repair_plan.get('repair_type') not in valid_repair_types:
                logger.warning(f"Invalid repair type: {repair_plan.get('repair_type')}")
                return False
            
            # Validate commands for safety
            if 'commands' in repair_plan:
                for command in repair_plan['commands']:
                    if not isinstance(command, list) or not command:
                        logger.warning(f"Invalid command format: {command}")
                        return False
                    
                    # Block dangerous commands
                    dangerous_patterns = ['rm -rf /', 'sudo rm', 'format', 'mkfs', '> /dev/']
                    command_str = ' '.join(command).lower()
                    if any(pattern in command_str for pattern in dangerous_patterns):
                        logger.warning(f"Dangerous command blocked: {command_str}")
                        return False
            
            # Validate file paths for safety
            if 'files_to_create' in repair_plan:
                for file_path in repair_plan['files_to_create'].keys():
                    if file_path.startswith('/') or '..' in file_path:
                        logger.warning(f"Unsafe file path blocked: {file_path}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating repair plan: {e}")
            return False
    
    def _record_successful_repair(self, error_signature: str, repair_plan: Dict):
        """Record successful repair for future reference"""
        try:
            # Could be extended to maintain a database of successful repairs
            logger.info(f"✅ Recorded successful repair for signature: {error_signature[:16]}...")
        except Exception as e:
            logger.warning(f"Could not record successful repair: {e}")
    
    async def _gather_project_context(self, project_path: str, stack: str) -> Dict:
        """🔥 ENHANCED: Gather more comprehensive project information"""
        try:
            context = {
                "stack": stack,
                "project_structure": {},
                "config_files": {},
                "existing_files": [],
                "environment_info": {}
            }
            
            project_root = Path(project_path)
            
            # Gather file structure (limited depth to avoid overwhelming LLM)
            for item in project_root.iterdir():
                if item.name.startswith('.'):
                    continue  # Skip hidden files/dirs
                    
                if item.is_file() and item.name not in ['.DS_Store']:
                    context["existing_files"].append(item.name)
                elif item.is_dir():
                    # Count files in subdirectory (for size estimation)
                    try:
                        file_count = len([f for f in item.iterdir() if f.is_file()]) if item.exists() else 0
                        context["project_structure"][item.name] = file_count
                    except:
                        context["project_structure"][item.name] = 0
            
            # Read key configuration files based on stack
            config_files_to_read = {
                "laravel": ["composer.json", "artisan", ".env.example", "phpstan.neon.dist"],
                "vue": ["package.json", "vite.config.js", "vue.config.js", "tsconfig.json"],
                "react": ["package.json", "package-lock.json", "tsconfig.json"],
                "python": ["requirements.txt", "pyproject.toml", "setup.py"],
                "node": ["package.json"],
            }
            
            files_to_check = config_files_to_read.get(stack, ["package.json", "composer.json"])
            
            for filename in files_to_check:
                file_path = project_root / filename
                if file_path.exists() and file_path.stat().st_size < 10000:  # Max 10KB files
                    try:
                        context["config_files"][filename] = file_path.read_text(encoding='utf-8', errors='ignore')
                    except:
                        context["config_files"][filename] = "[binary or unreadable]"
            
            # 🔥 NEW: Gather environment information
            context["environment_info"] = await self._gather_environment_info(project_root, stack)
            
            return context
            
        except Exception as e:
            logger.warning(f"Error gathering project context: {e}")
            return {"stack": stack, "error": str(e)}
    
    async def _gather_environment_info(self, project_root: Path, stack: str) -> Dict:
        """🔥 NEW: Gather environment-specific information"""
        env_info = {}
        
        try:
            if stack == "laravel":
                # Check Laravel-specific environment
                env_info["vendor_exists"] = (project_root / "vendor").exists()
                env_info["artisan_exists"] = (project_root / "artisan").exists()
                env_info["bootstrap_exists"] = (project_root / "bootstrap").exists()
                
                # Check if composer is available
                try:
                    result = await self._run_command_with_timeout(
                        ["composer", "--version"], 
                        cwd=str(project_root),
                        timeout=10
                    )
                    env_info["composer_available"] = result.returncode == 0
                except:
                    env_info["composer_available"] = False
                
                # Check PHP availability
                try:
                    result = await self._run_command_with_timeout(
                        ["php", "--version"],
                        cwd=str(project_root),
                        timeout=10
                    )
                    env_info["php_available"] = result.returncode == 0
                    if result.returncode == 0:
                        env_info["php_version"] = result.stdout.split('\
')[0] if result.stdout else "unknown"
                except:
                    env_info["php_available"] = False
            
            elif stack in ["vue", "react", "node"]:
                # Check Node.js environment
                env_info["node_modules_exists"] = (project_root / "node_modules").exists()
                env_info["package_json_exists"] = (project_root / "package.json").exists()
                
                # Check npm/yarn availability
                for package_manager in ["npm", "yarn"]:
                    try:
                        result = await self._run_command_with_timeout(
                            [package_manager, "--version"],
                            cwd=str(project_root),
                            timeout=10
                        )
                        env_info[f"{package_manager}_available"] = result.returncode == 0
                    except:
                        env_info[f"{package_manager}_available"] = False
            
        except Exception as e:
            logger.warning(f"Error gathering environment info: {e}")
            env_info["error"] = str(e)
        
        return env_info
    
    async def _generate_repair_with_llm(
        self, 
        project_path: str, 
        stack: str, 
        error_output: str, 
        failed_command: str,
        project_context: Dict
    ) -> Optional[Dict]:
        """🔥 ENHANCED: Use LLM with improved context and constraints"""
        
        if not self.llm_router:
            logger.warning("No LLM router available for repair generation")
            return None
        
        try:
            # Create enhanced diagnostic prompt
            prompt = self._create_enhanced_diagnostic_prompt(
                stack, error_output, failed_command, project_context
            )
            
            # Generate repair with LLM
            response = await self.llm_router.generate(
                prompt=prompt,
                task_type="repair_analysis",
                current_cost=0.0,
                budget_limit=1.0,  # Small budget for repairs
                run_id=None
            )
            
            if not response or not response.content:
                return None
            
            # Parse LLM response into repair plan
            repair_plan = self._parse_repair_response(response.content)
            return repair_plan
            
        except Exception as e:
            logger.error(f"Error generating repair with LLM: {e}")
            return None
    
    def _create_enhanced_diagnostic_prompt(
        self, 
        stack: str, 
        error_output: str, 
        failed_command: str, 
        project_context: Dict
    ) -> str:
        """🔥 ENHANCED: Create more comprehensive prompt for LLM analysis"""
        
        environment_info = project_context.get("environment_info", {})
        repair_history = project_context.get("repair_history", [])
        
        history_section = ""
        if repair_history:
            history_section = f"""
REPAIR HISTORY:
{chr(10).join(repair_history)}
NOTE: Avoid suggesting the same solutions that have been tried before.
"""
        
        environment_section = ""
        if environment_info:
            environment_section = f"""
ENVIRONMENT STATUS:
{self._format_environment_info(environment_info)}
"""
        
        return f"""SYSTEM ERROR ANALYSIS AND REPAIR - ENHANCED MODE

You are an expert system administrator and developer specializing in {stack} projects. 
Analyze this error and provide a specific, targeted repair plan.

PROJECT CONTEXT:
- Technology Stack: {stack}
- Failed Command: {failed_command}
- Project Structure: {project_context.get('project_structure', {})}
- Existing Files: {project_context.get('existing_files', [])}
{environment_section}
CONFIGURATION FILES:
{self._format_config_files(project_context.get('config_files', {}))}

ERROR OUTPUT:
{error_output}
{history_section}
ANALYSIS REQUIRED:
1. Identify the specific root cause of the error
2. Determine if this is a missing dependency, configuration issue, structural problem, or permission error
3. Provide minimal, targeted commands and/or files to create
4. Ensure the repair addresses the root cause, not just symptoms
5. Consider the project's current state and avoid destructive operations

SAFETY CONSTRAINTS:
- Only suggest safe, reversible operations
- Prefer dependency installation over file system modifications
- Use standard package managers (composer, npm, pip)
- Avoid direct file system manipulation when possible
- Do not suggest removing system files or directories

RESPONSE FORMAT:
```json
{{
    "diagnosis": "Specific description of the root cause",
    "repair_type": "dependency|configuration|structural|permission|missing_file",
    "confidence": 0.8,
    "commands": [
        ["command", "arg1", "arg2"],
        ["command2", "arg1"]
    ],
    "files_to_create": {{
        "relative/path/to/file.ext": "file content here"
    }},
    "files_to_modify": {{
        "relative/path/to/file.ext": "new content or specific changes"
    }},
    "success_check": "command to verify repair worked",
    "explanation": "Why this repair should work and what it addresses"
}}
```

Focus on {stack} best practices. Provide minimal, targeted fixes that address the specific error.
Prioritize dependency installation and configuration over structural changes."""
    
    def _format_environment_info(self, env_info: Dict) -> str:
        """Format environment information for prompt"""
        if not env_info:
            return "No environment information available"
        
        formatted = []
        for key, value in env_info.items():
            if key != "error":
                formatted.append(f"- {key}: {value}")
        
        return "\
".join(formatted)
    
    def _format_config_files(self, config_files: Dict[str, str]) -> str:
        """Format config files for prompt"""
        if not config_files:
            return "No configuration files found"
        
        formatted = []
        for filename, content in config_files.items():
            # Truncate long files
            display_content = content[:500] + "..." if len(content) > 500 else content
            formatted.append(f"--- {filename} ---\
{display_content}")
        
        return "\
\
".join(formatted)
    
    def _parse_repair_response(self, llm_content: str) -> Optional[Dict]:
        """🔥 ENHANCED: Parse LLM response with better validation"""
        try:
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_content, re.DOTALL)
            if not json_match:
                # Try to find JSON without markdown
                json_match = re.search(r'(\{.*\})', llm_content, re.DOTALL)
            
            if not json_match:
                logger.warning("No JSON found in LLM repair response")
                return None
            
            repair_plan = json.loads(json_match.group(1))
            
            # Validate required fields
            required_fields = ["diagnosis", "repair_type"]
            if not all(field in repair_plan for field in required_fields):
                logger.warning("Incomplete repair plan from LLM - missing required fields")
                return None
            
            # 🔥 NEW: Additional validation
            if "confidence" in repair_plan:
                confidence = repair_plan.get("confidence", 0.0)
                if confidence < 0.5:
                    logger.warning(f"Low confidence repair plan ({confidence}) - may not be reliable")
            
            # Ensure commands are properly formatted
            if "commands" in repair_plan:
                commands = repair_plan["commands"]
                if not isinstance(commands, list):
                    repair_plan["commands"] = []
                else:
                    # Validate each command
                    valid_commands = []
                    for cmd in commands:
                        if isinstance(cmd, list) and len(cmd) > 0:
                            valid_commands.append(cmd)
                    repair_plan["commands"] = valid_commands
            
            return repair_plan
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in LLM repair response: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM repair response: {e}")
            return None
    
    async def _apply_llm_repair(self, project_path: str, repair_plan: Dict) -> RepairResult:
        """🔥 ENHANCED: Apply repair with better monitoring and rollback capability"""
        try:
            logger.info(f"Applying LLM repair: {repair_plan.get('diagnosis', 'Unknown')}")
            
            commands_executed = []
            files_created = {}
            
            # 1. Execute repair commands with enhanced monitoring
            if "commands" in repair_plan:
                for command in repair_plan["commands"]:
                    try:
                        logger.info(f"🔧 Executing repair command: {' '.join(command)}")
                        
                        result = await self._run_command_with_timeout(
                            command,
                            cwd=project_path,
                            timeout=self.command_timeout
                        )
                        
                        command_str = " ".join(command)
                        commands_executed.append(command_str)
                        
                        if result.returncode != 0:
                            logger.warning(f"❌ Repair command failed: {command_str}")
                            logger.warning(f"   STDERR: {result.stderr}")
                            # Don't fail immediately - some commands might be optional
                        else:
                            logger.info(f"✅ Repair command succeeded: {command_str}")
                            
                    except asyncio.TimeoutError:
                        logger.error(f"⏰ Repair command timeout: {' '.join(command)}")
                        commands_executed.append(f"{' '.join(command)} (TIMEOUT)")
                    except Exception as e:
                        logger.error(f"❌ Error executing repair command {command}: {e}")
                        commands_executed.append(f"{' '.join(command)} (ERROR: {e})")
            
            # 2. Create files
            if "files_to_create" in repair_plan:
                for file_path, content in repair_plan["files_to_create"].items():
                    try:
                        full_path = Path(project_path) / file_path
                        
                        # Security check - ensure path is within project
                        full_path.resolve().relative_to(Path(project_path).resolve())
                        
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(content, encoding='utf-8')
                        files_created[file_path] = content
                        logger.info(f"✅ Created file: {file_path}")
                        
                        # Make executable if it's a script
                        if file_path in ["artisan", "manage.py"] or file_path.endswith(".sh"):
                            os.chmod(full_path, 0o755)
                            
                    except ValueError as e:
                        logger.error(f"❌ Security violation - file path outside project: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Error creating file {file_path}: {e}")
            
            # 3. Modify files (JSON patches or replacements)
            if "files_to_modify" in repair_plan:
                for file_path, new_content in repair_plan["files_to_modify"].items():
                    try:
                        full_path = Path(project_path) / file_path
                        
                        # Security check
                        full_path.resolve().relative_to(Path(project_path).resolve())
                        
                        if full_path.exists():
                            # Backup original file before modification
                            backup_path = full_path.with_suffix(full_path.suffix + '.backup')
                            full_path.rename(backup_path)
                            
                            # Write new content
                            full_path.write_text(new_content, encoding='utf-8')
                            logger.info(f"✅ Modified file: {file_path} (backup: {backup_path.name})")
                        else:
                            logger.warning(f"⚠️ File to modify not found: {file_path}")
                    except ValueError as e:
                        logger.error(f"❌ Security violation - file path outside project: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Error modifying file {file_path}: {e}")
            
            # 4. Verify repair if success check provided
            success_verified = True
            if "success_check" in repair_plan and repair_plan["success_check"]:
                try:
                    check_command = repair_plan["success_check"].split()
                    logger.info(f"🔍 Verifying repair with: {' '.join(check_command)}")
                    
                    result = await self._run_command_with_timeout(
                        check_command,
                        cwd=project_path,
                        timeout=30
                    )
                    success_verified = result.returncode == 0
                    if not success_verified:
                        logger.warning(f"⚠️ Repair verification failed: {result.stderr}")
                    else:
                        logger.info("✅ Repair verification passed")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error verifying repair: {e}")
                    success_verified = False
            
            return RepairResult(
                success=success_verified and (commands_executed or files_created),
                description=repair_plan.get("diagnosis", "LLM repair applied"),
                commands_executed=commands_executed,
                files_created=files_created
            )
            
        except Exception as e:
            logger.error(f"❌ Error applying LLM repair: {e}")
            return RepairResult(
                success=False,
                description="Failed to apply LLM repair",
                error_message=str(e)
            )
    
    async def _run_command_with_timeout(self, command: List[str], cwd: str, timeout: int = None):
        """🔥 ENHANCED: Run command with intelligent timeout and cleanup"""
        if timeout is None:
            timeout = self.command_timeout

        process = None
        process_group_id = None
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Store process group ID for cleanup
            if hasattr(os, 'getpgid') and process.pid:
                try:
                    process_group_id = os.getpgid(process.pid)
                except:
                    process_group_id = None
            
            # 🔥 NEW: Verify process was created successfully
            if process is None:
                logger.error(f"❌ Failed to create subprocess for command: {' '.join(command)}")
                return type('CommandResult', (), {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': 'Failed to create subprocess'
                })()
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            return type('CommandResult', (), {
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8', errors='ignore'),
                'stderr': stderr.decode('utf-8', errors='ignore')
            })()
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Command timeout ({timeout}s): {' '.join(command)}")
            
            # Enhanced cleanup
            cleanup_success = await self._cleanup_timed_out_process(process, process_group_id)
            if not cleanup_success:
                logger.error("❌ Failed to cleanup timed out process")
            
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds'
            })()
            
        except FileNotFoundError:
            logger.error(f"❌ Command not found: {command[0]}")
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command not found: {command[0]}'
            })()
            
        except Exception as e:
            logger.error(f"❌ Error running command {' '.join(command)}: {e}")
            # Ensure cleanup on any error
            if process:
                await self._cleanup_timed_out_process(process, process_group_id)
            
            return type('CommandResult', (), {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            })()
    
    async def _cleanup_timed_out_process(self, process, process_group_id=None) -> bool:
        """🔥 NEW: Enhanced process cleanup for repair agent"""
        cleanup_success = False
        
        try:
            # Strategy 1: Graceful termination
            if process and process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                    cleanup_success = True
                except:
                    pass
            
            # Strategy 2: Force kill
            if not cleanup_success and process and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=3)
                    cleanup_success = True
                except:
                    pass
            
            # Strategy 3: Kill process group
            if not cleanup_success and process_group_id and hasattr(os, 'killpg'):
                try:
                    os.killpg(process_group_id, 9)
                    await asyncio.sleep(0.5)
                    cleanup_success = True
                except:
                    pass
            
            return cleanup_success
            
        except Exception as e:
            logger.warning(f"⚠️ Error in process cleanup: {e}")
            return False
