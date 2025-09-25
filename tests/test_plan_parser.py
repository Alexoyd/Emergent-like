import pytest

from backend.orchestrator.plan_parser import (
    PlanParser,
    Step,
    ActionType,
    PlanParsingError,
)


class TestPlanParser:
    """Tests for the PlanParser functionality."""

    def setup_method(self):
        self.parser = PlanParser()

    def test_parse_simple_numbered_plan(self):
        """Test parsing of a simple numbered plan."""
        plan_text = """
        1. Create user model file
        2. Add authentication middleware
        3. Update database schema
        4. Write unit tests
        """
        steps = self.parser.parse_plan(plan_text)
        assert len(steps) == 4
        assert steps[0].description == "Create user model file"
        assert steps[1].description == "Add authentication middleware"
        assert steps[0].type_action == ActionType.CREATE_FILE
        # 'add' should be treated as a modification
        assert steps[1].type_action == ActionType.MODIFY_FILE

    def test_parse_markdown_plan(self):
        """Test parsing of a plan formatted using markdown bullets."""
        plan_text = """
        ## Development Plan

        - Create app/Models/User.php file with authentication
        - Modify routes/api.php to add user endpoints
        - Install passport package for OAuth
        - Run tests to validate changes

        ### Additional Steps
        * Configure .env file
        * Deploy to staging environment
        """
        steps = self.parser.parse_plan(plan_text)
        # We expect at least four steps from the bullet items
        assert len(steps) >= 4
        # Check that a user model file appears in at least one step's file list
        assert any(
            any("User.php" in f for f in step.files_involved) for step in steps
        )
        # Ensure at least one install package action is detected
        assert any(step.type_action == ActionType.INSTALL_PACKAGE for step in steps)
        # Ensure at least one run tests action is detected
        assert any(step.type_action == ActionType.RUN_TESTS for step in steps)

    def test_parse_detailed_plan_with_metadata(self):
        """Test parsing of a detailed plan containing metadata."""
        plan_text = """
        1. Create authentication controller - Duration: 30 minutes - Priority: High
           Files: app/Http/Controllers/AuthController.php
           Command: `php artisan make:controller AuthController`
           Success criteria: Controller created with login/logout methods

        2. Update user routes - Duration: 15 minutes - Priority: Medium
           Files: routes/api.php, routes/web.php
           Depends on: Step 1
           Success criteria: Routes properly configured and tested
        """
        steps = self.parser.parse_plan(plan_text)
        assert len(steps) == 2
        # Step 1 assertions
        assert steps[0].estimated_duration == 30
        assert steps[0].priority == 1  # High priority
        assert "app/Http/Controllers/AuthController.php" in steps[0].files_involved
        assert any(
            cmd.startswith("php artisan make:controller") for cmd in steps[0].commands
        )
        # Step 2 assertions
        assert steps[1].estimated_duration == 15
        assert steps[1].priority == 2  # Medium priority
        # Dependencies should list at least one dependency
        assert steps[1].dependencies
        assert steps[1].dependencies == [1]
        assert "routes/api.php" in steps[1].files_involved
        assert "routes/web.php" in steps[1].files_involved

    def test_parse_french_plan(self):
        """Test parsing of a plan written in French."""
        plan_text = """
        Étape 1: Créer le modèle utilisateur
        Étape 2: Modifier la configuration de la base de données
        Étape 3: Installer les dépendances composer
        Étape 4: Tester l'application
        """
        steps = self.parser.parse_plan(plan_text)
        assert len(steps) == 4
        assert "utilisateur" in steps[0].description.lower()
        # Step 3 should be detected as install package
        assert steps[2].type_action == ActionType.INSTALL_PACKAGE
        # Step 4 should be detected as run tests
        assert steps[3].type_action == ActionType.RUN_TESTS

    def test_parse_complex_plan_with_commands(self):
        """Test parsing of a plan containing code blocks and multiple commands."""
        plan_text = """
        1. Setup Laravel project structure
           ```bash
           composer create-project laravel/laravel myapp
           cd myapp
           php artisan key:generate
           ```

        2. Configure database connection
           Files: .env, config/database.php
           Run: `php artisan migrate`

        3. Install and configure authentication
           Command: `composer require laravel/sanctum`
           Then run: `php artisan vendor:publish --provider="Laravel\\Sanctum\\SanctumServiceProvider"`
        """
        steps = self.parser.parse_plan(plan_text)
        assert len(steps) == 3
        # Step 1 should capture multiple commands
        assert len(steps[0].commands) >= 3
        # Step 2 should list .env as a file involved
        assert any(".env" == f for f in steps[1].files_involved)
        # Step 3 should include a composer require command
        assert any("composer require" in cmd for cmd in steps[2].commands)

    def test_parse_plan_with_dependencies(self):
        """Test parsing of dependencies between steps."""
        plan_text = """
        1. Create database migration
        2. Run migration (depends on step 1)
        3. Create model (after step 2)
        4. Write tests (requires step 3)
        """
        steps = self.parser.parse_plan(plan_text)
        # Verify that dependencies are captured
        assert steps[1].dependencies == [1]
        assert steps[2].dependencies == [2]
        assert steps[3].dependencies == [3]

    def test_parse_empty_plan_error(self):
        """Test that an empty plan raises a PlanParsingError."""
        with pytest.raises(PlanParsingError):
            self.parser.parse_plan("")
        with pytest.raises(PlanParsingError):
            self.parser.parse_plan("   \n\n   ")

    def test_parse_invalid_plan_fallback(self):
        """Test fallback behaviour when the plan is unstructured."""
        plan_text = """
        This is not a properly formatted plan.
        It has no numbered steps or clear structure.
        But it should still create some basic steps.
        """
        steps = self.parser.parse_plan(plan_text)
        assert len(steps) >= 1
        assert steps[0].description

    def test_action_type_detection(self):
        """Test detection of action types based on description."""
        test_cases = [
            ("Create new controller file", ActionType.CREATE_FILE),
            ("Modify existing user model", ActionType.MODIFY_FILE),
            ("Delete old migration file", ActionType.DELETE_FILE),
            ("Run unit tests", ActionType.RUN_TESTS),
            ("Install composer packages", ActionType.INSTALL_PACKAGE),
            ("Configure environment variables", ActionType.CONFIGURE),
            ("Debug authentication issue", ActionType.DEBUG),
            ("Refactor user service", ActionType.REFACTOR),
            ("Something completely different", ActionType.OTHER),
        ]
        for description, expected_type in test_cases:
            detected_type = self.parser._detect_action_type(description)
            assert (
                detected_type == expected_type
            ), f"Failed for: {description}; got {detected_type}, expected {expected_type}"

    def test_file_extraction(self):
        """Test extraction of file names from textual descriptions."""
        test_cases = [
            ("Create app/Models/User.php", ["app/Models/User.php"]),
            ("Modify routes/api.php and routes/web.php", ["routes/api.php", "routes/web.php"]),
            ("Files: config/app.php, .env, database.json", ["config/app.php", ".env", "database.json"]),
            ("Update UserController.php", ["UserController.php"]),
        ]
        for text, expected_files in test_cases:
            extracted = self.parser._extract_files(text)
            for expected in expected_files:
                assert expected in extracted, f"Missing {expected} in {extracted}"

    def test_duration_and_priority_extraction(self):
        """Test extraction of durations and priorities from metadata strings."""
        # Duration extraction
        step = Step(id=1, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(step, ["Duration: 30 minutes"])
        assert step.estimated_duration == 30
        step2 = Step(id=2, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(step2, ["Time: 2 hours"])
        assert step2.estimated_duration == 120
        step3 = Step(id=3, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(step3, ["Durée: 1 heure"])
        assert step3.estimated_duration == 60
        # Priority extraction
        p1 = Step(id=4, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(p1, ["Priority: High"])
        assert p1.priority == 1
        p2 = Step(id=5, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(p2, ["Priorité: moyenne"])
        assert p2.priority == 2
        p3 = Step(id=6, description="", type_action=ActionType.OTHER)
        self.parser._parse_metadata(p3, ["Priority: 3"])
        assert p3.priority == 3
