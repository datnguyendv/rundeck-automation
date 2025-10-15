"""
Custom exception classes for better error handling
"""


class BaseAppException(Exception):
    """Base exception for all application errors"""
    pass


class TemplateRenderError(BaseAppException):
    """Raised when template rendering fails"""
    pass


class RundeckAPIError(BaseAppException):
    """Raised when Rundeck API call fails"""
    pass


class VaultAPIError(BaseAppException):
    """Raised when Vault API call fails"""
    pass


class NotificationError(BaseAppException):
    """Raised when notification sending fails"""
    pass


class ConfigurationError(BaseAppException):
    """Raised when configuration is invalid or missing"""
    pass


class ValidationError(BaseAppException):
    """Raised when input validation fails"""
    pass
