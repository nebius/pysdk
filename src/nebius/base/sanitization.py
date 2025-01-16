def ellipsis_in_middle(secret: str) -> str:
    """Inserts ellipsis in the middle of the strings, leaving only small trails in the
    beginning and in the end.

    For strings less than 3 symbols it will output them as is;
    Strings with less than 7 symbols will be truncated to 1 symbol a side;
    All other strings will be trunkated to 3 symbols each side.

    ```
    ellipsis_in_middle("") #-> ""
    ellipsis_in_middle("ab") #-> "ab"
    ellipsis_in_middle("abc") #-> "a...c"
    ellipsis_in_middle("abcdefg") #-> "abc...efg"
    ```

    Args:
     - secret (str): to redact

    Returns:
     - str: redacted secret
    """
    if len(secret) <= 2:
        return secret
    if len(secret) <= 6:
        return secret[0] + "..." + secret[-1]
    return secret[:3] + "..." + secret[-3:]
