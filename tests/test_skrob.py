import skrob.cli
from io import StringIO

def run_then_compare(argv, reference):
    with StringIO() as stream:
        skrob.cli.run(["skrob"] + argv, stream)
        assert stream.getvalue() == reference

def test_hackernews_json():
    run_then_compare(["""
        {
            id::text;
            by::text;
            parent `concat('https://hacker-news.firebaseio.com/v0/item/', //text(), '.json')`
            ->
        } {
            url::text;
        } !;
        """,
        "https://hacker-news.firebaseio.com/v0/item/1079.json"],
        "1079\n"
        "dmon\n"
        "17\n"
        "pg\n"
        "15\n"
        "sama\n"
        "1\n"
        "pg\n"
        "http://ycombinator.com\n",
    )

