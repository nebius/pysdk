from nebius.api.nebius import FieldBehavior
from nebius.api.nebius import field_behavior as fb_descriptor
from nebius.base.protos.compiler.descriptors import Field

_cache = dict[str, set[FieldBehavior]]()


def field_behavior(field: Field) -> set[FieldBehavior]:
    if field.full_type_name in _cache:
        return _cache[field.full_type_name]
    fb_array = field.descriptor.options.Extensions[fb_descriptor]  # type: ignore
    ret = set[FieldBehavior]()
    for fb in fb_array:  # type: ignore[unused-ignore]
        ret.add(FieldBehavior(fb))
    _cache[field.full_type_name] = ret
    return ret
