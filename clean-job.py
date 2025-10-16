import argparse
import sys
from pathlib import Path
from typing import Optional

from utils import (
    setup_logger,
    RundeckClient,
    FileOperations,
    RundeckAPIError,
    FileOperationError,
    AppConfig
)

logger = setup_logger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Clean up Rundeck job and temporary folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete job by href
  python clean-job.py --job-href "http://rundeck:4440/project/test/job/show/abc-123"
  
  # Delete job by ID
  python clean-job.py --job-id "abc-123-def-456"
  
  # Delete folder
  python clean-job.py --path "/tmp/job-folder"
  
  # Delete both (typical Rundeck usage)
  python clean-job.py --job-href "@data.href@" --path "/tmp/@job.id@/@job.execid@"
        """
    )
    
    parser.add_argument(
        "--job-href",
        help="Rundeck job href/permalink to delete"
    )
    parser.add_argument(
        "--job-id",
        help="Rundeck job ID to delete"
    )
    parser.add_argument(
        "--path",
        help="File or directory path to delete"
    )
    
    args = parser.parse_args()
    
    # Validate: at least one operation must be specified
    if not args.job_href and not args.job_id and not args.path:
        parser.error("Must specify at least one of: --job-href, --job-id, or --path")
    
    return args


def delete_rundeck_job(job_href: Optional[str] = None, job_id: Optional[str] = None) -> bool:
    """
    Delete a Rundeck job
    
    Args:
        job_href: Job href/permalink
        job_id: Job ID
    
    Returns:
        True if successful
    
    Raises:
        RundeckAPIError: If deletion fails
    """
    logger.info("=" * 60)
    logger.info("Deleting Rundeck Job")
    logger.info("=" * 60)
    
    config = AppConfig.from_env()
    rundeck = RundeckClient(
        url=config.rundeck.url,
        token=config.rundeck.token,
        project=config.rundeck.project
    )
    
    if job_id:
        logger.info(f"Job ID: {job_id}")
        success = rundeck.delete_job(job_id)
    else:
        logger.info(f"Job href: {job_href}")
        success = rundeck.delete_job_by_href(job_href)
    
    if success:
        logger.info("✅ Job deleted successfully")
        return True
    else:
        logger.warning("⚠️ Job not found (may already be deleted)")
        return True  # Not an error if already deleted


def delete_path(path: str) -> bool:
    """
    Delete a file or directory
    
    Args:
        path: Path to delete
    
    Returns:
        True if successful
    
    Raises:
        FileOperationError: If deletion fails
    """
    logger.info("=" * 60)
    logger.info("Deleting Path")
    logger.info("=" * 60)
    logger.info(f"Path: {path}")
    
    file_ops = FileOperations()
    success = file_ops.delete_path(path)
    
    if success:
        logger.info("✅ Path deleted successfully")
        return True
    else:
        logger.warning("⚠️ Path not found (may already be deleted)")
        return True  # Not an error if already deleted


def main() -> int:
    """
    Main execution
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    try:
        logger.info("=" * 80)
        logger.info("🧹 Rundeck Cleanup - Starting")
        logger.info("=" * 80)
        
        args = parse_arguments()
        
        # Delete job if specified
        if args.job_href or args.job_id:
            delete_rundeck_job(job_href=args.job_href, job_id=args.job_id)
        
        # Delete path if specified
        if args.path:
            delete_path(args.path)
        
        # Success
        logger.info("\n" + "=" * 80)
        logger.info("✅ CLEANUP COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
        return 0
    
    except (RundeckAPIError, FileOperationError) as e:
        logger.error(f"\n❌ Cleanup failed: {e}")
        return 1
    
    except Exception as e:
        logger.exception(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
