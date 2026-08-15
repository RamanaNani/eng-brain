def selfcheck():
    import tempfile

    # --- modes: fixtures laid out exactly as slice/SKILL.md Phase 4 documents ---
    d = Path(tempfile.mkdtemp())
    arch = d / "ARCHITECTURE.md"

    assert main(["modes", str(d)]) == 1, "a missing ARCHITECTURE.md must fail"

    arch.write_text("# Feature\n\n## Interfaces\nnothing here\n")
    assert main(["modes", str(d)]) == 1, "no '## Failure modes' section must fail"

    arch.write_text(
        "# Feature\n\n"
        "## Failure modes\n"
        "| Mode | Guaranteed behaviour |\n"
        "|---|---|\n"
        "| pooler drops the prepared statement | search returns empty, not an error |\n"
        "| capture resolves the wrong source | the write lands in a code source |\n"
        "\n## Interfaces\nunrelated\n"
    )
    # Exit 1 alone does not prove this branch survives: with no briefs, every mode
    # is also "never reaches any brief". That diagnosis would send the operator to
    # edit files that do not exist, so the message is the behaviour here.
    probs = check_modes(str(d))
    assert probs and "no slice briefs found" in probs[0], \
        f"no briefs must be named as such, not listed as one miss per mode: {probs}"

    # An ADR is not a brief. It covers mode two; the gate must still report mode two
    # missing, which is only true if slices/ IS read and ADR-*.md is NOT.
    (d / "ADR-001-source-resolution.md").write_text(
        "## Edge cases to test\n- capture resolves the wrong source\n")
    (d / "slices").mkdir()
    (d / "slices" / "01-pooler.md").write_text(
        "# Slice 01\n\n## Edge cases to test\n- pooler drops the prepared statement\n")
    probs = check_modes(str(d))
    assert len(probs) == 1 and "wrong source" in probs[0], (
        f"a brief under slices/ must count and an ADR must not: {probs}")

    (d / "02-source.md").write_text(
        "# Slice 02\n\n## Out of scope\n"
        "- capture resolves the wrong source — owned by the ops runbook\n")
    assert main(["modes", str(d)]) == 0, "a root-level brief must still count"

    # --- testout ---
    t = Path(tempfile.mkdtemp())
    out = t / "test_output.txt"

    def testout(sample):
        out.write_text(sample)
        return main(["testout", str(out)])

    assert testout("") == 1, "empty output must fail"
    assert testout("running the suite...\nlooks good to me!\n") == 1, \
        "prose with no counts must fail"

    # Both of those also trip the zero-passing check below, so the exit code alone
    # cannot tell whether these two branches still exist. Their whole job is the
    # message — the operator has to know whether the file was empty or merely
    # unparseable — so the message is what has to be pinned.
    out.write_text("")
    assert "did not run the tests" in check_testout(str(out))[0], \
        "an empty file must be reported as never run, not as an unparseable one"
    out.write_text("running the suite...\nlooks good to me!\n")
    assert "no runner summary" in check_testout(str(out))[0], \
        "prose must be reported as NOT RUN, not as a suite that collected nothing"

    # The three fixtures the round-1 critic proved this gate PASSED. All red.
    assert testout("=== 3 failed, 5 passed in 2.1s ===") == 1, \
        "pytest red must fail: 3 failed is not a pass"