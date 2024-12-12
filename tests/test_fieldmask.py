# type: ignore

import pytest


def test_fieldkey() -> None:
    from nebius.base.fieldmask import FieldKey

    assert FieldKey("Simple_Key_123").marshal() == "Simple_Key_123"
    assert isinstance(FieldKey("abc"), FieldKey)
    assert (
        FieldKey('Key		with spaces, commas, and: ".\\_-!@$%^"').marshal()
        == '"Key\\t\\twith spaces, commas, and: \\".\\\\_-!@$%^\\""'
    )


def test_fieldpath_join() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath

    cases = [
        {
            "A": FieldPath([]),
            "B": FieldPath([]),
            "R": FieldPath([]),
        },
        {
            "A": FieldPath([FieldKey("foo")]),
            "B": FieldPath([]),
            "R": FieldPath([FieldKey("foo")]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "B": FieldPath([]),
            "R": FieldPath([FieldKey("foo"), FieldKey("bar")]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "B": FieldPath([FieldKey("baz")]),
            "R": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
        },
        {
            "A": FieldPath([FieldKey("foo")]),
            "B": FieldPath([FieldKey("bar"), FieldKey("baz")]),
            "R": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
        },
        {
            "A": FieldPath([]),
            "B": FieldPath([FieldKey("bar"), FieldKey("baz")]),
            "R": FieldPath([FieldKey("bar"), FieldKey("baz")]),
        },
    ]

    for i, case in enumerate(cases):
        # Perform the join operation
        result = case["A"] + case["B"]
        # Assert the result matches the expected output
        assert result == case["R"], f"Failed on case {i}: {result} != {case['R']}"


def test_fieldpath_parent() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath

    # Define test cases
    cases = [
        {
            "A": FieldPath([]),
            "R": None,
        },
        {
            "A": FieldPath([FieldKey("foo")]),
            "R": FieldPath([]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "R": FieldPath([FieldKey("foo")]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
            "R": FieldPath([FieldKey("foo"), FieldKey("bar")]),
        },
    ]

    for i, case in enumerate(cases):
        # Perform the parent operation
        result = case["A"].parent()
        # Assert the result matches the expected output
        assert result == case["R"], f"Failed on case {i}: {result} != {case['R']}"


def test_fieldpath_copy() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath

    # Define test cases
    cases = [
        {
            "A": FieldPath([]),
        },
        {
            "A": FieldPath([FieldKey("foo")]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar")]),
        },
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
        },
    ]

    for i, case in enumerate(cases):
        # Perform the copy operation
        cp = case["A"].copy()
        # Assert the copy matches the original
        assert cp == case["A"], f"Failed on case {i}: {cp} != {case['A']}"
        assert case["A"] == FieldPath(
            case["A"]
        ), f"Failed on case {i}: FieldPath doesn't match"  # noqa: E501
        assert case["A"] == cp, f"Failed on case {i}: A != cp"
        assert cp == case["A"], f"Failed on case {i}: cp != A"

        if len(case["A"]) > 0:
            # Modify the original and assert copy is unaffected
            case["A"][0] = FieldKey("changed")
            assert cp != case["A"], f"Failed on case {i}: cp == A after modification"
            assert (
                case["A"] != cp
            ), f"Failed on case {i}: A equal to cp after modification"  # noqa: E501
            assert (
                cp != case["A"]
            ), f"Failed on case {i}: cp equal to A after modification"  # noqa: E501


def test_fieldpath_equality():
    from nebius.base.fieldmask import FieldKey, FieldPath

    # Define test cases
    paths = [
        FieldPath([]),
        FieldPath([FieldKey("foo")]),
        FieldPath([FieldKey("bar")]),
        FieldPath([FieldKey("foo"), FieldKey("foo")]),
        FieldPath([FieldKey("foo"), FieldKey("bar")]),
        FieldPath([FieldKey("foo"), FieldKey("baz")]),
        FieldPath([FieldKey("foe"), FieldKey("bar")]),
        FieldPath([FieldKey("foe"), FieldKey("baz")]),
        FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
        FieldPath([FieldKey("foo"), FieldKey("bae"), FieldKey("baz")]),
        FieldPath([FieldKey("foe"), FieldKey("bar"), FieldKey("baz")]),
        FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("bax")]),
        FieldPath([FieldKey("foo"), FieldKey("foo"), FieldKey("bar")]),
        FieldPath([FieldKey("foo"), FieldKey("foo"), FieldKey("baz")]),
        FieldPath([FieldKey("foo"), FieldKey("foo"), FieldKey("foo")]),
    ]

    for i, a in enumerate(paths):
        for j, b in enumerate(paths):
            # Test equality
            assert a == a, f"Self-equality failed for case {i}"
            assert b == b, f"Self-equality failed for case {j}"

            if i == j:
                assert a == b, f"Equality failed for cases {i}, {j}"
                assert b == a, f"Equality symmetry failed for cases {i}, {j}"
            else:
                assert a != b, f"Inequality failed for cases {i}, {j}"
                assert b != a, f"Inequality symmetry failed for cases {i}, {j}"


def test_fieldpath_to_mask():
    from nebius.base.fieldmask import FieldKey, FieldPath, Mask

    # Define test cases
    cases = [
        {"FP": FieldPath([]), "Res": ""},
        {"FP": FieldPath([FieldKey("foo")]), "Res": "foo"},
        {"FP": FieldPath([FieldKey("foo"), FieldKey("bar")]), "Res": "foo.bar"},
        {
            "FP": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
            "Res": "foo.bar.baz",
        },
    ]

    for i, case in enumerate(cases):
        # Convert FieldPath to Mask
        m = case["FP"].to_mask()

        # Check that the result is an instance of Mask
        assert isinstance(m, Mask), f"Failed on case {i}: Result is not a Mask instance"

        # Marshal the mask to a string
        str_representation = m.marshal()

        # Assert no error and correct string representation
        assert str_representation == case["Res"], (
            f"Failed on case {i}: " f"{str_representation} !=" f" {case['Res']}"
        )


def test_fieldpath_is_prefix_of():
    from nebius.base.fieldmask import FieldKey, FieldPath

    # Define test cases
    cases = [
        {"A": FieldPath([]), "B": FieldPath([]), "Res": False},
        {"A": FieldPath([FieldKey("foo")]), "B": FieldPath([]), "Res": False},
        {
            "A": FieldPath([FieldKey("foo")]),
            "B": FieldPath([FieldKey("bar")]),
            "Res": False,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("baz")]),
            "B": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "Res": False,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("foo"), FieldKey("baz"), FieldKey("abc")]),
            "B": FieldPath(
                [FieldKey("foo"), FieldKey("bar"), FieldKey("abc"), FieldKey("def")]
            ),
            "Res": False,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("baz"), FieldKey("foo")]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("foo"), FieldKey("abc"), FieldKey("def")]
            ),
            "Res": False,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("baz"), FieldKey("foo"), FieldKey("abc")]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("foo"), FieldKey("abc"), FieldKey("def")]
            ),
            "Res": False,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("bar"), FieldKey("foo"), FieldKey("")]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("foo"), FieldKey("abc"), FieldKey("def")]
            ),
            "Res": False,
        },  # noqa: E501
        {"A": FieldPath([]), "B": FieldPath([FieldKey("foo")]), "Res": True},
        {
            "A": FieldPath([FieldKey("bar")]),
            "B": FieldPath([FieldKey("bar"), FieldKey("foo")]),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("bar"), FieldKey("baz")]),
            "B": FieldPath([FieldKey("bar"), FieldKey("baz"), FieldKey("foo")]),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([]),
            "B": FieldPath([FieldKey("foo"), FieldKey("bar"), FieldKey("baz")]),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("bar")]),
            "B": FieldPath([FieldKey("bar"), FieldKey("foo"), FieldKey("baz")]),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("bar"), FieldKey("baz")]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("baz"), FieldKey("foo"), FieldKey("abc")]
            ),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([FieldKey("bar")]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("baz"), FieldKey("foo"), FieldKey("abc")]
            ),
            "Res": True,
        },  # noqa: E501
        {
            "A": FieldPath([]),
            "B": FieldPath(
                [FieldKey("bar"), FieldKey("baz"), FieldKey("foo"), FieldKey("abc")]
            ),
            "Res": True,
        },  # noqa: E501
    ]

    for i, case in enumerate(cases):
        res = case["A"].is_prefix_of(case["B"])
        assert res == case["Res"], f"Failed on case {i}: {res} != {case['Res']}"


def test_fieldpath_matches_reset_mask() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath, Mask

    cases = [
        {
            "FP": FieldPath([]),
            "M": None,
            "Res": False,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": None,
            "Res": False,
            "Final": False,
        },
        {
            "FP": FieldPath([]),
            "M": Mask(),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(),
            "Res": False,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(field_parts={FieldKey("abc"): Mask()}),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(field_parts={FieldKey("abc"): Mask(any=Mask())}),
            "Res": True,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(
                field_parts={
                    FieldKey("abc"): Mask(field_parts={FieldKey("foo"): Mask()})
                }
            ),
            "Res": True,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(
                field_parts={
                    FieldKey("abc"): Mask(field_parts={FieldKey("foo"): Mask()}),
                    FieldKey("def"): Mask(field_parts={FieldKey("foo"): Mask()}),
                }
            ),
            "Res": True,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("abc"), FieldKey("foo")]),
            "M": Mask(
                any=Mask(field_parts={FieldKey("foo"): Mask()}),
                field_parts={
                    FieldKey("abc"): Mask(field_parts={FieldKey("bar"): Mask()}),
                    FieldKey("def"): Mask(field_parts={FieldKey("baz"): Mask()}),
                },
            ),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc"), FieldKey("bar")]),
            "M": Mask(
                any=Mask(field_parts={FieldKey("bar"): Mask(any=Mask())}),
                field_parts={
                    FieldKey("abc"): Mask(field_parts={FieldKey("bar"): Mask()}),
                    FieldKey("def"): Mask(field_parts={FieldKey("baz"): Mask()}),
                },
            ),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc"), FieldKey("bar")]),
            "M": Mask(
                any=Mask(field_parts={FieldKey("bar"): Mask()}),
                field_parts={
                    FieldKey("abc"): Mask(
                        field_parts={FieldKey("bar"): Mask(any=Mask())}
                    ),
                    FieldKey("def"): Mask(field_parts={FieldKey("baz"): Mask()}),
                },
            ),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc"), FieldKey("bar")]),
            "M": Mask(
                any=Mask(field_parts={FieldKey("bar"): Mask()}),
                field_parts={
                    FieldKey("abc"): Mask(field_parts={FieldKey("bar"): Mask()}),
                    FieldKey("def"): Mask(field_parts={FieldKey("baz"): Mask()}),
                },
            ),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(any=Mask()),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("abc")]),
            "M": Mask(any=Mask(any=Mask())),
            "Res": True,
            "Final": False,
        },
        {
            "FP": FieldPath([FieldKey("x")]),
            "M": Mask(
                any=Mask(),
                field_parts={FieldKey("x"): Mask(field_parts={FieldKey("y"): Mask()})},
            ),
            "Res": True,
            "Final": True,
        },
        {
            "FP": FieldPath([FieldKey("x")]),
            "M": Mask(
                any=Mask(field_parts={FieldKey("y"): Mask()}),
                field_parts={FieldKey("x"): Mask()},
            ),
            "Res": True,
            "Final": True,
        },
    ]

    for i, case in enumerate(cases):
        res = case["FP"].matches_reset_mask(case["M"])
        res_final = case["FP"].matches_reset_mask_final(case["M"])
        assert res == case["Res"], f"Failed on case {i}: {res} != {case['Res']}"
        assert (
            res_final == case["Final"]
        ), f"Failed on case {i}: {res} != {case['Final']}"  # noqa: E501


def test_fieldpath_matches_select_mask() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath, Mask

    cases = [
        {
            "FP": FieldPath([]),
            "M": None,
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("foo")]),
            "M": None,
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "M": None,
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "M": Mask(),
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("foo")]),
            "M": Mask(),
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([]),
            "M": Mask(),
            "Res": True,
        },
        {
            "FP": FieldPath([]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("a")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("b")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("b"), FieldKey("c")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("b"), FieldKey("c"), FieldKey("d")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("a"), FieldKey("c"), FieldKey("d")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("b"), FieldKey("d")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": False,
        },
        {
            "FP": FieldPath([FieldKey("d")]),
            "M": Mask.unmarshal("a,b.c"),
            "Res": False,
        },
        {
            "FP": FieldPath([FieldKey("a"), FieldKey("d")]),
            "M": Mask.unmarshal("a.*"),
            "Res": True,
        },
        {
            "FP": FieldPath([FieldKey("a"), FieldKey("d"), FieldKey("e")]),
            "M": Mask.unmarshal("a.*"),
            "Res": True,
            "Inner": True,
        },
        {
            "FP": FieldPath([FieldKey("a"), FieldKey("d"), FieldKey("e")]),
            "M": Mask.unmarshal("a.*.c"),
            "Res": False,
        },
        {
            "FP": FieldPath([FieldKey("a"), FieldKey("d"), FieldKey("c")]),
            "M": Mask.unmarshal("a.*.c"),
            "Res": True,
        },
    ]

    for i, case in enumerate(cases):
        # Test the MatchesSelectMask method
        res = case["FP"].matches_select_mask(case["M"])
        res2, inner = case["FP"].matches_select_mask_inner(case["M"])

        # Assert the results
        assert res == case["Res"], f"Failed on case {i}: {res} != {case['Res']}"
        assert res2 == case["Res"], f"Failed on case {i}: {res2} != {case['Res']}"
        assert inner == case.get(
            "Inner", False
        ), f"Failed on case {i}: {inner} != {case.get('Inner', False)}"  # noqa: E501


def test_fieldpath_marshal() -> None:
    from nebius.base.fieldmask import FieldKey, FieldPath

    cases = [
        {
            "FP": FieldPath([]),
            "M": "",
        },
        {
            "FP": FieldPath([FieldKey("foo")]),
            "M": "foo",
        },
        {
            "FP": FieldPath([FieldKey("foo"), FieldKey("bar")]),
            "M": "foo.bar",
        },
        {
            "FP": FieldPath([FieldKey("foo.bar")]),
            "M": '"foo.bar"',
        },
        {
            "FP": FieldPath([FieldKey("foo.bar"), FieldKey("baz")]),
            "M": '"foo.bar".baz',
        },
    ]

    for i, case in enumerate(cases):
        res = case["FP"].marshal()
        assert res == case["M"], f"Failed on case {i}: expected {case['M']}, got {res}"


def test_fieldpath_unmarshal() -> None:
    from nebius.base.fieldmask import Error, FieldKey, FieldPath

    cases = [
        {
            "NoStarter": True,
            "Err": "wrong type of source\\: \\<class \\'NoneType\\'\\>, expected str",
        },
        {
            "Mask": "(",
            "Err": "unclosed left brace at position 0 near",
        },
        {
            "Mask": "a,b",
            "Err": "multiple paths in the mask",
        },
        {
            "Mask": "a.b",
            "Result": FieldPath([FieldKey("a"), FieldKey("b")]),
        },
    ]

    for i, case in enumerate(cases):
        mask = None if case.get("NoStarter", False) else case["Mask"]
        if "Err" in case:
            with pytest.raises((Error), match=case["Err"]):
                FieldPath.unmarshal(mask)
        else:
            res = FieldPath.unmarshal(mask)
            assert (
                res == case["Result"]
            ), f"Failed on case {i}: expected {case['Result']}, got {res}"  # noqa: E501


def test_parse_fieldmask() -> None:
    from nebius.base.fieldmask import Mask
    from nebius.base.fieldmask_parser import ParseError, parse

    cases = [
        {"Input": "*,", "Err": r"unexpected end of mask"},
        {"Input": "*.", "Err": r"unexpected end of mask"},
        {
            "Input": "*.(",
            "Err": r"unclosed left brace at position 2 near \"\*\.\u20de\(\"",
        },  # noqa: E501
        {
            "Input": " \t\r\n*.( \t\r\n",
            "Err": r"unclosed left brace at position 6 near \" \\t\\r\\n\*\.\u20de\( \\t\\r\\n\"",  # noqa: E501
        },
        {
            "Input": "abcdefghijklmonpqrst.(abcdefghijklmonpqrst",
            "Err": r"unclosed left brace at position 21 near \"jklmonpqrst\.\u20de\(abcdefghijklmo\.\.\.\"",  # noqa: E501
        },
        {
            "Input": "abcdefghijklmonpqrst)abcdefghijklmonpqrst",
            "Err": r"unmatched right brace at position 20 near \"ijklmonpqrst\u20de\)abcdefghijklmo\.\.\.\"",  # noqa: E501
        },
        {
            "Input": "abcdefghijklmonpqrst..abcdefghijklmonpqrst",
            "Err": r"unexpected token TokenDOT\(\"\.\" pos 21\), expecting field or submask at position 21 near \"jklmonpqrst\.\u20de\.abcdefghijklmo\.\.\.\"",  # noqa: E501
        },
        {
            "Input": "abcdefghijklmonpqrst abcdefghijklmonpqrst feafwafwawfadwadw",
            "Err": r"unexpected token TokenPLAIN_KEY\(\"abcdefghijklmonpqrst\" pos 21\), expecting separator or closing brace at position 21 near \"jklmonpqrst \u20deabcdefghijklmon\.\.\.\"",  # noqa: E501
        },
        {"Input": "#", "Err": r"unexpected symbol at position 0 near \"\u20de#\""},
        {
            "Input": "#1234567890abcdefghijklmnopqrst",
            "Err": r"unexpected symbol at position 0 near \"\u20de#1234567890abcdefghijklmnop\.\.\.\"",  # noqa: E501
        },
        {
            "Input": '"1234567890abcdefghijklmnopqrst',
            "Err": r"unterminated quoted string at position 0 near \"\u20de\\\"1234567890abcdefghijklmnop\.\.\.\"",  # noqa: E501
        },
        {"Input": "", "Output": ""},
        {"Input": "()", "Output": ""},
        {"Input": " \t\r\n( \t\r\n) \t\r\n", "Output": ""},
        {"Input": " \t\r\n", "Output": ""},
        {"Input": "*", "Output": "*"},
        {"Input": " \t\r\n* \t\r\n", "Output": "*"},
        {"Input": " \t\r\na \t\r\n", "Output": "a"},
        {"Input": " \t\r\n( \t\r\na \t\r\n) \t\r\n", "Output": "a"},
        {"Input": "*,*,*,*", "Output": "*"},
        {"Input": "test", "Output": "test"},
        {"Input": '"test"', "Output": "test"},
        {"Input": '"test "', "Output": '"test "'},
        {"Input": "a,a", "Output": "a"},
        {"Input": "a.b", "Output": "a.b"},
        {"Input": "a \t\r\n. \t\r\nb", "Output": "a.b"},
        {"Input": "a \t\r\n, \t\r\na", "Output": "a"},
        {"Input": "*,test", "Output": "*,test"},
        {"Input": "* \t\r\n, \t\r\ntest", "Output": "*,test"},
        {"Input": "test,*", "Output": "*,test"},
        {"Input": "a.b,a.b", "Output": "a.b"},
        {"Input": "a.*,a.*", "Output": "a.*"},
        {"Input": "*.b,*.b", "Output": "*.b"},
        {"Input": "a.b,a.c", "Output": "a.(b,c)"},
        {"Input": "a.(b)", "Output": "a.b"},
        {"Input": "a.(b,())", "Output": "a.b"},
        {"Input": "a.((),b)", "Output": "a.b"},
        {"Input": "a.((()))", "Output": "a"},
        {"Input": "a.(b,c)", "Output": "a.(b,c)"},
        {"Input": "*.(b,c)", "Output": "*.(b,c)"},
        {"Input": "a.(b,c).(d,e)", "Output": "a.(b.(d,e),c.(d,e))"},
        {"Input": "a.(*,c).(d,e)", "Output": "a.(*.(d,e),c.(d,e))"},
        {"Input": "a.(((((((*,c))))))).(d,e)", "Output": "a.(*.(d,e),c.(d,e))"},
        {
            "Input": "(((((((a))))))).(((((*)))),(((c)))).(((((((d,(((e))))))))))",
            "Output": "a.(*.(d,e),c.(d,e))",
        },
        {"Input": "a.(b,c.(d,e))", "Output": "a.(b,c.(d,e))"},
        {"Input": "a.(*,b,c)", "Output": "a.(*,b,c)"},
        {"Input": "a.(*,b,c.(d,e))", "Output": "a.(*,b,c.(d,e))"},
        {
            "Input": "*.*.(a,b,c.*,d.(e,f),g.(*.(h,i),j,k)),1,A,B,l,m,n.*,o.(p,q,w,x),r.(*.(s,t),u.*,v),z.(*.y,u.*,v)",  # noqa: E501
            "Output": "*.*.(a,b,c.*,d.(e,f),g.(*.(h,i),j,k)),1,A,B,l,m,n.*,o.(p,q,w,x),r.(*.(s,t),u.*,v),z.(*.y,u.*,v)",  # noqa: E501
        },
        {
            "Input": 'a."\\",.() \\\\t\\\\r\\\\n".b',
            "Output": 'a."\\",.() \\\\t\\\\r\\\\n".b',
        },  # noqa: E501
    ]

    for i, case in enumerate(cases):
        if "Err" in case:
            with pytest.raises(ParseError, match=case["Err"]):
                parse(case["Input"])
        else:
            result = parse(case["Input"])
            assert isinstance(result, Mask)
            normalized = result.marshal()
            assert (
                normalized == case["Output"]
            ), f"Failed on case {i}: expected {case['Output']}, got {normalized}"  # noqa: E501


def test_mask_is_empty() -> None:
    from nebius.base.fieldmask import FieldKey, Mask

    assert Mask().is_empty()
    assert Mask(any=None).is_empty()
    assert Mask(field_parts=dict[FieldKey, Mask]()).is_empty()
    assert Mask(any=None, field_parts=dict[FieldKey, Mask]()).is_empty()
    assert Mask(any=None, field_parts=dict[FieldKey, Mask]()).is_empty()
    assert not Mask(any=Mask()).is_empty()
    assert not Mask(field_parts=dict[FieldKey, Mask]({FieldKey(""): Mask()})).is_empty()


def test_mask_marshal() -> None:
    from nebius.base.fieldmask import Mask

    infinite_mask = Mask()
    infinite_mask.any = infinite_mask

    cases = [
        {
            "Mask": Mask(),
            "Result": "",
        },
        {
            "Mask": Mask(),
            "Result": "",
        },
        {
            "Mask": infinite_mask,
            "Err": RecursionError,
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": infinite_mask,
                },
            ),
            "Err": RecursionError,
        },
        {
            "Mask": Mask(
                any=Mask(),
            ),
            "Result": "*",
        },
        {
            "Mask": Mask(any=Mask()),
            "Result": "*",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": Mask(),
                }
            ),
            "Result": "test",
        },
        {
            "Mask": Mask(
                field_parts=Mask(),
            ),
            "Result": "",
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    "test": Mask(),
                },
            ),
            "Result": "*,test",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": Mask(),
                    "foo": Mask(),
                },
            ),
            "Result": "foo,test",
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    "test": Mask(),
                    "foo": Mask(),
                },
            ),
            "Result": "*,foo,test",
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(),
                ),
            ),
            "Result": "*.*",
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(),
                    field_parts={
                        "test": Mask(),
                    },
                ),
            ),
            "Result": "*.(*,test)",
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(),
                    field_parts={
                        "test": Mask(
                            any=Mask(),
                        ),
                    },
                ),
            ),
            "Result": "*.(*,test.*)",
        },
        {
            "Mask": Mask(
                any=Mask(
                    field_parts={
                        "test": Mask(
                            any=Mask(),
                        ),
                    },
                ),
            ),
            "Result": "*.test.*",
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(
                        any=Mask(),
                    ),
                ),
            ),
            "Result": "*.*.*",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": Mask(
                        any=Mask(),
                    ),
                },
            ),
            "Result": "test.*",
        },
        {
            "Mask": Mask(
                any=Mask(
                    field_parts={
                        "test": Mask(),
                    },
                ),
            ),
            "Result": "*.test",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": Mask(
                        any=Mask(),
                    ),
                },
            ),
            "Result": "test.*",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test": Mask(
                        field_parts={
                            "inner": Mask(),
                        },
                    ),
                },
            ),
            "Result": "test.inner",
        },
        {
            "Mask": Mask(
                field_parts={
                    "test.inner": Mask(
                        field_parts={
                            "inner": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"test.inner".inner',
        },
        {
            "Mask": Mask(
                field_parts={
                    "test,inner": Mask(
                        field_parts={
                            "inner": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"test,inner".inner',
        },
        {
            "Mask": Mask(
                field_parts={
                    "test(inner)": Mask(
                        field_parts={
                            "inner": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"test(inner)".inner',
        },
        {
            "Mask": Mask(
                field_parts={
                    '"test"': Mask(),
                },
            ),
            "Result": '"\\"test\\""',
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    '"test"': Mask(),
                },
            ),
            "Result": '"\\"test\\"",*',
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    '",.() ' + "\t\r\n": Mask(),
                },
            ),
            "Result": '"\\",.() \\t\\r\\n",*',
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    '"test"': Mask(
                        field_parts={
                            "inner": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"\\"test\\"".inner,*',
        },
        {
            "Mask": Mask(
                any=Mask(),
                field_parts={
                    '"test"': Mask(
                        field_parts={
                            "inner": Mask(),
                            "*": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"\\"test\\"".("*",inner),*',
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(
                        field_parts={
                            "a": Mask(),
                            "b": Mask(),
                            "c": Mask(
                                any=Mask(),
                            ),
                            "d": Mask(
                                field_parts={
                                    "e": Mask(),
                                    "f": Mask(),
                                },
                            ),
                            "g": Mask(
                                any=Mask(
                                    field_parts={
                                        "h": Mask(),
                                        "i": Mask(),
                                    },
                                ),
                                field_parts={
                                    "j": Mask(),
                                    "k": Mask(),
                                },
                            ),
                        },
                    ),
                ),
                field_parts={
                    "l": Mask(),
                    "m": Mask(),
                    "n": Mask(
                        any=Mask(),
                    ),
                    "o": Mask(
                        field_parts={
                            "p": Mask(),
                            "q": Mask(),
                        },
                    ),
                    "r": Mask(
                        any=Mask(
                            field_parts={
                                "s": Mask(),
                                "t": Mask(),
                            },
                        ),
                        field_parts={
                            "u": Mask(
                                any=Mask(),
                            ),
                            "v": Mask(),
                        },
                    ),
                },
            ),
            "Result": "*.*.(a,b,c.*,d.(e,f),g.(*.(h,i),j,k)),l,m,n.*,o.(p,q),r.(*.(s,t),u.*,v)",  # noqa: E501
        },
        {
            "Mask": Mask(
                any=Mask(
                    any=Mask(
                        field_parts={
                            "a": Mask(),
                            '"b"': Mask(),
                            '"c"': Mask(
                                any=Mask(),
                            ),
                            '"d"': Mask(
                                field_parts={
                                    "e": Mask(),
                                    '"f"': Mask(),
                                },
                            ),
                            "g": Mask(
                                any=Mask(
                                    field_parts={
                                        '"h"': Mask(),
                                        "i": Mask(),
                                    },
                                ),
                                field_parts={
                                    '"j"': Mask(),
                                    "k": Mask(),
                                },
                            ),
                        },
                    ),
                ),
                field_parts={
                    "l": Mask(),
                    "m": Mask(),
                    "n": Mask(
                        any=Mask(),
                    ),
                    '"o"': Mask(
                        field_parts={
                            '"p"': Mask(),
                            "q": Mask(),
                            "*": Mask(),
                        },
                    ),
                    "r": Mask(
                        any=Mask(
                            field_parts={
                                "s": Mask(),
                                "t": Mask(),
                                "*": Mask(),
                            },
                        ),
                        field_parts={
                            "u": Mask(
                                any=Mask(),
                            ),
                            "v": Mask(),
                            "*": Mask(),
                        },
                    ),
                },
            ),
            "Result": '"\\"o\\"".("*","\\"p\\"",q),*.*.("\\"b\\"","\\"c\\"".*,"\\"d\\"".("\\"f\\"",e),a,g.("\\"j\\"",*.("\\"h\\"",i),k)),l,m,n.*,r.("*",*.("*",s,t),u.*,v)',  # noqa: E501
        },
    ]

    for i, case in enumerate(cases):
        mask = case["Mask"]
        expected_result = case.get("Result")
        expected_err = case.get("Err")

        if expected_err:
            with pytest.raises(expected_err):
                mask.marshal()
        else:
            result = mask.marshal()
            assert result == expected_result, f"Failed on case {i}"


def test_mask_unmarshal_text() -> None:
    from nebius.base.fieldmask import Error, Mask

    cases = [
        {"mask": "(", "err": 'unclosed left brace at position 0 near "\u20de("'},
        {"mask": "", "result": Mask()},
        {"mask": "a", "result": Mask(field_parts={"a": Mask()})},
        {
            "mask": "test.inner",
            "result": Mask(field_parts={"test": Mask(field_parts={"inner": Mask()})}),
        },
        {
            "mask": "*",
            "result": Mask(any=Mask()),
        },
        {
            "mask": "*.test",
            "result": Mask(any=Mask(field_parts={"test": Mask()})),
        },
        {
            "mask": "test.*",
            "result": Mask(field_parts={"test": Mask(any=Mask())}),
        },
        {
            "mask": "test.(inner,outer)",
            "result": Mask(
                field_parts={
                    "test": Mask(field_parts={"inner": Mask(), "outer": Mask()})
                }
            ),
        },
        {
            "mask": "*.*",
            "result": Mask(any=Mask(any=Mask())),
        },
    ]

    for i, case in enumerate(cases):
        expected_result = case.get("result")
        expected_err = case.get("err")

        if expected_err:
            with pytest.raises(Error) as exc_info:
                Mask.unmarshal(case["mask"])
            assert str(exc_info.value) == str(expected_err), f"Failed on case {i}"
        else:
            mask = Mask.unmarshal(case["mask"])
            assert mask == expected_result, f"Failed on case {i}"


def test_mask_equality() -> None:
    from nebius.base.fieldmask import Mask

    infinite_mask = Mask()
    infinite_mask.any = infinite_mask

    assert infinite_mask != infinite_mask
    assert Mask() != ""
    assert "" != Mask()

    # Test cases for equality
    masks = [
        Mask(),
        Mask(any=Mask()),
        Mask(any=Mask(any=Mask())),
        Mask(any=Mask(field_parts={"a": Mask()})),
        Mask(field_parts={"a": Mask()}),
        Mask(field_parts={"a": Mask(any=Mask())}),
        Mask(field_parts={"b": Mask()}),
        Mask(field_parts={"a": Mask(), "b": Mask()}),
        Mask(any=Mask(), field_parts={"a": Mask()}),
        Mask(any=Mask(), field_parts={"b": Mask()}),
        Mask(any=Mask(), field_parts={"a": Mask(), "b": Mask()}),
    ]

    for i, mask1 in enumerate(masks):
        assert mask1 == mask1
        assert mask1 == mask1.copy()
        assert mask1.copy() == mask1
        assert mask1 != infinite_mask
        assert infinite_mask != mask1
        for j, mask2 in enumerate(masks):
            if i != j:
                assert mask1 != mask2, f"mask{i} must not be equal to mask{j}"
                assert mask2 != mask1, f"mask{j} must not be equal to mask{i}"
                assert (
                    mask2.copy() != mask1
                ), f"mask{j} copy must not be equal to mask{i}"  # noqa: E501
                assert (
                    mask1.copy() != mask2
                ), f"mask{i} copy must not be equal to mask{j}"  # noqa: E501
                assert (
                    mask1 != mask2.copy()
                ), f"mask{i} must not be equal to mask{j} copy"  # noqa: E501
                assert (
                    mask2 != mask1.copy()
                ), f"mask{j} must not be equal to mask{i} copy"  # noqa: E501


def test_mask_copy() -> None:
    from nebius.base.fieldmask import Mask

    infinite_mask = Mask()
    infinite_mask.any = infinite_mask

    with pytest.raises(RecursionError):
        infinite_mask.copy()
    with pytest.raises(RecursionError):
        Mask(any=infinite_mask).copy()
    with pytest.raises(RecursionError):
        Mask(field_parts={"a": infinite_mask}).copy()

    m = Mask()
    c = m.copy()
    assert c == m
    m.any = Mask()
    assert c != m

    m = Mask(any=Mask())
    c = m.copy()
    assert c == m
    m.any.any = Mask()
    assert c != m

    m = Mask(field_parts={"a": Mask()})
    c = m.copy()
    assert c == m
    m.any = Mask()
    assert c != m

    m = Mask(field_parts={"a": Mask()})
    c = m.copy()
    assert c == m
    m.field_parts["c"] = Mask()
    assert c != m

    m = Mask(field_parts={"a": Mask()})
    c = m.copy()
    assert c == m
    m.field_parts["a"] = Mask(any=Mask())
    assert c != m

    m = Mask(field_parts={"a": Mask()})
    c = m.copy()
    assert c == m
    m.field_parts["a"].any = Mask()
    assert c != m


def test_mask_merge_infinite_recursion() -> None:
    from nebius.base.fieldmask import Mask

    infinite_mask = Mask()
    infinite_mask.any = infinite_mask

    cases = [
        (infinite_mask, infinite_mask, RecursionError),
        (Mask(), infinite_mask, RecursionError),
        (Mask(), Mask(any=infinite_mask), RecursionError),
    ]

    for a, b, expected_exception in cases:
        with pytest.raises(expected_exception):
            a += b


def test_mask_merge_success() -> None:
    from nebius.base.fieldmask import Mask

    cases = [
        (Mask(), Mask(), ""),
        (Mask(any=Mask()), Mask(), "*"),
        (Mask(any=Mask()), Mask(any=Mask()), "*"),
        (
            Mask(any=Mask(any=Mask())),
            Mask(any=Mask()),
            "*.*",
        ),
        (
            Mask(any=Mask()),
            Mask(field_parts={"test": Mask()}),
            "*,test",
        ),
        (
            Mask(any=Mask()),
            Mask(field_parts={}),
            "*",
        ),
        (
            Mask(
                any=Mask(
                    any=Mask(
                        field_parts={
                            "a": Mask(),
                            "b": Mask(),
                            "c": Mask(any=Mask()),
                            "d": Mask(
                                field_parts={
                                    "e": Mask(),
                                    "f": Mask(),
                                }
                            ),
                            "g": Mask(
                                any=Mask(
                                    field_parts={
                                        "h": Mask(),
                                        "i": Mask(),
                                    }
                                ),
                                field_parts={
                                    "j": Mask(),
                                    "k": Mask(),
                                },
                            ),
                        }
                    )
                ),
                field_parts={
                    "l": Mask(),
                    "m": Mask(),
                    "n": Mask(any=Mask()),
                    "o": Mask(
                        field_parts={
                            "p": Mask(),
                            "q": Mask(),
                        }
                    ),
                    "r": Mask(
                        any=Mask(
                            field_parts={
                                "s": Mask(),
                                "t": Mask(),
                            }
                        ),
                        field_parts={
                            "u": Mask(any=Mask()),
                            "v": Mask(),
                        },
                    ),
                },
            ),
            Mask(
                any=Mask(
                    any=Mask(
                        field_parts={
                            "a": Mask(),
                            "b": Mask(),
                            "c": Mask(any=Mask()),
                            "d": Mask(
                                field_parts={
                                    "e": Mask(),
                                    "f": Mask(),
                                }
                            ),
                            "g": Mask(
                                any=Mask(
                                    field_parts={
                                        "h": Mask(),
                                        "i": Mask(),
                                    }
                                ),
                                field_parts={
                                    "j": Mask(),
                                    "k": Mask(),
                                },
                            ),
                        }
                    )
                ),
                field_parts={
                    "l": Mask(),
                    "A": Mask(),
                    "B": Mask(),
                    "1": Mask(),
                    "o": Mask(
                        field_parts={
                            "w": Mask(),
                            "x": Mask(),
                        }
                    ),
                    "z": Mask(
                        any=Mask(
                            field_parts={
                                "y": Mask(),
                            }
                        ),
                        field_parts={
                            "u": Mask(any=Mask()),
                            "v": Mask(),
                        },
                    ),
                },
            ),
            "*.*.(a,b,c.*,d.(e,f),g.(*.(h,i),j,k)),1,A,B,l,m,n.*,o.(p,q,w,x),r.(*.(s,t),u.*,v),z.(*.y,u.*,v)",
        ),
    ]

    for a, b, expected_result in cases:
        a += b
        result = a.marshal()
        assert result == expected_result


def test_to_field_path() -> None:
    from nebius.base.fieldmask import Error, FieldPath, Mask

    cases = [
        (Mask(any=Mask()), Error("wildcard in the mask")),
        (Mask(field_parts={"b": Mask(any=Mask())}), Error("wildcard in the mask")),
        (Mask(), None),
        (Mask(field_parts={}), None),
        (
            Mask(field_parts={"a": Mask(), "b": Mask()}),
            Error("multiple paths in the mask"),
        ),
        (
            Mask(field_parts={"c": Mask(field_parts={"a": Mask(), "b": Mask()})}),
            Error("multiple paths in the mask"),
        ),
        (
            Mask(field_parts={"a": Mask(field_parts={"b": Mask()})}),
            FieldPath(["a", "b"]),
        ),
        (
            Mask(field_parts={"a": Mask(field_parts={})}),
            FieldPath(["a"]),
        ),
    ]

    for mask, expected in cases:
        if isinstance(expected, Error):
            with pytest.raises(Error) as exc_info:
                mask.to_field_path()
            assert str(exc_info.value) == str(expected)
            assert not mask.is_field_path()
        else:
            assert mask.to_field_path() == expected
            assert mask.is_field_path()


def test_mask_sub_mask():
    from nebius.base.fieldmask import FieldKey, Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    cases = [
        {"mask": Mask(), "key": "foo", "result": None, "err": None},
        {"mask": None, "key": "foo", "result": None, "err": None},
        {
            "mask": Mask(field_parts={"bar": Mask()}),
            "key": "foo",
            "result": None,
            "err": None,
        },  # noqa: E501
        {
            "mask": Mask(field_parts={"foo": Mask(field_parts={"bar": Mask()})}),
            "key": "foo",
            "result": Mask(field_parts={"bar": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(any=Mask(field_parts={"bar": Mask()})),
            "key": "foo",
            "result": Mask(field_parts={"bar": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(
                any=Mask(field_parts={"baz": Mask()}),
                field_parts={"foo": Mask(field_parts={"bar": Mask()})},
            ),
            "key": "foo",
            "result": Mask(field_parts={"bar": Mask(), "baz": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(
                any=Mask(field_parts={"baz": inf_mask}),
                field_parts={"foo": Mask(field_parts={"bar": Mask()})},
            ),
            "key": "foo",
            "result": None,
            "err": RecursionError,
        },
    ]

    for i, case in enumerate(cases):
        mask = case["mask"]
        key = FieldKey(case["key"])
        expected_result = case["result"]
        expected_error = case["err"]

        if expected_error:
            with pytest.raises(expected_error):
                result = mask.sub_mask(key) if mask else None
        else:
            result = mask.sub_mask(key) if mask else None
            assert result == expected_result, f"Case {i} failed"


def test_mask_sub_mask_by_path():
    from nebius.base.fieldmask import FieldPath, Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    cases = [
        {"mask": Mask(), "path": FieldPath(["foo"]), "result": None, "err": None},
        {
            "mask": Mask(field_parts={"bar": Mask()}),
            "path": FieldPath(["foo"]),
            "result": None,
            "err": None,
        },  # noqa: E501
        {
            "mask": Mask(field_parts={"foo": Mask(field_parts={"bar": Mask()})}),
            "path": FieldPath(["foo"]),
            "result": Mask(field_parts={"bar": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(any=Mask(field_parts={"bar": Mask()})),
            "path": FieldPath(["foo"]),
            "result": Mask(field_parts={"bar": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(
                any=Mask(field_parts={"baz": Mask()}),
                field_parts={"foo": Mask(field_parts={"bar": Mask()})},
            ),
            "path": FieldPath(["foo"]),
            "result": Mask(field_parts={"bar": Mask(), "baz": Mask()}),
            "err": None,
        },
        {
            "mask": Mask(
                any=Mask(field_parts={"baz": inf_mask}),
                field_parts={"foo": Mask(field_parts={"bar": Mask()})},
            ),
            "path": FieldPath(["foo"]),
            "result": None,
            "err": RecursionError,
        },
    ]

    for i, case in enumerate(cases):
        mask = case["mask"]
        path = case["path"]
        expected_result = case["result"]
        expected_error = case["err"]

        if expected_error:
            with pytest.raises(expected_error):
                result = mask.sub_mask(path) if mask else None
        else:
            result = mask.sub_mask(path) if mask else None
            assert result == expected_result, f"Case {i} failed"


def test_mask_intesect_reset_mask():
    from nebius.base.fieldmask import Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    assert Mask().intersect_reset_mask(None) is None
    assert Mask().intersect_reset_mask("") is None
    assert Mask().intersect_reset_mask(object()) is None

    with pytest.raises(RecursionError):
        inf_mask.intersect_reset_mask(inf_mask)
    with pytest.raises(RecursionError):
        Mask(any=inf_mask).intersect_reset_mask(Mask(any=inf_mask))

    cases = [
        ("", "", ""),
        ("a.(x,y,z),b.*", "*.x,a.z", "a.(x,z),b.x"),
        ("a", "*", "a"),
    ]
    for i, case in enumerate(cases):
        a, b, r = case
        m = Mask.unmarshal(a).intersect_reset_mask(Mask.unmarshal(b))
        assert m == Mask.unmarshal(r), f"Case {i} failed"


def test_mask_intesect_dumb():
    from nebius.base.fieldmask import Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    assert Mask().intersect_dumb(None) is None
    assert Mask().intersect_dumb("") is None
    assert Mask().intersect_dumb(object()) is None

    with pytest.raises(RecursionError):
        inf_mask.intersect_dumb(inf_mask)
    with pytest.raises(RecursionError):
        Mask(any=inf_mask).intersect_dumb(Mask(any=inf_mask))

    cases = [
        ("", "", ""),
        ("*.(a,b),x,y", "*.(a,b),x,y", "*.(a,b),x,y"),
        ("a", "*", ""),
        ("*.(a,b),x,y", "*.(x,y),z,f", "*"),
        ("*.(a,b),x,y", "*.(a,y),x,f", "*.a,x"),
    ]
    for i, case in enumerate(cases):
        a, b, r = case
        m = Mask.unmarshal(a).intersect_dumb(Mask.unmarshal(b))
        assert m == Mask.unmarshal(r), f"Case {i} failed"


def test_mask_subtract_dumb():
    from nebius.base.fieldmask import Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    assert Mask().subtract_dumb(None) is None
    assert Mask().subtract_dumb("") is None
    assert Mask().subtract_dumb(object()) is None

    with pytest.raises(RecursionError):
        inf_mask.subtract_dumb(inf_mask)
    with pytest.raises(RecursionError):
        Mask(any=inf_mask).subtract_dumb(Mask(any=inf_mask))

    cases = [
        ("x.(a,b),*.(c,d),e,f", "x.(a,b),*.(c,d),e,f", ""),
        ("x.(a,b),*.(c,d),e,f", "x.(a),*.(c),e", "x.b,*.d,f"),
        ("a", "*", "a"),
        ("a", "a", ""),
        ("a", "b", "a"),
    ]
    for i, case in enumerate(cases):
        a, b, r = case
        mask_a = Mask.unmarshal(a)
        mask_b = Mask.unmarshal(b)
        mask_r = Mask.unmarshal(r)
        assert isinstance(mask_a, Mask), f"Case {i} failed: {a} must be mask"
        assert isinstance(mask_b, Mask), f"Case {i} failed: {b} must be mask"
        assert isinstance(mask_r, Mask), f"Case {i} failed: {r} must be mask"
        mask_a.subtract_dumb(mask_b)
        assert mask_a == mask_r, f"Case {i} failed: {mask_a} != {mask_r}"


def test_mask_subtract_reset_mask():
    from nebius.base.fieldmask import Mask

    inf_mask = Mask()
    inf_mask.field_parts["x"] = inf_mask

    assert Mask().subtract_reset_mask(None) is None
    assert Mask().subtract_reset_mask("") is None
    assert Mask().subtract_reset_mask(object()) is None

    with pytest.raises(RecursionError):
        inf_mask.subtract_reset_mask(inf_mask)
    with pytest.raises(RecursionError):
        Mask(any=inf_mask).subtract_reset_mask(Mask(any=inf_mask))

    cases = [
        ("x.(a,b),*.(c,d),e,f", "x.(a,b),*.(c,d),e,f", ""),
        ("x.(a,b),*.(c,d),e,f", "x.(a),*.(c),e", "x.b,*.d"),
    ]
    for i, case in enumerate(cases):
        a, b, r = case
        mask_a = Mask.unmarshal(a)
        mask_b = Mask.unmarshal(b)
        mask_r = Mask.unmarshal(r)
        assert isinstance(mask_a, Mask), f"Case {i} failed: {a} must be mask"
        assert isinstance(mask_b, Mask), f"Case {i} failed: {b} must be mask"
        assert isinstance(mask_r, Mask), f"Case {i} failed: {r} must be mask"
        mask_a.subtract_reset_mask(mask_b)
        assert mask_a == mask_r, f"Case {i} failed: {mask_a} != {mask_r}"
