"""
LLM-Powered Repair Agent for Self-Healing System
Uses AI to analyze complex errors and generate fixes when standard repairs fail
"""
import os
import logging
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
    LLM-powered repair agent that analyzes complex errors and generates fixes
    """
    
    def __init__(self, llm_router=None):
        self.llm_router = llm_router
        
    async def analyze_and_repair(
        self, 
        project_path: str, 
        stack: str, 
        error_output: str, 
        failed_command: str,
        context: Dict = None
    ) -> RepairResult:
        """
        Main repair method: analyzes error with LLM and applies generated fix
        """
        try:
            logger.info(f"🤖 LLM-powered error analysis for: {failed_command}")
            
            # 1. Gather project context
            project_context = await self._gather_project_context(project_path, stack)
            
            # 2. Generate repair with LLM
            repair_plan = await self._generate_repair_with_llm(
                project_path, stack, error_output, failed_command, project_context
            )
            
            if not repair_plan:
                return RepairResult(
                    success=False,
                    description="LLM could not generate repair plan",
                    error_message="No repair plan generated"
                )
            
            # 3. Apply the generated repair
            result = await self._apply_llm_repair(project_path, repair_plan)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM-powered repair: {e}")
            return RepairResult(
                success=False,
                description="LLM repair system error",
                error_message=str(e)
            )
    
    async def _gather_project_context(self, project_path: str, stack: str) -> Dict:
        """Gather relevant project information for LLM analysis"""
        try:
            context = {
                "stack": stack,
                "project_structure": {},
                "config_files": {},
                "existing_files": []
            }
            
            project_root = Path(project_path)
            
            # Gather file structure (limited depth)
            for item in project_root.iterdir():
                if item.is_file() and item.name not in ['.DS_Store']:
                    context["existing_files"].append(item.name)
                elif item.is_dir() and not item.name.startswith('.'):
                    context["project_structure"][item.name] = len(list(item.iterdir())) if item.exists() else 0
            
            # Read key configuration files
            config_files_to_read = {
                "laravel": ["composer.json", "artisan", ".env.example"],
                "vue": ["package.json", "vite.config.js", "vue.config.js"],
                "react": ["package.json", "package-lock.json"],
                "python": ["requirements.txt", "pyproject.toml", "setup.py"],
                "node": ["package.json"],
            }
            
            files_to_check = config_files_to_read.get(stack, ["package.json", "composer.json"])
            
            for filename in files_to_check:
                file_path = project_root / filename
                if file_path.exists() and file_path.stat().st_size < 10000:  # Max 10KB files
                    try:
                        context["config_files"][filename] = file_path.read_text()
                    except:
                        context["config_files"][filename] = "[binary or unreadable]"
            
            return context
            
        except Exception as e:
            logger.warning(f"Error gathering project context: {e}")
            return {"stack": stack, "error": str(e)}
    
    async def _generate_repair_with_llm(
        self, 
        project_path: str, 
        stack: str, 
        error_output: str, 
        failed_command: str,
        project_context: Dict
    ) -> Optional[Dict]:
        """Use LLM to analyze error and generate repair instructions"""
        
        if not self.llm_router:
            logger.warning("No LLM router available for repair generation")
            return None
        
        try:
            # Create diagnostic prompt
            prompt = self._create_diagnostic_prompt(
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
    
    def _create_diagnostic_prompt(
        self, 
        stack: str, 
        error_output: str, 
        failed_command: str, 
        project_context: Dict
    ) -> str:
        """Create prompt for LLM error analysis and repair generation"""
        
        return f"""SYSTEM ERROR ANALYSIS AND REPAIR

You are an expert system administrator and developer. Analyze this error and provide a specific repair plan.

PROJECT CONTEXT:
- Technology Stack: {stack}
- Failed Command: {failed_command}
- Project Structure: {project_context.get('project_structure', {})}
- Existing Files: {project_context.get('existing_files', [])}
- Configuration Files:
{self._format_config_files(project_context.get('config_files', {}))}

ERROR OUTPUT:
{error_output}

ANALYSIS REQUIRED:
1. Identify the root cause of the error
2. Determine if this is a missing dependency, configuration, or structural issue  
3. Provide specific repair commands and/or files to create
4. Ensure the repair is minimal and safe

RESPONSE FORMAT:
```json
{{
    "diagnosis": "Brief description of the problem",
    "repair_type": "dependency|configuration|structural|permission",
    "commands": [
        ["command", "arg1", "arg2"],
        ["command2", "arg1"]
    ],
    "files_to_create": {{
        "path/to/file.ext": "file content here"
    }},
    "files_to_modify": {{
        "path/to/file.ext": "new content or JSON patch"
    }},
    "success_check": "command to verify repair worked"
}}
```

Focus on {stack} best practices. Provide minimal, targeted fixes only."""
    
    def _format_config_files(self, config_files: Dict[str, str]) -> str:
        """Format config files for prompt"""
        if not config_files:
            return "No configuration files found"
        
        formatted = []
        for filename, content in config_files.items():
            # Truncate long files
            display_content = content[:500] + "..." if len(content) > 500 else content
            formatted.append(f"--- {filename} ---\n{display_content}")
        
        return "\n\n".join(formatted)
    
    def _parse_repair_response(self, llm_content: str) -> Optional[Dict]:
        """Parse LLM response into structured repair plan"""
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
                logger.warning("Incomplete repair plan from LLM")
                return None
            
            return repair_plan
            
        except Exception as e:
            logger.error(f"Error parsing LLM repair response: {e}")
            return None
    
    async def _apply_llm_repair(self, project_path: str, repair_plan: Dict) -> RepairResult:
        """Apply the repair plan generated by LLM"""
        try:
            logger.info(f"Applying LLM repair: {repair_plan.get('diagnosis', 'Unknown')}")
            
            commands_executed = []
            files_created = {}
            
            # 1. Execute repair commands
            if "commands" in repair_plan:
                for command in repair_plan["commands"]:
                    try:
                        import subprocess
                        result = subprocess.run(
                            command,
                            cwd=project_path,
                            capture_output=True,
                            text=True,
                            timeout=120
                        )
                        
                        command_str = " ".join(command)
                        commands_executed.append(command_str)
                        
                        if result.returncode != 0:
                            logger.warning(f"Repair command failed: {command_str} - {result.stderr}")
                        else:
                            logger.info(f"✅ Repair command succeeded: {command_str}")
                            
                    except Exception as e:
                        logger.error(f"Error executing repair command {command}: {e}")
            
            # 2. Create files
            if "files_to_create" in repair_plan:
                for file_path, content in repair_plan["files_to_create"].items():
                    try:
                        full_path = Path(project_path) / file_path
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(content)
                        files_created[file_path] = content
                        logger.info(f"✅ Created file: {file_path}")
                        
                        # Make executable if it's a script
                        if file_path in ["artisan", "manage.py"] or file_path.endswith(".sh"):
                            os.chmod(full_path, 0o755)
                            
                    except Exception as e:
                        logger.error(f"Error creating file {file_path}: {e}")
            
            # 3. Modify files (JSON patches or replacements)
            if "files_to_modify" in repair_plan:
                for file_path, new_content in repair_plan["files_to_modify"].items():
                    try:
                        full_path = Path(project_path) / file_path
                        if full_path.exists():
                            # For now, simple replacement (could be enhanced with JSON patches)
                            full_path.write_text(new_content)
                            logger.info(f"✅ Modified file: {file_path}")
                        else:
                            logger.warning(f"File to modify not found: {file_path}")
                    except Exception as e:
                        logger.error(f"Error modifying file {file_path}: {e}")
            
            # 4. Verify repair if success check provided
            success_verified = True
            if "success_check" in repair_plan:
                try:
                    check_command = repair_plan["success_check"].split()
                    result = subprocess.run(
                        check_command,
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    success_verified = result.returncode == 0
                    if not success_verified:
                        logger.warning(f"Repair verification failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Error verifying repair: {e}")
                    success_verified = False
            
            return RepairResult(
                success=success_verified,
                description=repair_plan.get("diagnosis", "LLM repair applied"),
                commands_executed=commands_executed,
                files_created=files_created
            )
            
        except Exception as e:
            logger.error(f"Error applying LLM repair: {e}")
            return RepairResult(
                success=False,
                description="Failed to apply LLM repair",
                error_message=str(e)
            )