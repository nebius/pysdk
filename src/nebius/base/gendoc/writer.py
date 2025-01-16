from time import time

from bs4 import BeautifulSoup, CData, NavigableString, PageElement
from bs4 import Comment as BSComment
from bs4 import Tag as BSTag
from pydoctor.model import System  # type: ignore
from pydoctor.templatewriter import TemplateLookup  # type: ignore
from pydoctor.templatewriter import (  # type: ignore[unused-ignore]
    TemplateWriter as Base,
)
from pydoctor.templatewriter.pages import Page  # type: ignore
from pydoctor.templatewriter.writer import flattenToFile  # type: ignore
from twisted.web.template import CDATA, Comment, Tag, renderer


def bs4_to_tag(element: PageElement) -> Tag | CDATA | Comment | str:
    if isinstance(element, BSTag):
        tag = Tag(element.name)
        for k, v in element.attrs.items():
            tag.attributes[k] = v
        for child in element.contents:
            tag.children.append(bs4_to_tag(child))
        return tag
    if isinstance(element, CData):
        return CDATA(element.text)
    if isinstance(element, BSComment):
        return Comment(element.text)
    if isinstance(element, NavigableString):
        return element.text
    raise ValueError(f"Unsupported element type: {type(element)}")


class APIReferencePage(Page):  # type:ignore[misc]
    filename = "apiReference.html"

    def __init__(
        self,
        system: System,
        template_lookup: TemplateLookup,
        clients: BSTag | None,
    ) -> None:
        super().__init__(system=system, template_lookup=template_lookup)
        self._clients = clients

    def title(self) -> str:
        return "Nebius API Reference"

    @renderer
    def clients(self, request: object, tag: Tag) -> Tag:
        if self._clients is not None:
            tag(bs4_to_tag(self._clients))
        return tag


CLIENT_SELECTOR = 'li a[name="nebius.aio.client.Client"] ~ ul'


class TemplateWriter(Base):  # type:ignore[misc]
    def writeSummaryPages(  # noqa: N802 # comply with the protocol
        self, system: System
    ) -> None:
        super().writeSummaryPages(system)

        system.msg("html", "starting " + APIReferencePage.filename + " ...", nonl=True)
        start = time()
        fn = self.build_directory.joinpath("classIndex.html")
        with fn.open("r", encoding="utf-8") as fp:
            soup = BeautifulSoup(fp, "html.parser")
        clients = soup.select_one(CLIENT_SELECTOR)
        page = APIReferencePage(system, self.template_lookup, clients)
        fn = self.build_directory.joinpath(page.filename)
        with fn.open("wb") as fobj:
            flattenToFile(fobj, page)  # type: ignore[unused-ignore]
        system.msg("html", "took %fs" % (time() - start), wantsnl=False)
