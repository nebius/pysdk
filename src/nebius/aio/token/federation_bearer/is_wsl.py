def is_wsl() -> bool:
    """
    Check if the current environment is Windows Subsystem for Linux (WSL).

    Returns:
        bool: True if running in WSL, False otherwise.
    """
    try:
        with open("/proc/version", "r") as f:
            version_info = f.read().lower()
            return "microsoft" in version_info or "wsl" in version_info
    except FileNotFoundError:
        return False
