from nebius_generator.pygen import PyGenFile


def test_generated_source_preserves_content_and_has_one_trailing_newline() -> None:
    generated = PyGenFile("example", docstring="hard break  \nnext line")
    generated.p("value = 1")
    generated.p()

    source = generated.dumps()

    assert "hard break  \nnext line" in source
    assert "    \n" not in source
    assert source.endswith("value = 1\n")
    assert not source.endswith("\n\n")
