from agentic_bench_gen.logio import TeeConsole


def test_tee_console_mirrors_prints_to_attached_log(tmp_path):
    console = TeeConsole()
    log = tmp_path / "runs" / "generation.log"
    console.attach_log_file(log)
    console.print("[bold]Architect (round 0):[/bold] hls_case tokens: in=1 out=2")
    console.detach_log_file()

    text = log.read_text()
    assert "run started" in text
    assert "Architect (round 0): hls_case tokens: in=1 out=2" in text
    # Markup is rendered, not written literally.
    assert "[bold]" not in text


def test_tee_console_without_log_attached_does_not_crash(capsys):
    console = TeeConsole()
    console.print("hello")
    console.detach_log_file()  # no-op when nothing attached
    assert "hello" in capsys.readouterr().out


def test_log_only_writes_to_file_but_not_terminal(tmp_path, capsys):
    console = TeeConsole()
    log = tmp_path / "generation.log"
    console.attach_log_file(log)
    console.log_only('raw response with [TEST] PASS and {"json": [1, 2]}')
    console.detach_log_file()

    assert capsys.readouterr().out == ""  # nothing on the terminal
    text = log.read_text()
    # Stored verbatim: bracket sequences are not eaten as rich markup.
    assert 'raw response with [TEST] PASS and {"json": [1, 2]}' in text


def test_log_only_is_a_noop_without_an_attached_log(capsys):
    console = TeeConsole()
    console.log_only("dropped")
    assert capsys.readouterr().out == ""


def test_reattaching_switches_log_files(tmp_path):
    console = TeeConsole()
    first, second = tmp_path / "a.log", tmp_path / "b.log"
    console.attach_log_file(first)
    console.print("one")
    console.attach_log_file(second)
    console.print("two")
    console.detach_log_file()
    assert "one" in first.read_text() and "two" not in first.read_text()
    assert "two" in second.read_text()
