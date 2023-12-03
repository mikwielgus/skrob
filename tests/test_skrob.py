import skrob.cli
from io import StringIO

def run_then_compare(argv, reference):
    with StringIO() as stream:
        skrob.cli.run(["skrob"] + argv, stream)
        assert stream.getvalue() == reference

def run_then_count(argv, count):
    with StringIO() as stream:
        skrob.cli.run(["skrob"] + argv, stream)
        assert stream.getvalue().count("<cooked") == count

def test_hackernews_json_thread_upward():
    run_then_compare(["""
        {
            id::text;
            by::text;
            parent
                `concat('https://hacker-news.firebaseio.com/v0/item/', //text(), '.json')`
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

def test_discourse_json_thread():
    run_then_count(["-n", "1",
    """
        ;
        post_stream stream
            `split(//item, 20)[position()>=2]`
            `concat('https://try.discourse.org/t/301/posts.json?post_ids[]=',
                    string-join(//chunk/item, '&post_ids[]='))`
            {->;} !;
    """,
    "https://try.discourse.org/t/what-happens-when-a-topic-has-over-1000-replies/301.json"],
                   1000)

