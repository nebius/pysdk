from logging import getLogger

from .descriptors import Field, File, Message
from .pygen import ImportedSymbol, PyGenFile

log = getLogger(__name__)


CLASS = ImportedSymbol("Message", "nebius.base.protos.message")


def generate_field(field: Field, g: PyGenFile, self_name: str, base_name: str) -> None:
    g.p("@property")
    g.p("def ", field.name, "(", self_name, ') -> "', add_eol=False)
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
    if field.tracks_presence():
        g.p("|None", add_eol=False, noindent=True)
    g.p('":', noindent=True)
    with g:
        g.p(
            "return super()._get_field(",
            '"',
            field.name,
            '", base=',
            self_name,
            ".",
            base_name,
            ", explicit_presence=",
            field.tracks_presence(),
            ",",
        )
        if field.is_message() and not field.message.no_wrap:
            g.p("wrap=", field.message.export_path, ",")
        g.p(")")
    g.p("@", field.name, ".setter")
    g.p("def ", field.name, '(self, value: "', add_eol=False)
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
    elif field.is_message():
        g.p(field.python_type(), "|", field.message.pb2, add_eol=False, noindent=True)
    else:
        g.p(field.python_type(), add_eol=False, noindent=True)
    if field.tracks_presence():
        g.p("|None", add_eol=False, noindent=True)
    g.p('") -> None:', noindent=True)
    with g:
        g.p(
            "return super()._set_field(",
            '"',
            field.name,
            '",value, base=',
            self_name,
            ".",
            base_name,
            ",explicit_presence=",
            field.tracks_presence(),
            ")",
        )
    g.p()


def generate_field_init_arg(field: Field, g: PyGenFile) -> None:
    g.p(field.name, ': "', add_eol=False)
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
    elif field.is_message():
        g.p(field.python_type(), "|", field.message.pb2, add_eol=False, noindent=True)
    else:
        g.p(field.python_type(), add_eol=False, noindent=True)
    g.p('|None" = None,', noindent=True)


def generate_field_init_setter(field: Field, g: PyGenFile, self_name: str) -> None:
    g.p("if ", field.name, " is not None:")
    with g:
        g.p(self_name, ".", field.name, " = ", field.name)


def generate_message(message: Message, g: PyGenFile) -> None:
    g.p("class ", message.name, "(", CLASS, "):")
    initial_message_name = g.suggest_name("initial_message")
    self_name = g.suggest_name("self")
    base_name = g.suggest_name("_pb2_base_")
    class_name = g.suggest_name("_PB2_CLASS_")
    message.attached_names["self"] = self_name
    message.attached_names["base"] = base_name
    message.attached_names["cls"] = class_name
    with g:
        g.p(class_name, " = ", message.pb2)
        g.p(base_name, ": ", message.pb2)
        g.p()

        for msg in message.messages():
            generate_message(msg, g)
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
                ', "',
                base_name,
                '", ',
                self_name,
                ".",
                class_name,
                ")",
            )

            for field in message.fields():
                generate_field_init_setter(field, g, self_name)
        g.p()

        for field in message.fields():
            generate_field(field, g, self_name, base_name)


def generate_file(file: File, g: PyGenFile) -> None:
    g.p("# file: ", file.name)
    if file.skipped:
        g.p("# file skipped")
        return
    for msg in file.messages():
        generate_message(msg, g)
