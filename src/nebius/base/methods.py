def fix_name(method_name: str) -> str:
    if method_name[0] != "/":
        return method_name
    method_name = method_name[1:]
    return method_name.replace("/", ".")
