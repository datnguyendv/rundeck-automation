import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from git import Repo, GitCommandError, InvalidGitRepositoryError
from .exceptions import BaseAppException
from .logger import setup_logger

logger = setup_logger(__name__)


class GitOperationError(BaseAppException):
    pass


class GitClient:
    def __init__(
        self, repo_url: str, username: Optional[str] = None, token: Optional[str] = None
    ):
        self.repo_url = repo_url
        self.username = username
        self.token = token

        # Setup authentication URL for HTTPS repos
        if username and token and repo_url.startswith("https://"):
            # Format: https://username:token@github.com/user/repo.git
            self.auth_url = repo_url.replace("https://", f"https://{username}:{token}@")
        else:
            self.auth_url = repo_url

        logger.info(f"Initialized GitClient for repo: {repo_url}")

    def clone(self, local_path: Path, branch: str = "main", depth: int = 1) -> Repo:
        try:
            local_path = Path(local_path)

            # Remove existing directory if exists
            if local_path.exists():
                logger.info(f"Removing existing directory: {local_path}")
                shutil.rmtree(local_path)

            # Create parent directory
            local_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Cloning branch '{branch}' to {local_path}")
            logger.debug(f"Repository: {self.repo_url}")

            # Clone repository
            if depth:
                repo = Repo.clone_from(
                    url=self.auth_url,
                    to_path=str(local_path),
                    branch=branch,
                    depth=depth,
                )
            else:
                repo = Repo.clone_from(
                    url=self.auth_url, to_path=str(local_path), branch=branch
                )

            logger.info(f"✅ Successfully cloned branch '{branch}' to {local_path}")
            logger.info(f"Current branch: {repo.active_branch.name}")
            logger.info(
                f"Latest commit: {repo.head.commit.hexsha[:7]} - {repo.head.commit.message.strip()}"
            )

            return repo

        except GitCommandError as e:
            error_msg = (
                f"Git clone failed: {e.stderr if hasattr(e, 'stderr') else str(e)}"
            )
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during git clone: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def get_repo(self, repo_path: Path) -> Repo:
        try:
            repo = Repo(str(repo_path))
            logger.debug(f"Loaded repo from: {repo_path}")
            return repo
        except InvalidGitRepositoryError as e:
            error_msg = f"Not a valid git repository: {repo_path}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load repository: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def add_file(self, repo_path: Path, file_path: str) -> bool:
        try:
            repo = self.get_repo(repo_path)

            logger.info(f"Adding file to git: {file_path}")
            repo.index.add([file_path])

            logger.info(f"✅ Successfully added file: {file_path}")
            return True

        except GitCommandError as e:
            error_msg = f"Git add failed: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to add file: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def commit(
        self,
        repo_path: Path,
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ) -> bool:
        try:
            repo = self.get_repo(repo_path)

            # Configure git user if provided
            if author_name and author_email:
                with repo.config_writer() as git_config:
                    git_config.set_value("user", "name", author_name)
                    git_config.set_value("user", "email", author_email)
                logger.debug(f"Set git author: {author_name} <{author_email}>")

            # Check if there are changes to commit
            if not repo.is_dirty() and not repo.untracked_files:
                logger.info("No changes to commit")
                return True

            logger.info(f"Committing changes: {message}")

            # Commit changes
            if author_name and author_email:
                from git import Actor

                author = Actor(author_name, author_email)
                commit = repo.index.commit(message, author=author)
            else:
                commit = repo.index.commit(message)

            logger.info(f"✅ Successfully committed: {commit.hexsha[:7]}")
            logger.debug(f"Commit message: {commit.message.strip()}")

            return True

        except GitCommandError as e:
            error_msg = f"Git commit failed: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to commit: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def push(
        self, repo_path: Path, branch: Optional[str] = None, force: bool = False
    ) -> bool:
        try:
            repo = self.get_repo(repo_path)

            # Get current branch if not specified
            if not branch:
                branch = repo.active_branch.name

            logger.info(f"Pushing changes to branch: {branch}")

            # Push to remote
            origin = repo.remote(name="origin")

            if force:
                logger.warning("⚠️  Force pushing to remote")
                push_info = origin.push(refspec=f"{branch}:{branch}", force=True)
            else:
                push_info = origin.push(refspec=f"{branch}:{branch}")

            # Check push result
            for info in push_info:
                if info.flags & info.ERROR:
                    error_msg = f"Push failed: {info.summary}"
                    logger.error(error_msg)
                    raise GitOperationError(error_msg)

            logger.info(f"✅ Successfully pushed to branch: {branch}")
            return True

        except GitCommandError as e:
            error_msg = f"Git push failed: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to push: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def get_current_branch(self, repo_path: Path) -> str:
        try:
            repo = self.get_repo(repo_path)
            branch = repo.active_branch.name
            logger.info(f"Current branch: {branch}")
            return branch

        except Exception as e:
            error_msg = f"Failed to get current branch: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def get_status(self, repo_path: Path) -> Dict[str, Any]:
        try:
            repo = self.get_repo(repo_path)

            status = {
                "branch": repo.active_branch.name,
                "is_dirty": repo.is_dirty(),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")],
                "latest_commit": {
                    "sha": repo.head.commit.hexsha[:7],
                    "message": repo.head.commit.message.strip(),
                    "author": str(repo.head.commit.author),
                    "date": repo.head.commit.committed_datetime.isoformat(),
                },
            }

            logger.debug(f"Repository status: {status}")
            return status

        except Exception as e:
            error_msg = f"Failed to get status: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e

    def commit_and_push(
        self,
        repo_path: Path,
        file_path: str,
        commit_message: str,
        branch: Optional[str] = None,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ) -> bool:
        try:
            # Get current branch if not specified
            if not branch:
                branch = self.get_current_branch(repo_path)

            logger.info(f"Starting git workflow for file: {file_path}")

            # Add file
            self.add_file(repo_path, file_path)

            # Commit changes
            self.commit(repo_path, commit_message, author_name, author_email)

            # Push changes
            self.push(repo_path, branch)

            logger.info("✅ Complete git workflow finished successfully")
            return True

        except GitOperationError:
            raise
        except Exception as e:
            error_msg = f"Git workflow failed: {e}"
            logger.error(error_msg)
            raise GitOperationError(error_msg) from e
