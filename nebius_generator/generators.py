from logging import getLogger
from typing import Any, cast

from ._bootstrap.annotations_pb2 import (
    api_service_name,
    credentials,
    enum_value_deprecation_details,
    field_deprecation_details,
    message_deprecation_details,
    method_behavior,
    method_deprecation_details,
    sensitive,
    service_deprecation_details,
)
from .annotations import (
    DeprecationDetails,
    FieldBehavior,
    MethodBehavior,
    field_behavior,
    get_deprecation_details,
)
from .descriptors import (
    Enum,
    EnumValue,
    Field,
    File,
    Message,
    Method,
    OneOf,
    Service,
    SourceInfo,
)
from .pygen import ImportedSymbol, ImportPath, PyGenFile
from .recursion_detector import is_recursive
from .well_known import converter_dict

log = getLogger(__name__)
_runtime_package = "nebius"


def configure_runtime_package(package: str) -> None:
    """Set the import root used for generated SDK runtime references."""
    global _runtime_package
    _runtime_package = package.rstrip(".")


def runtime_import(path: str) -> str:
    """Relocate a default ``nebius`` runtime import below the configured root."""
    return _runtime_package + path.removeprefix("nebius")


def registry_symbol(g: PyGenFile, name: str) -> ImportedSymbol:
    """Return a symbol imported from this generated namespace's registry."""
    if g.registry is None:
        raise RuntimeError("Generated file has no descriptor registry configured")
    return ImportedSymbol(name, g.registry)


def relative_module(current_module: str, target_package: str) -> str:
    """Return a relative import path from a module to a generated package."""
    current = current_module.rsplit(".", 1)[0].split(".")
    target = target_package.split(".")
    common = 0
    for current_part, target_part in zip(current, target):
        if current_part != target_part:
            break
        common += 1
    parents = "." * (len(current) - common + 1)
    remainder = ".".join(target[common:])
    return parents + remainder


def py_symbol(field: Field) -> ImportedSymbol:
    if field.is_message():
        if field.message.full_type_name in converter_dict:
            return converter_dict[field.message.full_type_name].python_class
    return field.python_type()


def tracks_presence(field: Field) -> bool:
    if field.is_message():
        try:
            _ = field.containing_oneof
            return True
        except ValueError:
            behavior = field_behavior(field)
            if FieldBehavior.MEANINGFUL_EMPTY_VALUE in behavior:
                return True
            return is_recursive(field.message)
    return field.tracks_presence()


def mask_getter(field: Field) -> ImportedSymbol | str:
    if field.is_message() and field.message.full_type_name in converter_dict:
        return converter_dict[field.message.full_type_name].mask_func
    return "None"


def escape_triple_quoted_string(s: str) -> str:
    """
    Converts a string into a properly escaped triple-quoted string.
    """
    return s.replace("\\", "\\\\").replace('"""', '\\"""')


def print_triple_quoted_string(s: str, g: PyGenFile) -> None:
    s_escaped = escape_triple_quoted_string(s)
    for line in (f'"""{s_escaped}"""').splitlines():
        g.p(line)


def md2rst(s: str) -> str:
    """
    Convert a markdown string to reStructuredText using m2r2.
    """
    import m2r2  # type: ignore

    class Renderer(m2r2.RestRenderer):  # type: ignore
        include_strike = False

        def linebreak(self) -> str:
            return "\n\n"

        def codespan(self, text: str) -> str:
            if "``" in text:
                return rf"\ :literal:`{text}`\ "
            return f"``{text}``"

        def strikethrough(self, text: str) -> str:
            self.include_strike = True
            return rf"\ :strike:`{text}`\ "

        def inline_html(self, html: str) -> str:
            return rf"\ :literal:`{html}`\ "

        def link(self, link: str, title: str, text: str) -> str:
            return super().link(link, "", text)  # type: ignore[unused-ignore,no-any-return]

    renderer = Renderer()
    rst = str(m2r2.convert(s, renderer=renderer))  # type: ignore[unused-ignore]

    if renderer.include_strike:
        rst = ".. role:: strike\n" + rst

    return rst


def remove_indentation(s: str) -> str:
    """
    Remove the common leading whitespace from all non-empty lines.
    Preserves blank lines.
    """
    ss = s.split("\n")
    non_empty = [line for line in ss if line.strip() != ""]
    if not non_empty:
        return s
    # count leading whitespace (spaces/tabs) for each non-empty line
    indents = [len(line) - len(line.lstrip()) for line in non_empty]
    common = min(indents)
    if common == 0:
        return s
    return "\n".join(line[common:] if line != "" else "" for line in ss)


def remove_first_spaces(s: str) -> str:
    ss = s.split("\n")
    all_have_space = all(line.startswith(" ") or line == "" for line in ss)
    if all_have_space:
        return "\n".join(line[1:] if line != "" else "" for line in ss)
    return s


def generate_docstring(
    info: SourceInfo,
    g: PyGenFile,
    deprecation_details: DeprecationDetails | None = None,
    additional_rst_comment: str = "",
) -> None:
    comment = "\n\n".join(
        filter(
            lambda x: x != "",
            [
                md2rst(remove_first_spaces(info.leading_comments)).strip(),
                md2rst(remove_first_spaces(info.trailing_comments)).strip(),
            ],
        )
    )
    if deprecation_details:
        if comment != "":
            comment += "\n\n"
        comment += md2rst(str(deprecation_details)).strip()
    if additional_rst_comment != "":
        if comment != "":
            comment += "\n\n"
        comment += additional_rst_comment.strip()
    if comment != "":
        print_triple_quoted_string("\n" + comment + "\n", g)
        g.p()


def generate_method_docstring(
    method: Method,
    g: PyGenFile,
    deprecation_details: DeprecationDetails | None = None,
) -> None:
    comment = remove_indentation(
        """
        :param request: The request object to send.
        :type request: :class:`"""
        + method.input.export_path.import_path.import_path
        + "."
        + method.input.pythonic_name
        + """`

        Other parameters can be provided as keyword arguments in the
        ``**kwargs`` dictionary, including metadata, timeouts, and retries.
        See :class:`nebius.aio.request_kwargs.RequestKwargs` for details.

        :return: A :class:`nebius.aio.request.Request` object representing the
            in-flight RPC. It can be awaited (async) or waited
            synchronously using its ``.wait()`` helpers.
        :rtype: :class:`nebius.aio.request.Request` of
            :class:`"""
        + method.output.export_path.import_path.import_path
        + "."
        + method.output.pythonic_name
        + """`.
        """
    ).strip()
    return generate_docstring(method.source_info, g, deprecation_details, comment)


def generate_service_docstring(
    service: Service,
    g: PyGenFile,
    deprecation_details: DeprecationDetails | None = None,
) -> None:
    comment = remove_indentation(
        """
        This class provides the client methods for the ``"""
        + service.full_type_name
        + """`` service.

        Each method constructs a :class:`nebius.aio.request.Request` object
        that represents the in-flight RPC. The request can be awaited (async)
        or waited synchronously using its ``.wait()`` helpers.

        The request methods accept various parameters to configure metadata,
        timeouts, authorization, and retries. See individual method docstrings
        for details.

        :cvar __service_name__: The full protobuf service name.
        """
    ).strip()
    return generate_docstring(service.source_info, g, deprecation_details, comment)


def getter_type(
    field: Field,
    g: PyGenFile,
    always_none: bool = False,
    never_none: bool = False,
) -> None:
    if field.is_map():
        g.p(
            ImportedSymbol("MutableMapping", "collections.abc"),
            "[",
            field.map_key.python_type(),
            ",",
            py_symbol(field.map_value),
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_repeated():
        g.p(
            ImportedSymbol("MutableSequence", "collections.abc"),
            "[",
            py_symbol(field),
            "]",
            add_eol=False,
            noindent=True,
        )
    else:
        g.p(py_symbol(field), add_eol=False, noindent=True)
    if not never_none and (tracks_presence(field) or always_none):
        g.p("|None", add_eol=False, noindent=True)


def setter_type(field: Field, g: PyGenFile, always_none: bool = False) -> None:
    if field.is_map():
        g.p(
            ImportedSymbol("Mapping", "collections.abc"),
            "[",
            field.map_key.python_type(),
            ",",
            field.map_value.python_type(),
            add_eol=False,
            noindent=True,
        )
        if (
            field.map_value.is_message()
            and field.map_value.message.full_type_name in converter_dict
        ):
            g.p(
                "|",
                converter_dict[field.map_value.message.full_type_name].python_class,
                add_eol=False,
                noindent=True,
            )
        g.p(
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_repeated():
        g.p(
            ImportedSymbol("Iterable", "collections.abc"),
            "[",
            field.python_type(),
            add_eol=False,
            noindent=True,
        )
        if field.is_message() and field.message.full_type_name in converter_dict:
            g.p(
                "|",
                converter_dict[field.message.full_type_name].python_class,
                add_eol=False,
                noindent=True,
            )
        g.p(
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_enum():
        g.p(field.python_type(), add_eol=False, noindent=True)
    elif field.is_message():
        ptype = field.python_type()
        g.p(ptype, add_eol=False, noindent=True)
        if field.message.full_type_name in converter_dict:
            g.p(
                "|",
                converter_dict[field.message.full_type_name].python_class,
                add_eol=False,
                noindent=True,
            )
    else:
        g.p(field.python_type(), add_eol=False, noindent=True)
    if tracks_presence(field) or always_none:
        g.p("|None", add_eol=False, noindent=True)


def generate_field(field: Field, g: PyGenFile, self_name: str) -> None:
    deprecation_details = get_deprecation_details(field, field_deprecation_details)
    g.p("@", ImportedSymbol("property", "builtins"))
    g.p("def ", field.pythonic_name, "(", self_name, ') -> "', add_eol=False)
    getter_type(field, g)
    g.p('":', noindent=True)
    with g:
        generate_docstring(field.source_info, g, deprecation_details)
        if deprecation_details is not None:
            g.p(
                ImportedSymbol("getLogger", "logging"),
                '("deprecation").warning(',
            )
            print_triple_quoted_string(
                f"Field {field.full_type_name} is deprecated. {deprecation_details}",
                g,
            )
            g.p(", stack_info=True, stacklevel=2)")
            g.p()
        g.p(
            "return ",
            ImportedSymbol("cast", "typing"),
            '("',
            add_eol=False,
        )
        getter_type(field, g)
        g.p(
            '", super()._get_field(',
            '"',
            field.pythonic_name,
            '", explicit_presence=',
            tracks_presence(field),
            ",",
            noindent=True,
        )
        if field.is_map():
            if field.map_value.is_message():
                wrap = field.map_value.message.export_path
                unwrap = None
                if field.map_value.message.full_type_name in converter_dict:
                    wrap = converter_dict[
                        field.map_value.message.full_type_name
                    ].from_func
                    unwrap = converter_dict[
                        field.map_value.message.full_type_name
                    ].to_func
                g.p(
                    "wrap=",
                    ImportedSymbol(
                        "Map", runtime_import("nebius.base.protos.pb_classes")
                    ),
                    ".with_wrap(",
                    wrap,
                    ",",
                    unwrap,
                    ",",
                    mask_getter(field.map_value),
                    "),",
                )
            else:
                g.p(
                    "wrap=",
                    ImportedSymbol(
                        "Map", runtime_import("nebius.base.protos.pb_classes")
                    ),
                    ",",
                )
        elif field.is_repeated():
            if field.is_message():
                wrap = field.message.export_path
                unwrap = None
                if field.message.full_type_name in converter_dict:
                    wrap = converter_dict[field.message.full_type_name].from_func
                    unwrap = converter_dict[field.message.full_type_name].to_func
                g.p(
                    "wrap=",
                    ImportedSymbol(
                        "Repeated", runtime_import("nebius.base.protos.pb_classes")
                    ),
                    ".with_wrap(",
                    wrap,
                    ",",
                    unwrap,
                    ",",
                    mask_getter(field),
                    "),",
                )
            else:
                g.p(
                    "wrap=",
                    ImportedSymbol(
                        "Repeated", runtime_import("nebius.base.protos.pb_classes")
                    ),
                    ",",
                )
        elif field.is_message() and field.message.full_type_name in converter_dict:
            wrap = converter_dict[field.message.full_type_name].from_func
            g.p("wrap=", wrap)
        elif field.is_message() and not field.message.no_wrap:
            g.p("wrap=", field.message.export_path, ",")
        elif field.is_enum() and not field.enum.no_wrap:
            g.p("wrap=", field.enum.export_path, ",")
        g.p("))")
    g.p("@", field.pythonic_name, ".setter")
    g.p("def ", field.pythonic_name, '(self, value: "', add_eol=False)
    setter_type(field, g, always_none=True)
    g.p('") -> None:', noindent=True)
    with g:
        if deprecation_details is not None:
            g.p(
                ImportedSymbol("getLogger", "logging"),
                '("deprecation").warning(',
            )
            print_triple_quoted_string(
                f"Field {field.full_type_name} is deprecated. {deprecation_details}",
                g,
            )
            g.p(", stack_info=True, stacklevel=2)")
            g.p()

        if field.is_enum():
            deprecated_values = dict[str, tuple[EnumValue, DeprecationDetails]]()
            for val in field.enum.values:
                ev_depr_details = get_deprecation_details(
                    val, enum_value_deprecation_details
                )
                if ev_depr_details is not None:
                    deprecated_values[val.name] = (val, ev_depr_details)
            if len(deprecated_values) > 0:
                for val, details in deprecated_values.values():
                    g.p(
                        "if value == ",
                        val.containing_enum.export_path,
                        ".",
                        val.name,
                        ":",
                    )
                    with g:
                        g.p(
                            ImportedSymbol("getLogger", "logging"),
                            '("deprecation").warning(',
                        )
                        print_triple_quoted_string(
                            f"Setting deprecated value {val.name} for field "
                            f"{field.full_type_name}. {details}",
                            g,
                        )
                        g.p(", stack_info=True, stacklevel=2)")
                g.p()

        g.p(
            "return super()._set_field(",
            '"',
            field.pythonic_name,
            '",value,explicit_presence=',
            tracks_presence(field),
            ",",
        )
        if (
            not (field.is_map() or field.is_repeated())
            and field.is_message()
            and field.message.full_type_name in converter_dict
        ):
            unwrap = converter_dict[field.message.full_type_name].to_func
            g.p("unwrap=", unwrap)
        g.p(")")
    g.p()


def generate_field_init_arg(field: Field, g: PyGenFile) -> None:
    g.p(field.pythonic_name, ': "', add_eol=False)
    setter_type(field, g, always_none=True)
    g.p(
        "|",
        ImportedSymbol("UnsetType", runtime_import("nebius.base.protos.unset")),
        '" = ',
        ImportedSymbol("Unset", runtime_import("nebius.base.protos.unset")),
        ",",
        noindent=True,
    )


def generate_field_init_setter(field: Field, g: PyGenFile, self_name: str) -> None:
    g.p(
        "if not isinstance(",
        field.pythonic_name,
        ", ",
        ImportedSymbol("UnsetType", runtime_import("nebius.base.protos.unset")),
        "):",
    )
    with g:
        g.p(self_name, ".", field.pythonic_name, " = ", field.pythonic_name)


def generate_enum(enum: Enum, g: PyGenFile) -> None:
    g.p(
        "class ",
        enum.pythonic_name,
        "(",
        ImportedSymbol("Enum", runtime_import("nebius.base.protos.pb_enum")),
        "):",
    )
    with g:
        generate_docstring(enum.source_info, g)
        g.p(
            "__PROTO_DESCRIPTOR__ = ",
            registry_symbol(g, "enum_descriptor"),
            '("',
            enum.full_type_name,
            '")',
        )
        for val in enum.values:
            g.p(val.name, " = ", val.number)
            generate_docstring(
                val.source_info,
                g,
                get_deprecation_details(val, enum_value_deprecation_details),
            )


def generate_oneof(oneof: OneOf, g: PyGenFile) -> None:
    self_name = g.suggest_name("self")
    g.p(
        "class __OneOfClass_",
        oneof.pythonic_name,
        "__(",
        ImportedSymbol("OneOf", runtime_import("nebius.base.protos.pb_classes")),
        "):",
    )
    with g:
        g.p("name: ", ImportedSymbol("str", "builtins"), '= "', oneof.name, '"')
        g.p()
        g.p(
            "def __init__(",
            self_name,
            ', msg: "',
            oneof.containing_message.export_path,
            '") -> None:',
        )
        with g:
            g.p("super().__init__()")
            g.p(
                self_name,
                '._message: "',
                oneof.containing_message.export_path,
                '" = msg',
            )
    g.p()

    for field in oneof.fields:
        g.p(
            "class __OneOfClass_",
            oneof.pythonic_name,
            "_",
            field.pythonic_name,
            "__(",
            "__OneOfClass_",
            oneof.pythonic_name,
            "__):",
        )
        with g:
            g.p(
                "field: ",
                ImportedSymbol("Literal", "typing"),
                '["',
                field.pythonic_name,
                '"] = "',
                field.pythonic_name,
                '"',
            )
            g.p()
            g.p(
                "def __init__(",
                self_name,
                ', msg: "',
                oneof.containing_message.export_path,
                '") -> None:',
            )
            with g:
                g.p("super().__init__(msg)")
            g.p("@", ImportedSymbol("property", "builtins"))
            g.p("def value(", self_name, ') -> "', add_eol=False)
            getter_type(field, g, never_none=True)
            g.p('":', noindent=True)
            with g:
                g.p(
                    "return ",
                    ImportedSymbol("cast", "typing"),
                    '("',
                    add_eol=False,
                )
                getter_type(field, g, never_none=True)
                g.p(
                    '", ',
                    self_name,
                    "._message.",
                    field.pythonic_name,
                    ")",
                    noindent=True,
                )
        g.p()

    g.p("@", ImportedSymbol("property", "builtins"))
    g.p("def ", oneof.pythonic_name, "(", self_name, ") -> ", add_eol=False)
    for field in oneof.fields:
        g.p(
            "__OneOfClass_",
            oneof.pythonic_name,
            "_",
            field.pythonic_name,
            "__|",
            noindent=True,
            add_eol=False,
        )
    g.p("None:", noindent=True)
    with g:
        generate_docstring(oneof.source_info, g)
        field_name = g.suggest_name("field_name", [self_name])
        g.p(field_name, ': str|None = super().which_field_in_oneof("', oneof.name, '")')
        g.p("match ", field_name, ":")
        with g:
            for field in oneof.fields:
                g.p('case "', field.name, '":')
                with g:
                    g.p(
                        "return ",
                        self_name,
                        ".__OneOfClass_",
                        oneof.pythonic_name,
                        "_",
                        field.pythonic_name,
                        "__(",
                        self_name,
                        ")",
                    )
            g.p("case None:")
            with g:
                g.p("return None")
            g.p("case _:")
            with g:
                g.p(
                    "raise ",
                    ImportedSymbol(
                        "OneOfMatchError",
                        runtime_import("nebius.base.protos.pb_classes"),
                    ),
                    "(",
                    field_name,
                    ")",
                )
    g.p()


def generate_message(message: Message, g: PyGenFile) -> None:
    g.p(
        "class ",
        message.pythonic_name,
        "(",
        ImportedSymbol("Message", runtime_import("nebius.base.protos.pb_classes")),
        "):",
    )
    initial_message_name = g.suggest_name("initial_message")
    self_name = g.suggest_name("self")
    with g:
        deprecation_details = get_deprecation_details(
            message, message_deprecation_details
        )
        generate_docstring(message.source_info, g, deprecation_details)
        g.p(
            "__PROTO_CLASS__ = ",
            registry_symbol(g, "message"),
            '("',
            message.full_type_name,
            '")',
        )
        g.p(
            "__PROTO_DESCRIPTOR__ = ",
            registry_symbol(g, "message_descriptor"),
            '("',
            message.full_type_name,
            '")',
        )
        g.p(
            "__sensitive_fields__: ",
            ImportedSymbol("set", "builtins"),
            "[",
            ImportedSymbol("str", "builtins"),
            "] = ",
            ImportedSymbol("set", "builtins"),
            "({",
        )
        with g:
            for field in message.fields():
                if bool(field.descriptor.options.Extensions[sensitive]):  # type: ignore[index]
                    g.p('"', field.pythonic_name, '",')
        g.p("})")
        g.p(
            "__credentials_fields__: ",
            ImportedSymbol("set", "builtins"),
            "[",
            ImportedSymbol("str", "builtins"),
            "] = ",
            ImportedSymbol("set", "builtins"),
            "({",
        )
        with g:
            for field in message.fields():
                if bool(field.descriptor.options.Extensions[credentials]):  # type: ignore[index]
                    g.p('"', field.pythonic_name, '",')
        g.p("})")
        g.p("__mask_functions__ = {")
        with g:
            for field in message.fields():
                if (
                    field.is_message()
                    and field.message.full_type_name in converter_dict
                ):
                    g.p('"', field.pythonic_name, '": ', mask_getter(field), ",")
        g.p("}")
        g.p()

        for msg in message.messages():
            generate_message(msg, g)
            g.p()

        for enum in message.enums:
            generate_enum(enum, g)
            g.p()

        for oneof in message.oneofs:
            generate_oneof(oneof, g)

        g.p("def __init__(")
        with g:
            g.p(self_name, ",")
            g.p(
                initial_message_name,
                ": ",
                ImportedSymbol("Message", "google.protobuf.message"),
                "|None = None,",
            )
            if len(message.fields()) > 0:
                g.p("*,")
            for field in message.fields():
                generate_field_init_arg(field, g)
        g.p(") -> None:")
        with g:
            g.p("super().__init__(", initial_message_name, ")")

            if deprecation_details is not None:
                g.p(
                    ImportedSymbol("getLogger", "logging"),
                    '("deprecation").warning(',
                )
                print_triple_quoted_string(
                    f"Message {message.full_type_name} is deprecated. "
                    f"{deprecation_details}",
                    g,
                )
                g.p(", stack_info=True, stacklevel=2)")
                g.p()

            for field in message.fields():
                generate_field_init_setter(field, g, self_name)
        g.p()

        g.p(
            "def __dir__(",
            self_name,
            ") ->",
            ImportedSymbol("Iterable", "collections.abc"),
            "[",
            ImportedSymbol("str", "builtins"),
            "]:",
        )
        with g:
            g.p("return [")
            with g:
                for f in message.fields():
                    g.p('"', f.pythonic_name, '",')
                for m in message.messages():
                    g.p('"', m.pythonic_name, '",')
                for o in message.oneofs:
                    g.p('"', o.pythonic_name, '",')
                for e in message.enums:
                    g.p('"', e.pythonic_name, '",')
            g.p("]")
        g.p()

        for field in message.fields():
            generate_field(field, g, self_name)

        g.p(
            "__PY_TO_PB2__: ",
            ImportedSymbol("dict", "builtins"),
            "[",
            ImportedSymbol("str", "builtins"),
            ",",
            ImportedSymbol("str", "builtins"),
            "] = {",
        )
        with g:
            for f in message.fields():
                g.p('"', f.pythonic_name, '":"', f.name, '",')
            for m in message.messages():
                g.p('"', m.pythonic_name, '":"', m.name, '",')
            for o in message.oneofs:
                g.p('"', o.pythonic_name, '":"', o.name, '",')
            for e in message.enums:
                g.p('"', e.pythonic_name, '":"', e.name, '",')
        g.p("}")
        g.p()


def is_operation_output(method: Method) -> bool:
    return (
        method.output.full_type_name == ".nebius.common.v1.Operation"
        or method.output.full_type_name == ".nebius.common.v1alpha1.Operation"
    )


def _method_behavior_setting(method: Method) -> list[MethodBehavior] | None:
    """
    Returns method behavior values when annotation is set, otherwise None.
    """
    ext = cast(Any, method_behavior)
    options = method.descriptor.options
    values = [MethodBehavior(value) for value in options.Extensions[ext]]
    if not values:
        return None
    return values


def _should_add_reset_mask(method: Method) -> bool:
    setting = _method_behavior_setting(method)
    if setting is None:
        return method.name == "Update"
    return MethodBehavior.METHOD_UPDATER in setting


def generate_service(srv: Service, g: PyGenFile) -> None:
    operation_type = None
    operation_source_method = None
    operation_service = None
    for method in srv.methods.values():
        if is_operation_output(method):
            operation_service = ImportedSymbol(
                "OperationServiceClient",
                method.output.export_path.import_path,
            )
            operation_service.import_path.localized = True
            if (
                operation_service.import_path == srv.export_path.import_path
                and operation_service.name == srv.pythonic_name + "Client"
            ):
                break
            operation_source_method = method.name
            operation_type = method.output.export_path
            break
    g.p()
    g.p(
        "class ",
        srv.pythonic_name,
        "Client(",
        add_eol=False,
    )
    if operation_type is None:
        g.p(
            ImportedSymbol("Client", runtime_import("nebius.aio.client")),
            noindent=True,
            add_eol=False,
        )
    else:
        g.p(
            ImportedSymbol("ClientWithOperations", runtime_import("nebius.aio.client")),
            "[",
            operation_type,
            ",",
            operation_service,
            "]",
            noindent=True,
            add_eol=False,
        )
    g.p("):", noindent=True)
    with g:
        deprecation_details = get_deprecation_details(srv, service_deprecation_details)
        generate_service_docstring(srv, g, deprecation_details)
        g.p(
            "__PROTO_DESCRIPTOR__ = ",
            registry_symbol(g, "service_descriptor"),
            '("',
            srv.full_type_name,
            '")',
        )
        g.p('"""The protobuf service descriptor extraction function."""')
        g.p('__service_name__ = "', srv.full_type_name, '"')
        endpoint_name = str(
            srv.descriptor.options.Extensions[api_service_name]  # type: ignore[index]
        )
        g.p('__service_name_override__ = "', endpoint_name, '"')
        if operation_type is not None:
            g.p("__operation_type__ = ", operation_type)
            g.p("__operation_service_class__ = ", operation_service)
            g.p('__operation_source_method__ = "', operation_source_method, '"')
            g.p(
                '"""The method name that can be used to fetch the address channel'
                + ' for the operation."""'
            )
        if deprecation_details is not None:
            g.p("__service_deprecation_details__ = (")
            print_triple_quoted_string(
                f"Service {srv.full_type_name} is deprecated. {deprecation_details}",
                g,
            )
            g.p(")")
        g.p()
        for method in srv.methods.values():
            method_deprecation_details_obj = get_deprecation_details(
                method, method_deprecation_details
            )
            g.p("def ", method.pythonic_name, "(self,")
            with g:
                g.p('request: "', method.input.export_path, '",')
                g.p(
                    "**kwargs: ",
                    ImportedSymbol("Unpack", "typing_extensions"),
                    "[",
                    ImportedSymbol(
                        "RequestKwargs", runtime_import("nebius.aio.request_kwargs")
                    ),
                    "]",
                )
            g.p(
                ") -> ",
                ImportedSymbol("Request", runtime_import("nebius.aio.request")),
                '["',
                method.input.export_path,
                '","',
                add_eol=False,
            )
            if is_operation_output(method):
                g.p(
                    ImportedSymbol("Operation", runtime_import("nebius.aio.operation")),
                    "[",
                    method.output.export_path,
                    "]",
                    noindent=True,
                    add_eol=False,
                )
            else:
                g.p(method.output.export_path, noindent=True, add_eol=False)
            g.p('"]:', noindent=True)
            with g:
                generate_method_docstring(method, g, method_deprecation_details_obj)
                if method_deprecation_details_obj is not None:
                    g.p(
                        ImportedSymbol("getLogger", "logging"),
                        '("deprecation").warning(',
                    )
                    print_triple_quoted_string(
                        f"Method {method.full_type_name} is deprecated. "
                        f"{method_deprecation_details_obj}",
                        g,
                    )
                    g.p(", stack_info=True, stacklevel=2)")
                    g.p()

                if _should_add_reset_mask(method):
                    g.p(
                        "kwargs['metadata'] = ",
                        ImportedSymbol(
                            "ensure_reset_mask_in_metadata",
                            runtime_import("nebius.base.fieldmask_protobuf"),
                        ),
                        "(request, kwargs.get('metadata', None))",
                    )
                g.p("return super().request(")
                with g:
                    g.p('method="', method.name, '",')
                    g.p("request=request,")
                    g.p("result_class=", method.output.export_path, ",")
                    if is_operation_output(method):
                        g.p(
                            "result_wrapper=",
                            ImportedSymbol(
                                "Operation", runtime_import("nebius.aio.operation")
                            ),
                            ",",
                        )
                    g.p("**kwargs,")
                g.p(")")
            g.p()
    g.p()


def generate_extension(ext: Field, g: PyGenFile) -> None:
    g.p(
        ext.pythonic_name,
        " = ",
        registry_symbol(g, "extension_descriptor"),
        '("',
        ext.full_type_name,
        '")',
    )


def generate_enum_export(enum: Enum, g: PyGenFile) -> None:
    g.p('"', enum.pythonic_name, '",')


def generate_extension_export(ext: Field, g: PyGenFile) -> None:
    g.p('"', ext.pythonic_name, '",')


def generate_message_export(msg: Message, g: PyGenFile) -> None:
    g.p('"', msg.pythonic_name, '",')


def generate_service_export(srv: Service, g: PyGenFile) -> None:
    g.p('"', srv.pythonic_name, 'Client",')


def generate_file(file: File, g: PyGenFile) -> None:
    g.p("# file: ", file.name)
    if file.skipped:
        g.p("# file skipped")
        return
    for enum in file.enums:
        generate_enum(enum, g)
        g.p()
    for msg in file.messages():
        generate_message(msg, g)
    for ext in file.extensions.values():
        generate_extension(ext, g)
    for srv in file.services_dict.values():
        generate_service(srv, g)


def generate_exports(file: File, g: PyGenFile) -> None:
    for enum in file.enums:
        generate_enum_export(enum, g)
    for ext in file.extensions.values():
        generate_extension_export(ext, g)
    for msg in file.messages():
        generate_message_export(msg, g)
    for srv in file.services_dict.values():
        generate_service_export(srv, g)


def generate_pb2_compat(file: File, g: PyGenFile) -> None:
    """Generate a legacy ``*_pb2`` facade over the direct package classes."""
    exports = [*file.enums, *file.messages(), *file.extensions.values()]
    for exported in exports:
        export = exported.export_path
        g.p(
            "from ",
            relative_module(g.import_path, export.import_path.import_path),
            " import ",
            export.name,
            " as ",
            exported.name,
        )
    if exports:
        g.p("DESCRIPTOR = ", exports[0].name, ".get_descriptor().file")
    elif file.services_dict:
        service = next(iter(file.services_dict.values()))
        g.p(
            "DESCRIPTOR = ",
            registry_symbol(g, "service_descriptor"),
            '("',
            service.full_type_name,
            '").file',
        )
    else:
        g.p("DESCRIPTOR = None")
    g.p()
    for enum in file.enums:
        for value in enum.values:
            g.p(value.name, " = ", enum.name, ".", value.name)


def generate_grpc_compat(file: File, g: PyGenFile) -> None:
    """Generate local gRPC stubs and server registration helpers."""
    grpc = ImportPath("grpc")
    experimental = ImportPath("grpc.experimental")
    any_type = ImportedSymbol("Any", "typing")
    local_types: dict[str, Message] = {}
    for service in file.services_dict.values():
        for method in service.methods.values():
            for message in (method.input, method.output):
                if message.containing_file.package == file.package:
                    local_types[message.pythonic_name] = message
    for name, message in sorted(local_types.items()):
        export = message.export_path
        g.p(
            "from ",
            relative_module(g.import_path, export.import_path.import_path),
            " import ",
            export.name,
            " as ",
            name,
        )

    def message_symbol(message: Message) -> ImportedSymbol | str:
        if message.containing_file.package == file.package:
            return message.pythonic_name
        return message.export_path

    def call_kind(method: Method) -> str:
        if method.descriptor.client_streaming and method.descriptor.server_streaming:
            return "stream_stream"
        if method.descriptor.client_streaming:
            return "stream_unary"
        if method.descriptor.server_streaming:
            return "unary_stream"
        return "unary_unary"

    for service in file.services_dict.values():
        endpoint_name = str(
            service.descriptor.options.Extensions[api_service_name]  # type: ignore[index]
        )
        g.p("class ", service.name, "Stub:")
        with g:
            g.p(
                '__service_name__ = "',
                service.full_type_name.lstrip("."),
                '"',
            )
            g.p('__service_name_override__ = "', endpoint_name, '"')
            g.p()
            g.p("def __init__(self, channel: ", any_type, ") -> None:")
            with g:
                for method in service.methods.values():
                    g.p("self.", method.name, " = channel.", call_kind(method), "(")
                    with g:
                        g.p(
                            '"/',
                            service.full_type_name.lstrip("."),
                            "/",
                            method.name,
                            '",',
                        )
                        g.p(
                            "request_serializer=",
                            message_symbol(method.input),
                            ".SerializeToString,",
                        )
                        g.p(
                            "response_deserializer=",
                            message_symbol(method.output),
                            ".FromString,",
                        )
                    g.p(")")
        g.p()

        g.p("class ", service.name, "Servicer:")
        with g:
            if not service.methods:
                g.p("pass")
            for method in service.methods.values():
                g.p(
                    "def ",
                    method.name,
                    "(self, request: ",
                    any_type,
                    ", context: ",
                    any_type,
                    ") -> ",
                    any_type,
                    ":",
                )
                with g:
                    g.p("context.set_code(", grpc, ".StatusCode.UNIMPLEMENTED)")
                    g.p('context.set_details("Method not implemented!")')
                    g.p('raise NotImplementedError("Method not implemented!")')
        g.p()

        g.p("class ", service.name, "(", service.name, "Servicer):")
        with g:
            g.p('"""Backward-compatible experimental service API."""')
            for method in service.methods.values():
                request_name = (
                    "request_iterator"
                    if method.descriptor.client_streaming
                    else "request"
                )
                g.p("@staticmethod")
                g.p("def ", method.name, "(")
                with g:
                    g.p(request_name, ": ", any_type, ",")
                    g.p("target: str,")
                    g.p("options: ", any_type, " = (),")
                    g.p("channel_credentials: ", any_type, " = None,")
                    g.p("call_credentials: ", any_type, " = None,")
                    g.p("insecure: bool = False,")
                    g.p("compression: ", any_type, " = None,")
                    g.p("wait_for_ready: bool | None = None,")
                    g.p("timeout: float | None = None,")
                    g.p("metadata: ", any_type, " = None,")
                g.p(") -> ", any_type, ":")
                with g:
                    g.p("return ", experimental, ".", call_kind(method), "(")
                    with g:
                        g.p(request_name, ",")
                        g.p("target,")
                        g.p(
                            '"/',
                            service.full_type_name.lstrip("."),
                            "/",
                            method.name,
                            '",',
                        )
                        g.p(message_symbol(method.input), ".SerializeToString,")
                        g.p(message_symbol(method.output), ".FromString,")
                        g.p("options,")
                        g.p("channel_credentials,")
                        g.p("insecure,")
                        g.p("call_credentials,")
                        g.p("compression,")
                        g.p("wait_for_ready,")
                        g.p("timeout,")
                        g.p("metadata,")
                    g.p(")")
                g.p()
        g.p()

        g.p(
            "def add_",
            service.name,
            "Servicer_to_server(servicer: ",
            any_type,
            ", server: ",
            any_type,
            ") -> None:",
        )
        with g:
            g.p("rpc_method_handlers = {")
            with g:
                for method in service.methods.values():
                    handler_kind = (
                        "stream_stream_rpc_method_handler"
                        if method.descriptor.client_streaming
                        and method.descriptor.server_streaming
                        else (
                            "stream_unary_rpc_method_handler"
                            if method.descriptor.client_streaming
                            else (
                                "unary_stream_rpc_method_handler"
                                if method.descriptor.server_streaming
                                else "unary_unary_rpc_method_handler"
                            )
                        )
                    )
                    g.p('"', method.name, '": ', grpc, ".", handler_kind, "(")
                    with g:
                        g.p("servicer.", method.name, ",")
                        g.p(
                            "request_deserializer=",
                            message_symbol(method.input),
                            ".FromString,",
                        )
                        g.p(
                            "response_serializer=",
                            message_symbol(method.output),
                            ".SerializeToString,",
                        )
                    g.p("),")
            g.p("}")
            g.p("generic_handler = ", grpc, ".method_handlers_generic_handler(")
            with g:
                g.p('"', service.full_type_name.lstrip("."), '", rpc_method_handlers')
            g.p(")")
            g.p("server.add_generic_rpc_handlers((generic_handler,))")
            g.p('if hasattr(server, "add_registered_method_handlers"):')
            with g:
                g.p("server.add_registered_method_handlers(")
                with g:
                    g.p(
                        '"',
                        service.full_type_name.lstrip("."),
                        '", rpc_method_handlers',
                    )
                g.p(")")
        g.p()
