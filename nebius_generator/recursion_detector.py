from .descriptors import Message

_cache = dict[str, bool]()


def is_recursive(msg: Message) -> bool:
    """Returns true only if the message has a field of any level with itself. Messages
    containing recursive ones won't themselves be reported as recursive.

    :param msg: Message to test
    :returns: if the message is recursive
    """
    if msg.full_type_name in _cache:
        return _cache[msg.full_type_name]
    return _is_recursive_detector(msg, set[str]())


def _is_recursive_detector(current: Message, visited: set[str]) -> bool:
    if current.full_type_name in _cache:
        return _cache[current.full_type_name]
    if current.full_type_name in visited:
        _cache[current.full_type_name] = True
        return True

    visited.add(current.full_type_name)
    for field in current.fields():
        if field.is_map() and field.map_value.is_message():
            field = field.map_value
        if field.is_message():
            _is_recursive_detector(field.message, visited)
    visited.remove(current.full_type_name)
    if current.full_type_name not in _cache:
        _cache[current.full_type_name] = False
    return _cache[current.full_type_name]
