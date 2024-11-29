from logging import getLogger

from .descriptors import Enum, Field, File, Message
from .pygen import ImportedSymbol, PyGenFile

log = getLogger(__name__)


def getter_type(field: Field, g: PyGenFile, always_none: bool = False) -> None:
    if field.is_map():
        g.p(
            ImportedSymbol("MutableMapping", "collections.abc"),
            "[",
            field.map_key.python_type(),
            ",",
            field.map_value.python_type(),
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_repeated():
        g.p(
            ImportedSymbol("MutableSequence", "collections.abc"),
            "[",
            field.python_type(),
            "]",
            add_eol=False,
            noindent=True,
        )
    else:
        g.p(field.python_type(), add_eol=False, noindent=True)
    if field.tracks_presence() or always_none:
        g.p("|None", add_eol=False, noindent=True)


def setter_type(field: Field, g: PyGenFile, always_none: bool = False) -> None:
    if field.is_map():
        g.p(
            ImportedSymbol("Mapping", "collections.abc"),
            "[",
            field.map_key.python_type(),
            ",",
            field.map_value.python_type(),
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_repeated():
        g.p(
            ImportedSymbol("Iterable", "collections.abc"),
            "[",
            field.python_type(),
            "]",
            add_eol=False,
            noindent=True,
        )
    elif field.is_enum():
        ptype = field.python_type()
        pb2 = field.enum.pb2
        if pb2 == ptype:
            g.p(ptype, add_eol=False, noindent=True)
        else:
            g.p(ptype, "|", pb2, add_eol=False, noindent=True)
    elif field.is_message():
        ptype = field.python_type()
        pb2 = field.message.pb2
        if pb2 == ptype:
            g.p(ptype, add_eol=False, noindent=True)
        else:
            g.p(ptype, "|", pb2, add_eol=False, noindent=True)
    else:
        g.p(field.python_type(), add_eol=False, noindent=True)
    if field.tracks_presence() or always_none:
        g.p("|None", add_eol=False, noindent=True)


def generate_field(field: Field, g: PyGenFile, self_name: str) -> None:
    g.p("@property")
    g.p("def ", field.name, "(", self_name, ') -> "', add_eol=False)
    getter_type(field, g)
    g.p('":', noindent=True)
    with g:
        g.p(
            "return super()._get_field(",
            '"',
            field.name,
            '", explicit_presence=',
            field.tracks_presence(),
            ",",
        )
        if field.is_message() and not field.message.no_wrap:
            g.p("wrap=", field.message.export_path, ",")
        if field.is_enum() and not field.enum.no_wrap:
            g.p("wrap=", field.enum.export_path, ",")
        g.p(")")
    g.p("@", field.name, ".setter")
    g.p("def ", field.name, '(self, value: "', add_eol=False)
    setter_type(field, g)
    g.p('") -> None:', noindent=True)
    with g:
        g.p(
            "return super()._set_field(",
            '"',
            field.name,
            '",value,explicit_presence=',
            field.tracks_presence(),
            ")",
        )
    g.p()


def generate_field_init_arg(field: Field, g: PyGenFile) -> None:
    g.p(field.name, ': "', add_eol=False)
    setter_type(field, g, always_none=True)
    g.p('" = None,', noindent=True)


def generate_field_init_setter(field: Field, g: PyGenFile, self_name: str) -> None:
    g.p("if ", field.name, " is not None:")
    with g:
        g.p(self_name, ".", field.name, " = ", field.name)


def generate_enum(enum: Enum, g: PyGenFile) -> None:
    descriptor_name = g.suggest_name("__PB2_DESCRIPTOR__")
    g.p(
        "class ",
        enum.name,
        "(",
        ImportedSymbol("Enum", "nebius.base.protos.pb_enum"),
        "):",
    )
    with g:
        g.p(
            descriptor_name,
            " = ",
            ImportedSymbol("DescriptorWrap", "nebius.base.protos.descriptor"),
            "[",
            ImportedSymbol("EnumDescriptor", "google.protobuf.descriptor"),
            ']("',
            enum.full_type_name,
            '",',
            ImportedSymbol("DESCRIPTOR", enum.containing_file.pb2),
            ",",
            ImportedSymbol("EnumDescriptor", "google.protobuf.descriptor"),
            ")",
        )
        for val in enum.values:
            g.p(val.name, " = ", val.number)


def generate_message(message: Message, g: PyGenFile) -> None:
    g.p(
        "class ",
        message.name,
        "(",
        ImportedSymbol("Message", "nebius.base.protos.message"),
        "):",
    )
    initial_message_name = g.suggest_name("initial_message")
    self_name = g.suggest_name("self")
    class_name = g.suggest_name("_PB2_CLASS_")
    message.attached_names["self"] = self_name
    message.attached_names["cls"] = class_name
    with g:
        g.p(class_name, " = ", message.pb2)
        g.p()

        for msg in message.messages():
            generate_message(msg, g)
            g.p()

        for enum in message.enums:
            generate_enum(enum, g)
            g.p()

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
            g.p(
                "super().__init__(",
                initial_message_name,
                ",",
                self_name,
                ".",
                class_name,
                ',"',
                message.full_type_name,
                '",',
                ImportedSymbol("DESCRIPTOR", message.containing_file.pb2),
                ")",
            )

            for field in message.fields():
                generate_field_init_setter(field, g, self_name)
        g.p()

        for field in message.fields():
            generate_field(field, g, self_name)


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
