import tempfile
from pathlib import Path

import pytest


@pytest.mark.kinda_slow
@pytest.mark.parametrize("dryrun", [True, False], ids=["dryrun", "not-dryrun"])
def test_autofix(run_semgrep_in_tmp, snapshot, dryrun):
    snapshot.assert_match(
        run_semgrep_in_tmp(
            "rules/autofix/autofix.yaml",
            target_name="autofix/autofix.py",
        )[0],
        "results.json",
    )

    # Make a copy of the target file b/c autofixes are inline. We
    # don't want to modify the the actual target file, and there
    # isn't a way currently to dump the fixed file contents before
    # writing.
    # This tempfile will be deleted when the with context closes.
    with tempfile.NamedTemporaryFile(dir=Path("targets")) as tf:
        with open(Path("targets") / "autofix/autofix.py", "r") as fin:
            tf.write(fin.read().encode("utf-8"))
        tf.flush()  # Make sure file has been copied.
        tf.seek(
            0
        )  # Seek to beginning since Semgrep will be reading from it. Just in case.
        run_semgrep_in_tmp(
            "rules/autofix/autofix.yaml",
            target_name=tf.name,
            options=["--autofix", "--dryrun"] if dryrun else ["--autofix"],
        )
        tf.seek(0)  # Seek to beginning again so we can read and compare to snapshot.
        snapshot.assert_match(
            tf.read().decode("utf-8", errors="replace"),
            "autofix-dryrun" if dryrun else "autofix-fixed",
        )


@pytest.mark.kinda_slow
@pytest.mark.parametrize("dryrun", [True, False], ids=["dryrun", "not-dryrun"])
@pytest.mark.parametrize(
    "rule,target",
    [
        ("rules/autofix/csv-writer.yaml", "autofix/csv-writer.py"),
        ("rules/autofix/defaulthttpclient.yaml", "autofix/defaulthttpclient.java"),
        ("rules/autofix/flask-use-jsonify.yaml", "autofix/flask-use-jsonify.py"),
        ("rules/autofix/requests-use-timeout.yaml", "autofix/requests-use-timeout.py"),
        (
            "rules/autofix/django-none-password-default.yaml",
            "autofix/django-none-password-default.py",
        ),
        (
            "rules/autofix/terraform-ec2-instance-metadata-options.yaml",
            "autofix/terraform-ec2-instance-metadata-options.hcl",
        ),
        (
            "rules/autofix/python-assert-statement.yaml",
            "autofix/python-assert-statement.py",
        ),
        ("rules/autofix/java-string-wrap.yaml", "autofix/java-string-wrap.java"),
        ("rules/autofix/two-autofixes.yaml", "autofix/two-autofixes.txt"),
    ],
)
@pytest.mark.kinda_slow
def test_regex_autofix(run_semgrep_in_tmp, snapshot, rule, target, dryrun):
    # Yes, this is fugly. I apologize. T_T
    snapshot.assert_match(
        run_semgrep_in_tmp(rule, target_name=target)[0],
        "results.json",
    )
    # Make a copy of the target file b/c autofixes are inline. We
    # don't want to modify the the actual target file, and there
    # isn't a way currently to dump the fixed file contents before
    # writing.
    # This tempfile will be deleted when the with context closes.
    with tempfile.NamedTemporaryFile(dir=Path("targets")) as tf:
        with open(Path("targets") / target, "r") as fin:
            tf.write(fin.read().encode("utf-8"))
        tf.flush()  # Make sure file has been copied.
        tf.seek(
            0
        )  # Seek to beginning since Semgrep will be reading from it. Just in case.
        run_semgrep_in_tmp(
            rule,
            target_name=tf.name,
            options=["--autofix", "--dryrun"] if dryrun else ["--autofix"],
        )
        tf.seek(0)  # Seek to beginning again so we can read and compare to snapshot.
        snapshot.assert_match(
            tf.read().decode("utf-8", errors="replace"),
            (f"{target}-dryrun" if dryrun else f"{target}-fixed"),
        )
