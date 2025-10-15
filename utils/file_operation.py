"""
Simple file system operations
"""
import shutil
import logging
from pathlib import Path
from typing import Union

from .exceptions import BaseAppException
from .logger import setup_logger

logger = setup_logger(__name__)


class FileOperationError(BaseAppException):
    """Raised when file operations fail"""
    pass


class FileOperations:
    """Simple file system operations"""
    
    @staticmethod
    def delete_path(path: Union[str, Path]) -> bool:
        """
        Delete a file or directory
        
        Args:
            path: Path to file or directory
        
        Returns:
            True if deleted successfully
        
        Raises:
            FileOperationError: If deletion fails
        """
        path = Path(path)
        
        if not path.exists():
            logger.warning(f"Path does not exist: {path}")
            return False
        
        try:
            if path.is_file() or path.is_symlink():
                logger.info(f"Deleting file: {path}")
                path.unlink()
                logger.info(f"✅ File deleted: {path}")
            
            elif path.is_dir():
                logger.info(f"Deleting directory: {path}")
                shutil.rmtree(path)
                logger.info(f"✅ Directory deleted: {path}")
            
            return True
        
        except PermissionError as e:
            error_msg = f"Permission denied: {path}"
            logger.error(error_msg)
            raise FileOperationError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Failed to delete {path}: {e}"
            logger.error(error_msg)
            raise FileOperationError(error_msg) from e
