"""Documentation conversion kept compatible with the previous Python generator."""

from __future__ import annotations


def markdown_to_rst(markdown: str) -> str:
    if not markdown:
        return ""
    import m2r2  # type: ignore[import-untyped]

    class Renderer(m2r2.RestRenderer):  # type: ignore[misc]
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
            return super().link(link, "", text)  # type: ignore[no-any-return]

    renderer = Renderer()
    result = str(m2r2.convert(markdown, renderer=renderer))
    if renderer.include_strike:
        result = ".. role:: strike\n" + result
    return result
