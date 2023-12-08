import skrob.cli
import pytest
from io import StringIO


class HeadStream:
    def __init__(self, stream, max_lines):
        self._stream = stream
        self._max_lines = max_lines
        self.counter = 0

    def write(self, text):
        self._stream.write(text)
        self.counter += 1

        if self.counter >= self._max_lines:
            raise BrokenPipeError

    def flush(self):
        self._stream.flush()


def run_then_compare(argv, reference):
    with StringIO() as output_stream:
        skrob.cli.run(["skrob"] + argv, output_stream)
        assert output_stream.getvalue() == reference


def run_then_count(argv, substring, count):
    with StringIO() as output_stream:
        skrob.cli.run(["skrob"] + argv, output_stream)
        assert output_stream.getvalue().count(substring) == count


def run_up_to_writes(argv, count):
    with StringIO() as output_stream:
        wrapped_stream = HeadStream(output_stream, count)

        with pytest.raises(SystemExit):
            skrob.cli.run(["skrob"] + argv, wrapped_stream)

        assert wrapped_stream.counter == count


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
                parent %concat('https://hacker-news.firebaseio.com/v0/item/', ., '.json')% ->
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
            kids item %concat('https://hacker-news.firebaseio.com/v0/item/', ., '.json')% ->
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
                %split(//item, 20)[position()>=2]%
                %concat('https://try.discourse.org/t/301/posts.json?post_ids[]=',
                        string-join(//chunk/item, '&post_ids[]='))%
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
                more_topics_url::text %re:replace(., 'latest\?', '', 'latest.json?')% ->
            } !;
            """,
            "https://try.discourse.org/latest.json",
        ],
        "<id",
        46,
    )


def test_mastodon_json_user():
    run_up_to_writes(
        [
            """
            %concat('/api/v1/accounts/', //id, '/statuses?limit=40')% -> {
                root>item>content;
                %(//root/item/id)[last()]% %concat('statuses?limit=40&max_id=', .)% ->
            } !;
            """,
            "https://mastodon.social/api/v1/accounts/lookup?acct=Gargron",
        ],
        200,
    )
