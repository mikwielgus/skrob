import skrob.cli
from io import StringIO


def run_then_compare(argv, reference):
    with StringIO() as output_stream:
        skrob.cli.run(["skrob"] + argv, output_stream)
        assert output_stream.getvalue() == reference


def run_then_count(argv, substring, count):
    with StringIO() as output_stream:
        skrob.cli.run(["skrob"] + argv, output_stream)
        assert output_stream.getvalue().count(substring) == count


def test_phpbb_html_thread():
    run_then_count(
        [
            """
            {
                .content;
                a[rel='next']::attr(href) ->
            } !;
            """,
            "https://www.phpbb.com/community/viewtopic.php?t=2118",
        ],
        'class="content"',
        60,
    )


def test_phpbb_html_subforum():
    # Note: the number of topics PhpBB shows is different than the number of extracted ones. This
    # may either be a bug or some threads or posts may be just hidden.
    run_then_count(
        [
            """
            {
                .topictitle::attr(href) -> {
                    .content;
                    a[rel='next']::attr(href) ->
                } !;
                a[rel='next']::attr(href) ->
            } !;
            """,
            "https://www.phpbb.com/community/viewforum.php?f=691",
        ],
        'class="content"',
        1519,
    )


def test_hackernews_json_thread_upward():
    run_then_compare(
        [
            """
            {
                id::text;
                by::text;
                parent `concat('https://hacker-news.firebaseio.com/v0/item/', ., '.json')` ->
            } {
                url::text;
            } !;
            """,
            "https://hacker-news.firebaseio.com/v0/item/1079.json",
        ],
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


def test_hackernews_json_thread_downward():
    run_then_count(
        [
            """
        {
            id::text;
            kids item `concat('https://hacker-news.firebaseio.com/v0/item/', ., '.json')` ->
        } !;
    """,
            "https://hacker-news.firebaseio.com/v0/item/1.json",
        ],
        "\n",
        18,
    )


def test_discourse_json_thread():
    run_then_count(
        [
            "-n",
            "1",
            """
            ;
            post_stream stream
                `split(//item, 20)[position()>=2]`
                `concat('https://try.discourse.org/t/301/posts.json?post_ids[]=',
                        string-join(//chunk/item, '&post_ids[]='))`
                {->;} !;
            """,
            "https://try.discourse.org/t/what-happens-when-a-topic-has-over-1000-replies/301.json",
        ],
        "<cooked",
        1000,
    )


def test_discourse_json_latest():
    run_then_count(
        [
            "-n",
            "1",
            """
            {
                topic_list topics;
                more_topics_url::text `re:replace(., 'latest\?', '', 'latest.json?')` ->
            } !;
            """,
            "https://try.discourse.org/latest.json",
        ],
        "<id",
        46,
    )


def test_mastodon_json_user():
    run_then_count(
        [
            """
            `concat('/api/v1/accounts/', //id, '/statuses?limit=40')` -> {
                content;
                `(//item/id)[last()]` `concat('statuses?limit=40&max_id=', .)` ->
            } !;
            """,
            "https://mastodon.social/api/v1/accounts/lookup?acct=Gargron",
        ],
        "<content",
        720,
    )
