from scripts.check_coverage import below_floor, main


def report(**percent):
    return {"files": {path: {"summary": {"percent_covered": p}} for path, p in percent.items()}}


def test_a_service_below_the_floor_is_reported_and_providers_are_exempt():
    files = report(
        **{
            "app/services/rebalance.py": 92.0,
            "app/services/benchmark_service.py": 40.0,
            "app/services/picnic_provider.py": 10.0,
            "app/services/__init__.py": 0.0,
            "app/routers/assets.py": 5.0,
        }
    )
    assert below_floor(files) == [("app/services/benchmark_service.py", 40.0)]


def test_the_exit_code_tells_ci(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text('{"files": {"app/services/a.py": {"summary": {"percent_covered": 80.0}}}}')
    bad = tmp_path / "bad.json"
    bad.write_text('{"files": {"app/services/a.py": {"summary": {"percent_covered": 79.9}}}}')

    assert main([str(good)]) == 0
    assert main([str(bad)]) == 1
    assert "79.9% covered" in capsys.readouterr().out
    assert main([]) == 2
