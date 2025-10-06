"""
Advanced Patch Validator & Auto-Repair System
Validates, repairs, and enhances patch quality for reliable application
"""
import os
import re
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class PatchIssue(Enum):
    """Types of patch issues that can be detected and repaired"""
    MISSING_DIFF_HEADER = "missing_diff_header"
    MISSING_FILE_HEADERS = "missing_file_headers" 
    INVALID_HUNK_HEADER = "invalid_hunk_header"
    MALFORMED_CONTENT = "malformed_content"
    PATH_MISMATCH = "path_mismatch"
    ENCODING_ISSUE = "encoding_issue"
    LINE_ENDING_ISSUE = "line_ending_issue"
    CONTEXT_CORRUPTION = "context_corruption"

@dataclass
class PatchValidationResult:
    """Result of patch validation and repair"""
    is_valid: bool
    original_patch: str
    repaired_patch: Optional[str] = None
    issues_found: List[PatchIssue] = None
    repairs_applied: List[str] = None
    validation_errors: List[str] = None
    confidence_score: float = 0.0  # 0.0 to 1.0

class PatchValidator:
    """
    Advanced patch validator with automatic repair capabilities
    """
    
    def __init__(self):
        self.diff_header_pattern = re.compile(r'^diff --git a/(.+) b/(.+)$', re.MULTILINE)
        self.file_header_patterns = {
            'old_file': re.compile(r'^--- (.*)$', re.MULTILINE),
            'new_file': re.compile(r'^\+\+\+ (.*)$', re.MULTILINE)
        }
        self.hunk_header_pattern = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*$', re.MULTILINE)
        
    def validate_and_repair_patch(self, patch_content: str, project_path: str = None) -> PatchValidationResult:
        """
        Main method: validate patch and apply automatic repairs
        """
        try:
            logger.info("🔍 Validating patch quality and format...")
            
            # Initialize result
            result = PatchValidationResult(
                is_valid=False,
                original_patch=patch_content,
                issues_found=[],
                repairs_applied=[],
                validation_errors=[]
            )
            
            # 1. Basic format validation
            issues = self._detect_patch_issues(patch_content)
            result.issues_found = issues
            
            if not issues:
                # Patch is already valid
                result.is_valid = True
                result.confidence_score = 1.0
                logger.info("✅ Patch is already valid")
                return result
            
            # 2. Apply automatic repairs
            repaired_patch = self._apply_automatic_repairs(patch_content, issues, project_path)
            result.repaired_patch = repaired_patch
            
            # 3. Validate repaired patch
            final_validation = self._validate_repaired_patch(repaired_patch, project_path)
            result.is_valid = final_validation['is_valid']
            result.confidence_score = final_validation['confidence']
            result.validation_errors = final_validation.get('errors', [])
            
            if result.is_valid:
                logger.info(f"✅ Patch successfully repaired and validated (confidence: {result.confidence_score:.2f})")
            else:
                logger.warning(f"❌ Patch repair failed (confidence: {result.confidence_score:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in patch validation: {e}")
            return PatchValidationResult(
                is_valid=False,
                original_patch=patch_content,
                validation_errors=[f"Validation system error: {str(e)}"]
            )
    
    def _detect_patch_issues(self, patch_content: str) -> List[PatchIssue]:
        """Detect all issues in the patch"""
        issues = []
        
        # Check for diff header
        if not self.diff_header_pattern.search(patch_content):
            issues.append(PatchIssue.MISSING_DIFF_HEADER)
        
        # Check for file headers
        old_file_match = self.file_header_patterns['old_file'].search(patch_content)
        new_file_match = self.file_header_patterns['new_file'].search(patch_content)
        
        if not old_file_match or not new_file_match:
            issues.append(PatchIssue.MISSING_FILE_HEADERS)
        
        # Check for hunk headers
        hunk_matches = self.hunk_header_pattern.findall(patch_content)
        if not hunk_matches:
            issues.append(PatchIssue.INVALID_HUNK_HEADER)
        
        # Check line endings
        if '\r\n' in patch_content or '\r' in patch_content:
            issues.append(PatchIssue.LINE_ENDING_ISSUE)
        
        # Check for malformed content
        if self._has_malformed_content(patch_content):
            issues.append(PatchIssue.MALFORMED_CONTENT)
        
        return issues
    
    def _has_malformed_content(self, patch_content: str) -> bool:
        """Check if patch has malformed content lines"""
        lines = patch_content.split('\n')
        
        for line in lines:
            # Skip headers and hunks
            if (line.startswith('diff --git') or 
                line.startswith('---') or 
                line.startswith('+++') or 
                line.startswith('@@')):
                continue
            
            # Content lines should start with +, -, or space
            if line and not line[0] in ['+', '-', ' ']:
                # Check if it's just an empty line or metadata
                if line.strip() and not line.startswith('index ') and not line.startswith('new file'):
                    return True
        
        return False
    
    def _apply_automatic_repairs(self, patch_content: str, issues: List[PatchIssue], project_path: str = None) -> str:
        """Apply automatic repairs for detected issues"""
        repaired = patch_content
        repairs_applied = []
        
        # Fix line endings first
        if PatchIssue.LINE_ENDING_ISSUE in issues:
            repaired = repaired.replace('\r\n', '\n').replace('\r', '\n')
            repairs_applied.append("Fixed line endings (CRLF/CR → LF)")
            logger.info("🔧 Fixed line endings")
        
        # Add missing diff header
        if PatchIssue.MISSING_DIFF_HEADER in issues:
            repaired = self._add_diff_header(repaired, project_path)
            repairs_applied.append("Added missing diff --git header")
            logger.info("🔧 Added diff header")
        
        # Add missing file headers
        if PatchIssue.MISSING_FILE_HEADERS in issues:
            repaired = self._add_file_headers(repaired)
            repairs_applied.append("Added missing --- and +++ file headers")
            logger.info("🔧 Added file headers")
        
        # Fix malformed content
        if PatchIssue.MALFORMED_CONTENT in issues:
            repaired = self._fix_malformed_content(repaired)
            repairs_applied.append("Fixed malformed content lines")
            logger.info("🔧 Fixed malformed content")
        
        # Add missing hunk headers
        if PatchIssue.INVALID_HUNK_HEADER in issues:
            repaired = self._add_hunk_headers(repaired)
            repairs_applied.append("Added/fixed hunk headers")
            logger.info("🔧 Fixed hunk headers")
        
        return repaired
    
    def _add_diff_header(self, patch_content: str, project_path: str = None) -> str:
        """Add missing diff --git header"""
        lines = patch_content.split('\n')
        
        # Try to extract filename from existing headers or content
        filename = self._extract_filename_from_patch(patch_content)
        if not filename:
            filename = "unknown_file.txt"
        
        # Add diff header at the beginning
        diff_header = f"diff --git a/{filename} b/{filename}"
        
        # Check if we need index line (for new files)
        has_new_file = any('new file mode' in line for line in lines)
        if has_new_file:
            index_line = "new file mode 100644\nindex 0000000..1234567"
            return f"{diff_header}\n{index_line}\n{patch_content}"
        else:
            return f"{diff_header}\n{patch_content}"
    
    def _add_file_headers(self, patch_content: str) -> str:
        """Add missing --- and +++ file headers"""
        lines = patch_content.split('\n')
        result_lines = []
        
        filename = self._extract_filename_from_patch(patch_content)
        if not filename:
            filename = "unknown_file.txt"
        
        # Look for diff header to insert after it
        diff_header_found = False
        headers_added = False
        
        for line in lines:
            result_lines.append(line)
            
            if line.startswith('diff --git') and not headers_added:
                diff_header_found = True
            elif diff_header_found and not headers_added and (line.startswith('@@') or line.startswith('+') or line.startswith('-')):
                # Insert file headers before content
                is_new_file = any('new file mode' in l for l in lines)
                if is_new_file:
                    result_lines.insert(-1, "--- /dev/null")
                    result_lines.insert(-1, f"+++ b/{filename}")
                else:
                    result_lines.insert(-1, f"--- a/{filename}")
                    result_lines.insert(-1, f"+++ b/{filename}")
                headers_added = True
        
        return '\n'.join(result_lines)
    
    def _extract_filename_from_patch(self, patch_content: str) -> Optional[str]:
        """Extract filename from patch content"""
        # Try diff header first
        diff_match = self.diff_header_pattern.search(patch_content)
        if diff_match:
            return diff_match.group(1)
        
        # Try file headers
        for pattern in self.file_header_patterns.values():
            match = pattern.search(patch_content)
            if match:
                filepath = match.group(1)
                if filepath != '/dev/null':
                    # Remove a/ or b/ prefix
                    if filepath.startswith(('a/', 'b/')):
                        return filepath[2:]
                    return filepath
        
        # Try to infer from content (look for typical file extensions)
        common_extensions = ['.py', '.js', '.php', '.vue', '.ts', '.jsx', '.tsx', '.json', '.md']
        for ext in common_extensions:
            if ext in patch_content.lower():
                return f"file{ext}"
        
        return None
    
    def _add_hunk_headers(self, patch_content: str) -> str:
        """Add missing @@ hunk headers"""
        lines = patch_content.split('\n')
        result_lines = []
        
        content_started = False
        line_number = 1
        
        for line in lines:
            # Skip until we get to content
            if not content_started:
                result_lines.append(line)
                if line.startswith('+++'):
                    content_started = True
                    # Add basic hunk header after +++ line
                    result_lines.append("@@ -0,0 +1,1 @@")
                continue
            
            # If we find content without hunk header, we already added it
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _fix_malformed_content(self, patch_content: str) -> str:
        """Fix malformed content lines"""
        lines = patch_content.split('\n')
        result_lines = []
        
        in_content = False
        
        for line in lines:
            # Detect when we're in content section
            if line.startswith('@@'):
                in_content = True
                result_lines.append(line)
                continue
            
            if not in_content:
                result_lines.append(line)
                continue
            
            # Fix content lines
            if line == '':
                result_lines.append(line)  # Empty line is OK
            elif line.startswith(('+', '-', ' ')):
                result_lines.append(line)  # Already properly formatted
            elif line.strip():
                # Assume it's an addition if it doesn't start with +/-/ 
                result_lines.append(f"+{line}")
            else:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _validate_repaired_patch(self, patch_content: str, project_path: str = None) -> Dict:
        """Validate the repaired patch"""
        try:
            confidence = 0.0
            errors = []
            
            # Check basic structure
            has_diff_header = bool(self.diff_header_pattern.search(patch_content))
            has_file_headers = bool(
                self.file_header_patterns['old_file'].search(patch_content) and
                self.file_header_patterns['new_file'].search(patch_content)
            )
            has_hunk_header = bool(self.hunk_header_pattern.search(patch_content))
            
            if has_diff_header:
                confidence += 0.3
            else:
                errors.append("Missing diff --git header")
            
            if has_file_headers:
                confidence += 0.3
            else:
                errors.append("Missing file headers")
            
            if has_hunk_header:
                confidence += 0.3
            else:
                errors.append("Missing hunk headers")
            
            # Additional validation
            if not self._has_malformed_content(patch_content):
                confidence += 0.1
            else:
                errors.append("Still has malformed content")
            
            # Syntax validation (basic)
            if self._validate_patch_syntax(patch_content):
                confidence += 0.1
            else:
                errors.append("Syntax validation failed")
            
            return {
                'is_valid': confidence >= 0.8,  # 80% confidence required
                'confidence': confidence,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error in repaired patch validation: {e}")
            return {
                'is_valid': False,
                'confidence': 0.0,
                'errors': [f"Validation error: {str(e)}"]
            }
    
    def _validate_patch_syntax(self, patch_content: str) -> bool:
        """Basic syntax validation for patch"""
        try:
            lines = patch_content.split('\n')
            
            # Count additions and deletions in hunks
            for line in lines:
                if line.startswith('@@'):
                    # Parse hunk header
                    match = self.hunk_header_pattern.match(line)
                    if not match:
                        return False
            
            return True
            
        except Exception:
            return False
    
    def create_enhanced_patch(self, file_path: str, old_content: str, new_content: str) -> str:
        """
        Create a high-quality patch from scratch with proper formatting
        """
        try:
            import difflib
            
            # Generate unified diff
            old_lines = old_content.splitlines(keepends=True)
            new_lines = new_content.splitlines(keepends=True)
            
            diff_lines = list(difflib.unified_diff(
                old_lines, 
                new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm=''
            ))
            
            if not diff_lines:
                return ""
            
            # Enhance with proper git headers
            enhanced_lines = [f"diff --git a/{file_path} b/{file_path}"]
            
            # Add index line if it's a new file
            if not old_content:
                enhanced_lines.append("new file mode 100644")
                enhanced_lines.append("index 0000000..abc1234")
            
            # Add the diff content (skip the first --- and +++ from difflib)
            enhanced_lines.extend(diff_lines[2:] if len(diff_lines) > 2 else diff_lines)
            
            return '\n'.join(enhanced_lines)
            
        except Exception as e:
            logger.error(f"Error creating enhanced patch: {e}")
            return ""
    
    def preview_patch_application(self, patch_content: str, project_path: str) -> Dict:
        """
        Preview what the patch would do without applying it
        """
        try:
            import tempfile
            import subprocess
            
            # Validate patch first
            validation_result = self.validate_and_repair_patch(patch_content, project_path)
            
            if not validation_result.is_valid:
                return {
                    'can_apply': False,
                    'errors': validation_result.validation_errors,
                    'preview': None
                }
            
            # Use the repaired patch if available
            final_patch = validation_result.repaired_patch or patch_content
            
            # Create temp patch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(final_patch)
                patch_file = f.name
            
            try:
                # Try git apply --check (dry run)
                result = subprocess.run(
                    ["git", "apply", "--check", "--verbose", patch_file],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                can_apply = result.returncode == 0
                
                # Get detailed info
                if can_apply:
                    # Get file changes preview
                    stat_result = subprocess.run(
                        ["git", "apply", "--stat", patch_file],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    return {
                        'can_apply': True,
                        'errors': [],
                        'preview': {
                            'stats': stat_result.stdout if stat_result.returncode == 0 else "Stats unavailable",
                            'confidence': validation_result.confidence_score,
                            'repairs_applied': validation_result.repairs_applied
                        }
                    }
                else:
                    return {
                        'can_apply': False,
                        'errors': [result.stderr],
                        'preview': None
                    }
                    
            finally:
                try:
                    os.unlink(patch_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in patch preview: {e}")
            return {
                'can_apply': False,
                'errors': [f"Preview error: {str(e)}"],
                'preview': None
            }