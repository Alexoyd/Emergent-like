"""
Plan parsing utilities for emergent-like agent system.

This module defines the ``Step`` data structure used to represent
individual work items, an ``ActionType`` enumeration to classify the
nature of each step, and a ``PlanParser`` capable of transforming
semi‑structured text plans into structured lists of steps.  The parser
supports a variety of plan formats including numbered lists, bullet
lists, markdown sections, French/English keywords and metadata blocks.

Errors raised by the parser are encapsulated in ``PlanParsingError``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class ActionType(Enum):
    """Enumeration of high‑level actions for plan steps."""

    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_TESTS = "run_tests"
    INSTALL_PACKAGE = "install_package"
    CONFIGURE = "configure"
    DEBUG = "debug"
    REFACTOR = "refactor"
    OTHER = "other"


class PlanParsingError(Exception):
    """Raised when a plan cannot be parsed into valid steps."""


@dataclass
class Step:
    """Represents a discrete unit of work in a generated plan."""

    id: int
    description: str
    type_action: ActionType
    dependencies: List[int] = field(default_factory=list)
    files_involved: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    estimated_duration: Optional[int] = None  # duration in minutes
    priority: Optional[int] = None  # lower numbers mean higher priority


class PlanParser:
    """
    Convert high‑level plan text into a list of :class:`Step` objects.

    The parser attempts to be resilient to a variety of plan formats
    produced by large language models, including markdown headings,
    numbered lists, bullet lists, annotated steps with metadata and
    French/English language variants.  When no structured plan can be
    identified, the parser falls back to wrapping the entire text in a
    single ``Step``.
    """

    STEP_PATTERNS = [
        # e.g. "1. Step description", "2) Step description"
        re.compile(r"^\s*(\d+)[\.\)]\s+(.*)$"),
        # e.g. "- Step description", "* Step description"
        re.compile(r"^\s*[-*+]\s+(.*)$"),
        # e.g. "Étape 1: description" or "Etape 1 : description"
        re.compile(r"^\s*Étape\s*(\d+)\s*[:.-]\s*(.*)$", re.IGNORECASE),
        re.compile(r"^\s*Etape\s*(\d+)\s*[:.-]\s*(.*)$", re.IGNORECASE),
    ]

    DEPENDENCY_PATTERNS = [
        # depends on step 1, Depends on: Step 1
        re.compile(r"depends? on\s*(?:[:\-])?\s*step\s*(\d+)", re.IGNORECASE),
        # after step 2
        re.compile(r"after\s*step\s*(\d+)", re.IGNORECASE),
        # requires step 3
        re.compile(r"requires?\s*step\s*(\d+)", re.IGNORECASE),
    ]

    DURATION_PATTERNS = [
        # e.g. "Duration: 30 minutes" or "Durée: 2 hours"
        re.compile(r"\b(?:duration|durée|time)\s*[:=]\s*(\d+(?:\.\d+)?)\s*(minutes|minute|hours|hour|heures|heure)", re.IGNORECASE),
        # e.g. "30 minutes", "2 hours"
        re.compile(r"(\d+(?:\.\d+)?)\s*(minutes|minute|hours|hour|heures|heure)", re.IGNORECASE),
    ]

    PRIORITY_PATTERNS = [
        re.compile(r"\bpriority\s*[:=]\s*(high|medium|low|\d+)", re.IGNORECASE),
        re.compile(r"\bpriorité\s*[:=]\s*(haute|moyenne|basse|\d+)", re.IGNORECASE),
    ]

    def parse_plan(self, text: str) -> List[Step]:
        """Parse a textual plan into a list of :class:`Step` objects.

        :param text: The raw plan text produced by a language model.
        :raises PlanParsingError: If the plan is empty or cannot be parsed.
        :return: A list of parsed steps.
        """
        if text is None or not text.strip():
            raise PlanParsingError("Plan text is empty")

        # Normalise line endings and remove carriage returns
        lines = text.strip().splitlines()

        steps: List[Step] = []
        i = 0
        step_counter = 1

        while i < len(lines):
            line = lines[i].rstrip()
            # Skip headings and empty lines
            if not line or line.strip().startswith("#"):
                i += 1
                continue

            match = None
            description = None
            for pattern in self.STEP_PATTERNS:
                m = pattern.match(line)
                if m:
                    match = m
                    # If pattern includes a group for id, skip group[1], else use auto increment
                    if m.lastindex and len(m.groups()) >= 2:
                        # group 1 is step number in the text, group 2 is description
                        description = m.group(2).strip()
                    else:
                        description = m.group(m.lastindex).strip() if m.lastindex else m.group(1).strip()
                    break
            # If no explicit match on numbering/bullet, treat line starting with uppercase letter as step
            if not match:
                # Heuristic: treat any line beginning with a non‑bullet word as a new step if it's not indented
                if re.match(r"^\s*\d+", line):
                    # line like "1 Create step" without a dot
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) > 1:
                        description = parts[1]
                elif re.match(r"^\s*(Étape|Etape)\s*\d+", line, re.IGNORECASE):
                    # Already matched by pattern above
                    pass
                else:
                    # If line begins with a dash inside markdown list but with no space (rare), handle
                    if re.match(r"^\s*[-*]\s*", line):
                        description = line.lstrip("-* ")
                    else:
                        # Not a new step; skip
                        i += 1
                        continue

            # At this point we have a description for a step
            metadata_lines: List[str] = []
            j = i + 1
            # Collect all indented lines following this step until next step or heading
            while j < len(lines):
                next_line = lines[j]
                # Stop if next line starts a new step or heading
                if (next_line.strip() and
                    (self._is_step_start(next_line) or next_line.strip().startswith("#"))):
                    break
                metadata_lines.append(next_line.rstrip("\n"))
                j += 1

            # Parse metadata from description and subsequent lines
            step = Step(
                id=step_counter,
                description=description.strip(),
                type_action=self._detect_action_type(description),
            )
            # Extract metadata from the description line itself and from subsequent lines
            # This allows duration/priority specified inline (e.g., "Duration: 30 minutes")
            self._parse_metadata(step, [description] + metadata_lines)

            # Add step
            steps.append(step)
            step_counter += 1
            i = j

        # If no structured steps were found, create a single step fallback
        if not steps:
            fallback_step = Step(
                id=1,
                description=text.strip(),
                type_action=self._detect_action_type(text),
            )
            # Attempt to extract files and commands from the entire text
            self._parse_metadata(fallback_step, [])
            steps.append(fallback_step)

        return steps

    def _is_step_start(self, line: str) -> bool:
        """Return True if the line appears to start a new step."""
        stripped = line.strip()
        if not stripped:
            return False
        # Headings start a new section but not a step
        if stripped.startswith("#"):
            return False
        for pattern in self.STEP_PATTERNS:
            if pattern.match(stripped):
                return True
        # Additional heuristic: lines beginning with digits followed by space
        if re.match(r"^\d+\s+", stripped):
            return True
        # Lines starting with bullet or star
        if re.match(r"^[-*+]\s+", stripped):
            return True
        # Lines starting with Étape or Etape
        if re.match(r"^(Étape|Etape)\s+\d+", stripped, re.IGNORECASE):
            return True
        return False

    def _parse_metadata(self, step: Step, lines: List[str]) -> None:
        """
        Inspect metadata lines and update the step in place with extracted
        files, commands, durations, priority and dependencies.
        """
        # Join lines for easier scanning of patterns across lines
        for idx, raw in enumerate(lines):
            line = raw.strip()
            if not line:
                continue
            # Detect and extract commands inside fenced code blocks
            if line.startswith("```"):
                # gather all lines until closing triple backtick
                commands = []
                k = idx + 1
                while k < len(lines) and not lines[k].strip().startswith("```"):
                    cmd_line = lines[k].strip()
                    if cmd_line:
                        commands.append(cmd_line)
                    k += 1
                step.commands.extend(commands)
                continue

            # Metadata sections starting with key: value pairs
            # Files: ...
            if re.match(r"^(Files|Fichiers|Fichier)\s*:", line, re.IGNORECASE):
                # Everything after the colon is considered a file list
                files_part = line.split(":", 1)[1]
                step.files_involved.extend(self._extract_files(files_part))
                continue
            # Command: or Run: or Run: `cmd`
            if re.match(r"^(Command|Run|Then run)\s*:", line, re.IGNORECASE):
                cmd = line.split(":", 1)[1].strip().strip("`")
                if cmd:
                    step.commands.append(cmd)
                continue
            # Estimated duration
            for pattern in self.DURATION_PATTERNS:
                m = pattern.search(line)
                if m:
                    value = float(m.group(1))
                    unit = m.group(2).lower()
                    if unit.startswith("hour") or unit.startswith("heure") or unit.startswith("heures"):
                        minutes = int(value * 60)
                    else:
                        minutes = int(value)
                    step.estimated_duration = minutes
                    break
            # Priority
            for pattern in self.PRIORITY_PATTERNS:
                m = pattern.search(line)
                if m:
                    val = m.group(1).lower()
                    # Map textual priorities to numbers (1 high, 2 medium, 3 low)
                    if val in {"high", "haute", "1"}:
                        step.priority = 1
                    elif val in {"medium", "moyenne", "2"}:
                        step.priority = 2
                    elif val in {"low", "basse", "3"}:
                        step.priority = 3
                    else:
                        try:
                            step.priority = int(val)
                        except Exception:
                            pass
                    break
            # Dependencies (collect step numbers)
            for pattern in self.DEPENDENCY_PATTERNS:
                m = pattern.search(line)
                if m:
                    try:
                        dep_id = int(m.group(1))
                        step.dependencies.append(dep_id)
                    except ValueError:
                        pass
                    break
            # Additional file extraction within normal lines
            step.files_involved.extend(self._extract_files(line))
        # Deduplicate file list
        if step.files_involved:
            unique_files = []
            for f in step.files_involved:
                if f not in unique_files:
                    unique_files.append(f)
            step.files_involved = unique_files

    def _detect_action_type(self, description: str) -> ActionType:
        """Infer the action type from a step description."""
        if not description:
            return ActionType.OTHER
        desc = description.lower()
        # French/English verbs for creating a file (explicit create/generate verbs)
        if any(word in desc for word in ["create", "créer", "creer", "generate", "make"]):
            # Distinguish between creating and modifying existing artefacts
            if any(word in desc for word in ["model", "controller", "service", ".php", ".js", ".py", "file", "fichier"]):
                return ActionType.CREATE_FILE
        # Modify or add existing file or configuration
        if any(word in desc for word in ["modify", "update", "edit", "changer", "change", "adjust", "amend", "add", "ajouter"]):
            return ActionType.MODIFY_FILE
        # Delete or remove
        if any(word in desc for word in ["delete", "remove", "supprimer", "drop"]):
            return ActionType.DELETE_FILE
        # Run tests
        if any(word in desc for word in ["test", "tests", "unit tests", "pest", "phpunit", "pytest", "run test", "run tests"]):
            return ActionType.RUN_TESTS
        # Install package
        if any(word in desc for word in ["install", "installer", "require", "composer", "npm", "pip", "package"]):
            return ActionType.INSTALL_PACKAGE
        # Configuration
        if any(word in desc for word in ["configure", "configurer", "setup", "set up", "config"]):
            return ActionType.CONFIGURE
        # Debugging
        if any(word in desc for word in ["debug", "fix", "résoudre", "resoudre", "resolve", "bug"]):
            return ActionType.DEBUG
        # Refactoring
        if any(word in desc for word in ["refactor", "refactoriser", "clean up", "optimiser", "simplify"]):
            return ActionType.REFACTOR
        return ActionType.OTHER

    def _extract_files(self, text: str) -> List[str]:
        """Return a list of file paths mentioned in text."""
        files = []
        if not text:
            return files
        # Split by whitespace and commas to find potential file names
        tokens = re.split(r"[\\s,]+", text)
        for token in tokens:
            token = token.strip()
            # Heuristic: treat token as file if it contains a slash or a dot and has an extension like .php/.js/.py/.json etc.
            if not token:
                continue
            if "/" in token or "." in token:
                # Remove trailing punctuation
                token_clean = token.strip().strip("`.,;:()[]{}<>")
                # Ensure token has at least one dot or slash and valid filename characters
                if re.match(r"[A-Za-z0-9_.\\-/]+\\.[A-Za-z0-9]+", token_clean):
                    files.append(token_clean)
        return files
