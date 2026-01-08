"""
GitHub Actions Monitor
Integrates with GitHub API to monitor and control workflows
"""

from github import Github
from typing import Dict, List, Optional
import os
import logging
import base64
import asyncio

logger = logging.getLogger(__name__)


class GitHubMonitor:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_repo = os.getenv("GITHUB_REPO")
        
        if not self.github_token or not self.github_repo:
            raise ValueError("GITHUB_TOKEN and GITHUB_REPO must be set")
        
        self.gh = Github(self.github_token)
        self.repo = self.gh.get_repo(self.github_repo)
        
        logger.info(f"GitHub Monitor initialized for {self.github_repo}")
    
    def check_connection(self) -> bool:
        """Check if GitHub API connection is working"""
        try:
            self.gh.get_user().login
            return True
        except Exception as e:
            logger.error(f"GitHub connection check failed: {e}")
            return False
    
    async def get_active_workflows(self) -> List[Dict]:
        """
        Get all currently running workflow runs
        """
        try:
            workflows = self.repo.get_workflow_runs(
                status="in_progress"
            )
            
            active_runs = []
            for run in workflows:
                active_runs.append({
                    'id': run.id,
                    'name': run.name,
                    'status': run.status,
                    'created_at': run.created_at.isoformat(),
                    'head_branch': run.head_branch,
                    'head_sha': run.head_sha,
                    'event': run.event,
                    'author': run.head_commit.author.name if run.head_commit else None,
                    'url': run.html_url
                })
            
            return active_runs
        
        except Exception as e:
            logger.error(f"Error fetching active workflows: {e}")
            return []
    
    async def fetch_workflow_logs(self, run_id: str) -> str:
        """
        Fetch logs from a workflow run
        Returns combined logs from all jobs
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            
            # Get all jobs for this run
            jobs = run.jobs()
            
            all_logs = []
            for job in jobs:
                all_logs.append(f"\n=== Job: {job.name} (Status: {job.conclusion}) ===\n")
                
                # Get steps
                for step in job.steps:
                    all_logs.append(f"\n--- Step: {step.name} ---")
                    all_logs.append(f"Status: {step.conclusion}")
                    if step.conclusion == "failure":
                        all_logs.append("✗ FAILED")
            
            # Get run logs (download URL)
            try:
                logs_url = run.logs_url
                # Note: In production, you'd actually download and parse the logs
                # For now, we'll use job information
                all_logs.append(f"\nLogs URL: {logs_url}")
            except:
                pass
            
            return "\n".join(all_logs)
        
        except Exception as e:
            logger.error(f"Error fetching workflow logs: {e}")
            return f"Error fetching logs: {e}"
    
    async def rerun_workflow(self, run_id: str) -> bool:
        """
        Re-trigger a failed workflow run
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            run.rerun()
            logger.info(f"✅ Re-triggered workflow run {run_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error re-running workflow: {e}")
            return False
    
    async def get_workflow_status(self, run_id: str) -> Optional[Dict]:
        """
        Get status of a specific workflow run
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            
            return {
                'id': run.id,
                'name': run.name,
                'status': run.status,
                'conclusion': run.conclusion,
                'created_at': run.created_at.isoformat(),
                'updated_at': run.updated_at.isoformat(),
                'head_branch': run.head_branch,
                'head_sha': run.head_sha,
                'url': run.html_url
            }
        
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return None
    
    async def cancel_workflow(self, run_id: str) -> bool:
        """
        Cancel a running workflow
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            run.cancel()
            logger.info(f"Cancelled workflow run {run_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error cancelling workflow: {e}")
            return False
    
    async def get_recent_failures(self, limit: int = 10) -> List[Dict]:
        """
        Get recent failed workflow runs
        """
        try:
            workflows = self.repo.get_workflow_runs(
                status="completed",
                conclusion="failure"
            )
            
            failures = []
            for i, run in enumerate(workflows):
                if i >= limit:
                    break
                
                failures.append({
                    'id': run.id,
                    'name': run.name,
                    'conclusion': run.conclusion,
                    'created_at': run.created_at.isoformat(),
                    'head_branch': run.head_branch,
                    'head_sha': run.head_sha,
                    'author': run.head_commit.author.name if run.head_commit else None,
                    'url': run.html_url
                })
            
            return failures
        
        except Exception as e:
            logger.error(f"Error fetching recent failures: {e}")
            return []
    
    def get_file_content(self, file_path: str, branch: str = "main") -> Optional[str]:
        """
        Get content of a file from repository
        """
        try:
            file_content = self.repo.get_contents(file_path, ref=branch)
            return file_content.decoded_content.decode()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def update_file(
        self,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main"
    ) -> bool:
        """
        Update a file in the repository
        """
        try:
            file = self.repo.get_contents(file_path, ref=branch)
            self.repo.update_file(
                file_path,
                commit_message,
                content,
                file.sha,
                branch=branch
            )
            logger.info(f"Updated {file_path} on branch {branch}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating file: {e}")
            return False
    
    def create_file(
        self,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = "main"
    ) -> bool:
        """
        Create a new file in the repository
        """
        try:
            self.repo.create_file(
                file_path,
                commit_message,
                content,
                branch=branch
            )
            logger.info(f"Created {file_path} on branch {branch}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating file: {e}")
            return False
    
    async def create_issue(
        self,
        title: str,
        body: str,
        labels: List[str] = None
    ) -> bool:
        """
        Create an issue for manual intervention
        """
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels or ["auto-healing", "needs-attention"]
            )
            logger.info(f"Created issue #{issue.number}: {title}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return False
    
    async def add_comment_to_commit(
        self,
        commit_sha: str,
        comment: str
    ) -> bool:
        """
        Add a comment to a commit (for notifications)
        """
        try:
            commit = self.repo.get_commit(commit_sha)
            commit.create_comment(comment)
            logger.info(f"Added comment to commit {commit_sha[:7]}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            return False
    
    async def get_commit_info(self, commit_sha: str) -> Optional[Dict]:
        """
        Get information about a commit
        """
        try:
            commit = self.repo.get_commit(commit_sha)
            
            return {
                'sha': commit.sha,
                'author': commit.commit.author.name,
                'email': commit.commit.author.email,
                'message': commit.commit.message,
                'date': commit.commit.author.date.isoformat(),
                'files_changed': len(commit.files),
                'additions': commit.stats.additions,
                'deletions': commit.stats.deletions,
                'url': commit.html_url
            }
        
        except Exception as e:
            logger.error(f"Error getting commit info: {e}")
            return None
    
    async def get_pull_request_for_commit(self, commit_sha: str) -> Optional[Dict]:
        """
        Get pull request associated with a commit
        """
        try:
            prs = self.repo.get_pulls(state="all")
            
            for pr in prs:
                if pr.merge_commit_sha == commit_sha or \
                   any(commit.sha == commit_sha for commit in pr.get_commits()):
                    return {
                        'number': pr.number,
                        'title': pr.title,
                        'state': pr.state,
                        'url': pr.html_url,
                        'author': pr.user.login
                    }
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding PR for commit: {e}")
            return None
    
    async def create_branch(self, branch_name: str, from_branch: str = "main") -> bool:
        """
        Create a new branch
        """
        try:
            source = self.repo.get_branch(from_branch)
            self.repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha
            )
            logger.info(f"Created branch {branch_name} from {from_branch}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating branch: {e}")
            return False
    
    async def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main"
    ) -> Optional[int]:
        """
        Create a pull request with auto-healing changes
        """
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            logger.info(f"Created PR #{pr.number}: {title}")
            return pr.number
        
        except Exception as e:
            logger.error(f"Error creating PR: {e}")
            return None
    
    async def get_workflow_artifacts(self, run_id: str) -> List[Dict]:
        """
        Get artifacts from a workflow run
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            artifacts = run.get_artifacts()
            
            return [
                {
                    'id': artifact.id,
                    'name': artifact.name,
                    'size': artifact.size_in_bytes,
                    'created_at': artifact.created_at.isoformat(),
                    'download_url': artifact.archive_download_url
                }
                for artifact in artifacts
            ]
        
        except Exception as e:
            logger.error(f"Error getting artifacts: {e}")
            return []
    
    async def get_rate_limit(self) -> Dict:
        """
        Get current GitHub API rate limit status
        """
        try:
            rate_limit = self.gh.get_rate_limit()
            
            return {
                'core': {
                    'limit': rate_limit.core.limit,
                    'remaining': rate_limit.core.remaining,
                    'reset': rate_limit.core.reset.isoformat()
                },
                'search': {
                    'limit': rate_limit.search.limit,
                    'remaining': rate_limit.search.remaining,
                    'reset': rate_limit.search.reset.isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting rate limit: {e}")
            return {}
    
    async def analyze_test_results(self, run_id: str) -> Dict:
        """
        Analyze test results from a workflow run
        """
        try:
            run = self.repo.get_workflow_run(int(run_id))
            jobs = run.jobs()
            
            test_results = {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'failed_tests': [],
                'flaky_tests': []
            }
            
            for job in jobs:
                for step in job.steps:
                    # Parse test output (simplified)
                    if 'test' in step.name.lower():
                        if step.conclusion == 'success':
                            test_results['passed'] += 1
                        elif step.conclusion == 'failure':
                            test_results['failed'] += 1
                            test_results['failed_tests'].append({
                                'name': step.name,
                                'job': job.name
                            })
                        elif step.conclusion == 'skipped':
                            test_results['skipped'] += 1
                
                test_results['total_tests'] = (
                    test_results['passed'] + 
                    test_results['failed'] + 
                    test_results['skipped']
                )
            
            return test_results
        
        except Exception as e:
            logger.error(f"Error analyzing test results: {e}")
            return {}
    
    async def get_deployment_status(self) -> List[Dict]:
        """
        Get recent deployment status
        """
        try:
            deployments = self.repo.get_deployments()
            
            status_list = []
            for i, deployment in enumerate(deployments):
                if i >= 5:  # Last 5 deployments
                    break
                
                statuses = deployment.get_statuses()
                latest_status = list(statuses)[0] if statuses.totalCount > 0 else None
                
                status_list.append({
                    'id': deployment.id,
                    'environment': deployment.environment,
                    'ref': deployment.ref,
                    'created_at': deployment.created_at.isoformat(),
                    'status': latest_status.state if latest_status else 'unknown',
                    'description': latest_status.description if latest_status else None
                })
            
            return status_list
        
        except Exception as e:
            logger.error(f"Error getting deployment status: {e}")
            return []
    
    def get_repository_stats(self) -> Dict:
        """
        Get repository statistics
        """
        try:
            return {
                'name': self.repo.name,
                'full_name': self.repo.full_name,
                'description': self.repo.description,
                'stars': self.repo.stargazers_count,
                'forks': self.repo.forks_count,
                'open_issues': self.repo.open_issues_count,
                'default_branch': self.repo.default_branch,
                'language': self.repo.language,
                'size': self.repo.size,
                'created_at': self.repo.created_at.isoformat(),
                'updated_at': self.repo.updated_at.isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error getting repository stats: {e}")
            return {}


class GitHubWebhookHandler:
    """
    Handle GitHub webhook events
    """
    
    @staticmethod
    def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify GitHub webhook signature
        """
        import hmac
        import hashlib
        
        if not signature:
            return False
        
        hash_obj = hmac.new(
            secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = f"sha256={hash_obj.hexdigest()}"
        
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def parse_event(event_type: str, payload: Dict) -> Dict:
        """
        Parse different types of GitHub webhook events
        """
        if event_type == "workflow_run":
            return {
                'event': 'workflow_run',
                'action': payload.get('action'),
                'workflow_run': payload.get('workflow_run'),
                'repository': payload.get('repository')
            }
        
        elif event_type == "push":
            return {
                'event': 'push',
                'ref': payload.get('ref'),
                'commits': payload.get('commits'),
                'repository': payload.get('repository'),
                'pusher': payload.get('pusher')
            }
        
        elif event_type == "pull_request":
            return {
                'event': 'pull_request',
                'action': payload.get('action'),
                'pull_request': payload.get('pull_request'),
                'repository': payload.get('repository')
            }
        
        return {
            'event': event_type,
            'payload': payload
        }
