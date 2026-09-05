from gui.src.utils.tag_search_parser import (
    AndNode,
    CompoundTagQueryParser,
    EmptyQueryNode,
    NotNode,
    OrNode,
    TagLiteralNode,
    evaluate_tag_query,
    extract_referenced_tags,
    normalize_tag,
    parse_tag_query,
    validate_tag_query,
)


def test_normalize_tag():
    assert normalize_tag("  Blue Eyes  ") == "blue_eyes"
    assert normalize_tag("Long_Hair") == "long_hair"
    assert normalize_tag("K-ON!") == "k-on!"


def test_empty_query():
    node = parse_tag_query("")
    assert isinstance(node, EmptyQueryNode)
    assert evaluate_tag_query("", ["solo", "1girl"]) is True
    assert extract_referenced_tags("") == set()

    is_valid, err = validate_tag_query("   ")
    assert is_valid is True
    assert err is None


def test_single_tag():
    node = parse_tag_query("solo")
    assert isinstance(node, TagLiteralNode)
    assert node.tag == "solo"
    assert evaluate_tag_query("solo", ["solo", "1girl"]) is True
    assert evaluate_tag_query("solo", ["1girl", "hat"]) is False
    assert extract_referenced_tags("solo") == {"solo"}


def test_and_query_explicit_and_implicit():
    # Explicit AND
    node_explicit = parse_tag_query("solo AND 1girl")
    assert isinstance(node_explicit, AndNode)
    assert evaluate_tag_query("solo AND 1girl", ["solo", "1girl"]) is True
    assert evaluate_tag_query("solo AND 1girl", ["solo"]) is False

    # Implicit AND
    node_implicit = parse_tag_query("solo 1girl")
    assert isinstance(node_implicit, AndNode)
    assert evaluate_tag_query("solo 1girl", ["solo", "1girl", "blue_eyes"]) is True
    assert evaluate_tag_query("solo 1girl", ["solo"]) is False

    # && and & symbols
    assert evaluate_tag_query("solo && 1girl", ["solo", "1girl"]) is True
    assert evaluate_tag_query("solo & 1girl", ["solo", "1girl"]) is True


def test_or_query():
    node = parse_tag_query("sword OR staff")
    assert isinstance(node, OrNode)
    assert evaluate_tag_query("sword OR staff", ["sword"]) is True
    assert evaluate_tag_query("sword OR staff", ["staff"]) is True
    assert evaluate_tag_query("sword OR staff", ["bow"]) is False

    # || and | symbols
    assert evaluate_tag_query("sword || staff", ["staff"]) is True
    assert evaluate_tag_query("sword | staff", ["bow"]) is False


def test_not_query_and_prefix_shorthand():
    # Explicit NOT
    node = CompoundTagQueryParser("NOT chibi").parse()
    assert isinstance(node, NotNode)
    assert evaluate_tag_query("NOT chibi", ["solo", "1girl"]) is True
    assert evaluate_tag_query("NOT chibi", ["solo", "chibi"]) is False

    # Prefix -
    assert evaluate_tag_query("solo -chibi", ["solo", "1girl"]) is True
    assert evaluate_tag_query("solo -chibi", ["solo", "chibi"]) is False

    # Prefix !
    assert evaluate_tag_query("solo !chibi", ["solo", "1girl"]) is True
    assert evaluate_tag_query("solo !chibi", ["solo", "chibi"]) is False



def test_quoted_phrases():
    # Quoted string with spaces
    assert evaluate_tag_query('"blue eyes" AND "long hair"', ["blue_eyes", "long_hair"]) is True
    assert evaluate_tag_query('"blue eyes" AND "long hair"', ["blue_eyes", "short_hair"]) is False
    assert evaluate_tag_query("'black hair' OR 'white hair'", ["white_hair"]) is True


def test_parentheses_and_operator_precedence():
    # AND has higher precedence than OR: a OR b AND c == a OR (b AND c)
    q = "sword OR magic AND staff"
    assert evaluate_tag_query(q, ["sword"]) is True
    assert evaluate_tag_query(q, ["magic"]) is False
    assert evaluate_tag_query(q, ["magic", "staff"]) is True

    # Explicit parentheses override: (sword OR magic) AND staff
    q_paren = "(sword OR magic) AND staff"
    assert evaluate_tag_query(q_paren, ["sword"]) is False
    assert evaluate_tag_query(q_paren, ["sword", "staff"]) is True
    assert evaluate_tag_query(q_paren, ["magic", "staff"]) is True


def test_nested_complex_expression():
    q = '1girl (blue_eyes OR "red eyes") -chibi -comic'
    tags_pass = ["1girl", "red_eyes", "smile"]
    tags_fail_chibi = ["1girl", "red_eyes", "chibi"]
    tags_fail_eye = ["1girl", "green_eyes"]

    assert evaluate_tag_query(q, tags_pass) is True
    assert evaluate_tag_query(q, tags_fail_chibi) is False
    assert evaluate_tag_query(q, tags_fail_eye) is False

    referenced = extract_referenced_tags(q)
    assert referenced == {"1girl", "blue_eyes", "red_eyes", "chibi", "comic"}


def test_syntax_validation_and_errors():
    is_valid, err = validate_tag_query("solo AND (1girl OR hat)")
    assert is_valid is True
    assert err is None

    is_invalid, err = validate_tag_query("solo AND (1girl OR")
    assert is_invalid is False
    assert err is not None

    is_invalid, err = validate_tag_query("AND")
    assert is_invalid is False
    assert err is not None
