import pytest
from connectors.utils import html_to_plain_text, compute_content_hash, parse_tag_date, join_tag_array
from datetime import datetime, timezone

def test_html_to_plain_text():
    html = "<p>Hello &nbsp; <b>world</b>! &lt;tag&gt; &amp; &quot;quotes&quot;</p>"
    expected = "Hello world ! <tag> & \"quotes\""
    assert html_to_plain_text(html) == expected

def test_compute_content_hash():
    content = "test content"
    # echo -n "test content" | shasum -a 256
    expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
    assert compute_content_hash(content) == expected

def test_parse_tag_date():
    iso_date = "2023-10-27T10:00:00Z"
    expected = datetime(2023, 10, 27, 10, 0, 0, tzinfo=timezone.utc)
    assert parse_tag_date(iso_date) == expected
    
    assert parse_tag_date("invalid-date") is None
    assert parse_tag_date(123) is None

def test_join_tag_array():
    arr = ["one", "two", "three"]
    assert join_tag_array(arr) == "one, two, three"
    
    assert join_tag_array([]) is None
    assert join_tag_array("not an array") is None
    assert join_tag_array(["one", None, "three"]) == "one, three"
