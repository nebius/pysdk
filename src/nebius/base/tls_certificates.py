import os
import platform


def get_system_certificates() -> str:
    system_cert_path = None

    if platform.system() == "Linux":
        # Common Linux trust store paths
        possible_paths = [
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/ca-bundle.pem",  # OpenSUSE
        ]
        for path in possible_paths:
            if os.path.exists(path):
                system_cert_path = path
                break
    elif platform.system() == "Darwin":  # macOS
        # macOS requires fetching certs via security CLI
        possible_paths = [
            "/opt/homebrew/etc/openssl@3/cert.pem",  # New
            "/usr/local/etc/openssl@1.1/cert.pem",  # Deprecated
        ]
        for path in possible_paths:
            if os.path.exists(path):
                system_cert_path = path
                break
    elif platform.system() == "Windows":
        # On Windows, use certifi-win32 or fetch manually
        try:
            import certifi_win32  # type: ignore[unused-ignore,import-not-found]

            system_cert_path = str(certifi_win32.wincerts.where())  # type: ignore[unused-ignore]
        except ImportError:
            raise RuntimeError("Install 'certifi-win32' to access Windows certificates")

    if not system_cert_path or not os.path.exists(system_cert_path):
        raise RuntimeError("System certificate bundle not found.")
    return system_cert_path
