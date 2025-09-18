import os
import logging
import asyncio
import httpx
import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import quote
import git
from git import Repo, InvalidGitRepositoryError

logger = logging.getLogger(__name__)

class GitHubIntegration:
    def __init__(self):
        self.client_id = os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = os.getenv("GITHUB_CLIENT_SECRET") 
        self.redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
        self.api_base_url = "https://api.github.com"
        
    async def get_oauth_url(self, state: str = None) -> str:
        """Get GitHub OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "repo,user:email",
            "state": state or ""
        }
        
        query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"https://github.com/login/oauth/authorize?{query_string}"
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange OAuth code for access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://github.com/login/oauth/access_token",
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"GitHub token exchange failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error exchanging GitHub code: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get GitHub user information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/user",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"GitHub user info failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting GitHub user info: {e}")
            return None
    
    async def list_repositories(self, access_token: str, per_page: int = 30) -> List[Dict[str, Any]]:
        """List user repositories"""
        try:
            repos = []
            page = 1
            
            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(
                        f"{self.api_base_url}/user/repos",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={
                            "sort": "updated",
                            "direction": "desc", 
                            "per_page": per_page,
                            "page": page
                        }
                    )
                    
                    if response.status_code != 200:
                        break
                        
                    page_repos = response.json()
                    if not page_repos:
                        break
                        
                    repos.extend(page_repos)
                    
                    if len(page_repos) < per_page:
                        break
                        
                    page += 1
            
            return repos[:100]  # Limit to 100 repos
            
        except Exception as e:
            logger.error(f"Error listing repositories: {e}")
            return []
    
    async def clone_repository(self, repo_url: str, local_path: Path, access_token: str = None) -> bool:
        """Clone repository to local path"""
        try:
            # Prepare authenticated URL if token provided
            if access_token and repo_url.startswith("https://github.com/"):
                repo_url = repo_url.replace("https://github.com/", f"https://{access_token}@github.com/")
            
            # Clone repository
            Repo.clone_from(repo_url, local_path)
            
            logger.info(f"Successfully cloned repository to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            return False
    
    async def init_git_repo(self, local_path: Path) -> bool:
        """Initialize git repository"""
        try:
            if (local_path / ".git").exists():
                return True
                
            Repo.init(local_path)
            logger.info(f"Initialized git repository at {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing git repo: {e}")
            return False
    
    async def add_remote(self, local_path: Path, remote_name: str, remote_url: str) -> bool:
        """Add remote to git repository"""
        try:
            repo = Repo(local_path)
            
            # Remove existing remote if exists
            if remote_name in [remote.name for remote in repo.remotes]:
                repo.delete_remote(remote_name)
            
            # Add new remote
            repo.create_remote(remote_name, remote_url)
            
            logger.info(f"Added remote {remote_name}: {remote_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding remote: {e}")
            return False
    
    async def commit_changes(self, local_path: Path, message: str, author_name: str = None, author_email: str = None) -> bool:
        """Commit changes to git repository"""
        try:
            repo = Repo(local_path)
            
            # Add all changes
            repo.git.add(A=True)
            
            # Check if there are changes to commit
            if not repo.is_dirty() and not repo.untracked_files:
                logger.info("No changes to commit")
                return True
            
            # Set author if provided
            if author_name and author_email:
                repo.config_writer().set_value("user", "name", author_name).release()
                repo.config_writer().set_value("user", "email", author_email).release()
            
            # Commit changes
            repo.index.commit(message)
            
            logger.info(f"Committed changes: {message}")
            return True
            
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            return False
    
    async def push_changes(self, local_path: Path, remote_name: str = "origin", branch: str = "main", access_token: str = None) -> bool:
        """Push changes to remote repository"""
        try:
            repo = Repo(local_path)
            
            # Update remote URL with token if provided
            if access_token:
                remote = repo.remote(remote_name)
                remote_url = remote.url
                if remote_url.startswith("https://github.com/"):
                    authenticated_url = remote_url.replace("https://github.com/", f"https://{access_token}@github.com/")
                    remote.set_url(authenticated_url)
            
            # Push changes
            origin = repo.remote(remote_name)
            origin.push(branch)
            
            logger.info(f"Pushed changes to {remote_name}/{branch}")
            return True
            
        except Exception as e:
            logger.error(f"Error pushing changes: {e}")
            return False
    
    async def pull_changes(self, local_path: Path, remote_name: str = "origin", branch: str = "main") -> bool:
        """Pull changes from remote repository"""
        try:
            repo = Repo(local_path)
            
            # Fetch and pull changes
            origin = repo.remote(remote_name)
            origin.fetch()
            origin.pull(branch)
            
            logger.info(f"Pulled changes from {remote_name}/{branch}")
            return True
            
        except Exception as e:
            logger.error(f"Error pulling changes: {e}")
            return False
    
    async def create_branch(self, local_path: Path, branch_name: str) -> bool:
        """Create and checkout new branch"""
        try:
            repo = Repo(local_path)
            
            # Create new branch
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            
            logger.info(f"Created and checked out branch: {branch_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating branch: {e}")
            return False
    
    async def checkout_branch(self, local_path: Path, branch_name: str) -> bool:
        """Checkout existing branch"""
        try:
            repo = Repo(local_path)
            repo.git.checkout(branch_name)
            
            logger.info(f"Checked out branch: {branch_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error checking out branch: {e}")
            return False
    
    async def create_pull_request(self, access_token: str, repo_owner: str, repo_name: str, 
                                title: str, body: str, head_branch: str, base_branch: str = "main") -> Optional[Dict[str, Any]]:
        """Create pull request"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/pulls",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json"
                    },
                    json={
                        "title": title,
                        "body": body,
                        "head": head_branch,
                        "base": base_branch
                    }
                )
                
                if response.status_code == 201:
                    pr = response.json()
                    logger.info(f"Created pull request #{pr['number']}: {title}")
                    return pr
                else:
                    logger.error(f"Failed to create pull request: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating pull request: {e}")
            return None
    
    async def get_repository_contents(self, access_token: str, repo_owner: str, repo_name: str, path: str = "") -> List[Dict[str, Any]]:
        """Get repository contents"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/contents/{path}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get repository contents: {response.text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting repository contents: {e}")
            return []
    
    async def get_file_content(self, access_token: str, repo_owner: str, repo_name: str, file_path: str) -> Optional[str]:
        """Get file content from repository"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/contents/{file_path}",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    file_data = response.json()
                    if file_data.get("encoding") == "base64":
                        content = base64.b64decode(file_data["content"]).decode("utf-8")
                        return content
                    return file_data.get("content", "")
                else:
                    logger.error(f"Failed to get file content: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None
    
    async def get_repository_languages(self, access_token: str, repo_owner: str, repo_name: str) -> Dict[str, int]:
        """Get repository programming languages"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/languages",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get repository languages: {response.text}")
                    return {}
                    
        except Exception as e:
            logger.error(f"Error getting repository languages: {e}")
            return {}
    
    async def analyze_repository_structure(self, access_token: str, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Analyze repository structure and detect stack"""
        try:
            # Get languages
            languages = await self.get_repository_languages(access_token, repo_owner, repo_name)
            
            # Get root contents
            contents = await self.get_repository_contents(access_token, repo_owner, repo_name)
            
            # Detect stack based on files and languages
            stack = "unknown"
            framework = None
            
            file_names = [item["name"].lower() for item in contents if item["type"] == "file"]
            
            # Laravel detection
            if "composer.json" in file_names or "artisan" in file_names:
                stack = "laravel"
                framework = "Laravel"
            # React detection  
            elif "package.json" in file_names and any("react" in lang.lower() for lang in languages.keys()):
                stack = "react"
                framework = "React"
            # Vue detection
            elif "package.json" in file_names and any("vue" in lang.lower() for lang in languages.keys()):
                stack = "vue"
                framework = "Vue.js"
            # Python detection
            elif "requirements.txt" in file_names or "setup.py" in file_names or "Python" in languages:
                stack = "python"
                if "main.py" in file_names or "app.py" in file_names:
                    framework = "FastAPI/Flask"
            # Node.js detection
            elif "package.json" in file_names:
                stack = "node"
                framework = "Node.js"
            
            return {
                "stack": stack,
                "framework": framework,
                "languages": languages,
                "files": file_names,
                "estimated_complexity": len(contents)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing repository structure: {e}")
            return {
                "stack": "unknown",
                "framework": None,
                "languages": {},
                "files": [],
                "estimated_complexity": 0
            }
    
    def get_repo_info_from_url(self, repo_url: str) -> Optional[Dict[str, str]]:
        """Extract owner and repo name from GitHub URL"""
        try:
            if "github.com/" in repo_url:
                # Handle both HTTPS and SSH URLs
                if repo_url.startswith("git@github.com:"):
                    # SSH format: git@github.com:owner/repo.git
                    parts = repo_url.replace("git@github.com:", "").replace(".git", "").split("/")
                else:
                    # HTTPS format: https://github.com/owner/repo or https://github.com/owner/repo.git
                    parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
                
                if len(parts) >= 2:
                    return {
                        "owner": parts[0],
                        "repo": parts[1]
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing repo URL: {e}")
            return None