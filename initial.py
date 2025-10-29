import os
from utils import (setup_logger, AppConfig, VaultClient, VaultAPIError)

logger = setup_logger(__name__)

def main():
    config = AppConfig.from_env()
    print(config)

if __name__ == "__main__":
    import sys
    sys.exit(main())
