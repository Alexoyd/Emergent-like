"""
Tests d'intégration pour le cycle itératif complet.

Ce fichier teste la nouvelle implémentation d'execute_run() avec :
- PlannerAgent pour la génération de plan
- DeveloperAgent pour la génération de patches
- ReviewerAgent pour l'évaluation des résultats
- Gestion des timeouts et interruptions
- Points de validation utilisateur
- Sauvegarde des conversations d'agents
"""

import pytest
import asyncio
import os
import tempfile
import shutil
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from pathlib import Path

# Import des composants à tester
import sys
sys.path.append(str(Path(__file__).parent))

from backend.server import (
    execute_run, _save_agent_conversation, _execute_step_with_agents,
    _finalize_execution, _is_execution_timeout, _get_project_file_tree
)
from backend.orchestrator.agents.planner import PlannerAgent, ProjectContext
from backend.orchestrator.agents.developer import DeveloperAgent
from backend.orchestrator.agents.reviewer import ReviewerAgent, ReviewDecision
from backend.orchestrator.plan_parser import Step, ActionType
from backend.server import Run, RunStatus


class TestIterativeCycle:
    """Tests pour le cycle itératif complet."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock de la base de données."""
        db = Mock()
        db.runs = Mock()
        db.runs.find_one = AsyncMock()
        db.runs.update_one = AsyncMock()
        db.runs.insert_one = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_state_manager(self):
        """Mock du state manager."""
        state_manager = Mock()
        state_manager.add_log = AsyncMock()
        state_manager.update_run_status = AsyncMock()
        state_manager.update_current_step = AsyncMock()
        return state_manager
    
    @pytest.fixture
    def mock_agents(self):
        """Mock des agents."""
        planner = Mock(spec=PlannerAgent)
        developer = Mock(spec=DeveloperAgent)
        reviewer = Mock(spec=ReviewerAgent)
        
        # Mock des résultats
        from backend.orchestrator.agents.planner import PlanGenerationResult
        from backend.orchestrator.agents.developer import PatchGenerationResult
        from backend.orchestrator.agents.reviewer import ReviewResult
        
        planner.generate_plan = AsyncMock(return_value=PlanGenerationResult(
            plan_text="1. Create basic structure\n2. Add functionality",
            steps=[
                Step(id=1, description="Create basic structure", type_action=ActionType.CREATE_FILE),
                Step(id=2, description="Add functionality", type_action=ActionType.MODIFY_FILE)
            ],
            context=["context1", "context2"]
        ))
        
        developer.generate_patch = AsyncMock(return_value=PatchGenerationResult(
            step_id=1,
            stack="laravel",
            patch_text="diff --git a/test.php b/test.php\n+<?php echo 'Hello World';",
            attempts=1,
            validated=True
        ))
        
        reviewer.review_step_result = AsyncMock(return_value=ReviewResult(
            decision=ReviewDecision.ACCEPT,
            feedback="All tests passed successfully",
            confidence=0.95,
            test_summary={"all_passed": True, "total_tests": 3},
            suggestions=[]
        ))
        
        return planner, developer, reviewer
    
    @pytest.fixture
    def sample_run(self):
        """Run d'exemple pour les tests."""
        return Run(
            id="test-run-123",
            goal="Create a simple Laravel application",
            stack="laravel",
            project_path="/tmp/test-project",
            max_steps=5,
            max_retries_per_step=2,
            daily_budget_eur=10.0
        )
    
    @pytest.fixture
    def temp_project_dir(self):
        """Répertoire temporaire pour les tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_save_agent_conversation(self, mock_db, mock_state_manager):
        """Test de la sauvegarde des conversations d'agents."""
        with patch('backend.server.db', mock_db), \
             patch('backend.server.state_manager', mock_state_manager):
            
            await _save_agent_conversation(
                "test-run-123",
                "planner",
                "input",
                {"task": "Create app", "context": {}}
            )
            
            # Vérifier que la conversation a été sauvegardée
            mock_db.runs.update_one.assert_called_once()
            call_args = mock_db.runs.update_one.call_args
            assert call_args[0][0] == {"id": "test-run-123"}
            assert "$push" in call_args[0][1]
            assert "agent_conversations" in call_args[0][1]["$push"]
            
            # Vérifier le log
            mock_state_manager.add_log.assert_called_once()
    
    def test_is_execution_timeout(self):
        """Test de la détection de timeout."""
        # Contexte sans timeout
        context_no_timeout = {
            "start_time": datetime.now(timezone.utc),
            "timeout_seconds": 3600
        }
        assert not _is_execution_timeout(context_no_timeout)
        
        # Contexte avec timeout
        context_timeout = {
            "start_time": datetime.now(timezone.utc).replace(year=2020),
            "timeout_seconds": 3600
        }
        assert _is_execution_timeout(context_timeout)
    
    @pytest.mark.asyncio
    async def test_get_project_file_tree(self, temp_project_dir):
        """Test de la génération de l'arbre de fichiers."""
        # Créer quelques fichiers de test
        os.makedirs(os.path.join(temp_project_dir, "app"), exist_ok=True)
        os.makedirs(os.path.join(temp_project_dir, "routes"), exist_ok=True)
        
        with open(os.path.join(temp_project_dir, "composer.json"), "w") as f:
            f.write('{"name": "test"}')
        
        with open(os.path.join(temp_project_dir, "app", "User.php"), "w") as f:
            f.write('<?php class User {}')
        
        tree = await _get_project_file_tree(temp_project_dir)
        
        assert "composer.json" in tree
        assert "app/" in tree
        assert "User.php" in tree
        assert "routes/" in tree
    
    @pytest.mark.asyncio
    async def test_execute_step_with_agents_success(
        self, mock_db, mock_state_manager, mock_agents, sample_run, temp_project_dir
    ):
        """Test d'exécution réussie d'une étape avec les agents."""
        planner, developer, reviewer = mock_agents
        
        # Mock des composants
        mock_tool_manager = Mock()
        mock_tool_manager.apply_patch = AsyncMock()
        mock_project_manager = Mock()
        mock_project_manager.get_code_path = Mock(return_value=Path(temp_project_dir))
        
        # Mock des tests
        mock_test_results = [
            Mock(test_type="pest", status="passed", output="All tests passed", details=None)
        ]
        
        step = Step(id=1, description="Create basic structure", type_action=ActionType.CREATE_FILE)
        execution_context = {
            "plan_revision_count": 0,
            "max_plan_revisions": 2
        }
        
        with patch('backend.server.db', mock_db), \
             patch('backend.server.state_manager', mock_state_manager), \
             patch('backend.server.developer_agent', developer), \
             patch('backend.server.reviewer_agent', reviewer), \
             patch('backend.server.tool_manager', mock_tool_manager), \
             patch('backend.server.project_manager', mock_project_manager), \
             patch('backend.server.run_comprehensive_tests', AsyncMock(return_value=mock_test_results)):
            
            result = await _execute_step_with_agents(
                "test-run-123", sample_run, step, 0, execution_context
            )
            
            assert result is True
            developer.generate_patch.assert_called_once()
            reviewer.review_step_result.assert_called_once()
            mock_tool_manager.apply_patch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_step_with_agents_retry(
        self, mock_db, mock_state_manager, mock_agents, sample_run, temp_project_dir
    ):
        """Test d'exécution d'une étape avec retry."""
        planner, developer, reviewer = mock_agents
        
        # Mock pour simuler un échec puis un succès
        from backend.orchestrator.agents.reviewer import ReviewResult
        reviewer.review_step_result = AsyncMock(side_effect=[
            ReviewResult(
                decision=ReviewDecision.RETRY,
                feedback="Tests failed, please fix",
                confidence=0.7,
                test_summary={"all_passed": False, "total_tests": 3},
                suggestions=["Fix syntax error"]
            ),
            ReviewResult(
                decision=ReviewDecision.ACCEPT,
                feedback="All tests passed",
                confidence=0.95,
                test_summary={"all_passed": True, "total_tests": 3},
                suggestions=[]
            )
        ])
        
        mock_tool_manager = Mock()
        mock_tool_manager.apply_patch = AsyncMock()
        mock_project_manager = Mock()
        mock_project_manager.get_code_path = Mock(return_value=Path(temp_project_dir))
        
        mock_test_results = [
            Mock(test_type="pest", status="failed", output="Syntax error", details=None)
        ]
        
        step = Step(id=1, description="Create basic structure", type_action=ActionType.CREATE_FILE)
        execution_context = {
            "plan_revision_count": 0,
            "max_plan_revisions": 2
        }
        
        with patch('backend.server.db', mock_db), \
             patch('backend.server.state_manager', mock_state_manager), \
             patch('backend.server.developer_agent', developer), \
             patch('backend.server.reviewer_agent', reviewer), \
             patch('backend.server.tool_manager', mock_tool_manager), \
             patch('backend.server.project_manager', mock_project_manager), \
             patch('backend.server.run_comprehensive_tests', AsyncMock(return_value=mock_test_results)):
            
            result = await _execute_step_with_agents(
                "test-run-123", sample_run, step, 0, execution_context
            )
            
            assert result is True
            assert developer.generate_patch.call_count == 2  # Premier échec + retry
            assert reviewer.review_step_result.call_count == 2
    
    @pytest.mark.asyncio
    async def test_finalize_execution_success(
        self, mock_db, mock_state_manager, sample_run, temp_project_dir
    ):
        """Test de finalisation réussie."""
        # Créer des fichiers pour simuler un projet Laravel
        os.makedirs(os.path.join(temp_project_dir, "app"), exist_ok=True)
        with open(os.path.join(temp_project_dir, "composer.json"), "w") as f:
            f.write('{"name": "test"}')
        
        mock_project_manager = Mock()
        mock_project_manager.get_code_path = Mock(return_value=Path(temp_project_dir))
        
        execution_context = {
            "start_time": datetime.now(timezone.utc),
            "plan_revision_count": 0
        }
        
        with patch('backend.server.state_manager', mock_state_manager), \
             patch('backend.server.project_manager', mock_project_manager):
            
            await _finalize_execution(
                "test-run-123", sample_run, 3, True, execution_context
            )
            
            # Vérifier que le statut a été mis à jour vers COMPLETED
            mock_state_manager.update_run_status.assert_called_with(
                "test-run-123", RunStatus.COMPLETED
            )
    
    @pytest.mark.asyncio
    async def test_finalize_execution_no_files(
        self, mock_db, mock_state_manager, sample_run, temp_project_dir
    ):
        """Test de finalisation sans fichiers générés."""
        # Répertoire vide (pas de fichiers générés)
        mock_project_manager = Mock()
        mock_project_manager.get_code_path = Mock(return_value=Path(temp_project_dir))
        
        execution_context = {
            "start_time": datetime.now(timezone.utc),
            "plan_revision_count": 0
        }
        
        with patch('backend.server.state_manager', mock_state_manager), \
             patch('backend.server.project_manager', mock_project_manager):
            
            await _finalize_execution(
                "test-run-123", sample_run, 3, True, execution_context
            )
            
            # Vérifier que le statut a été mis à jour vers FAILED
            mock_state_manager.update_run_status.assert_called_with(
                "test-run-123", RunStatus.FAILED
            )


class TestAPICompatibility:
    """Tests de compatibilité API."""
    
    @pytest.mark.asyncio
    async def test_api_endpoints_exist(self):
        """Vérifier que les nouveaux endpoints existent."""
        from backend.server import api_router
        
        # Récupérer toutes les routes
        routes = [route.path for route in api_router.routes]
        
        # Vérifier les nouveaux endpoints
        assert "/runs/{run_id}/agent-conversations" in routes
        assert "/runs/{run_id}/validate-plan" in routes
        assert "/runs/{run_id}/validate-step" in routes
        assert "/runs/{run_id}/interrupt" in routes
        assert "/runs/{run_id}/execution-context" in routes
    
    def test_run_model_compatibility(self):
        """Vérifier que le modèle Run est toujours compatible."""
        # Test de création d'un Run avec les anciens paramètres
        run = Run(
            goal="Test goal",
            stack="laravel",
            max_steps=10,
            max_retries_per_step=2,
            daily_budget_eur=5.0
        )
        
        assert run.goal == "Test goal"
        assert run.stack == "laravel"
        assert run.status == RunStatus.PENDING
        assert run.current_step == 0
        assert hasattr(run, 'id')
        assert hasattr(run, 'created_at')
        assert hasattr(run, 'updated_at')


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v"])