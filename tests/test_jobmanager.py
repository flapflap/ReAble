import threading
import time

import pytest

from reable.jobs import Cancelled, JobBusy, JobManager


def wait(job, timeout=5):
    t0 = time.time()
    while job.state in ("running", "stopping") and time.time() - t0 < timeout:
        time.sleep(0.01)
    return job


def test_runs_a_job_and_keeps_events_and_result():
    m = JobManager()

    def work(rep, cancel):
        for i in range(3):
            rep.step("lecture", f"p{i}")
            rep.finish_item(f"p{i}", "converti")
        rep.end("fini")
        return {"n": 3}
    j = wait(m.start("convert", 3, work))
    assert j.state == "done" and j.result == {"n": 3}
    assert j.events[-1].status == "done" and j.events[-1].index == 3
    assert m.get(j.id) is j and m.current() is None


def test_only_one_job_at_a_time():
    m = JobManager()
    gate = threading.Event()

    def work(rep, cancel):
        gate.wait(5)
    j = m.start("analyze", 1, work)
    with pytest.raises(JobBusy):
        m.start("convert", 1, work)
    gate.set()
    wait(j)
    m.start("convert", 1, lambda rep, cancel: None)             # libre à nouveau


def test_stop_goes_through_stopping_then_stopped():
    m = JobManager()
    started = threading.Event()

    def work(rep, cancel):
        started.set()
        while True:
            rep.step("conversion", "x")
            time.sleep(0.01)
    j = m.start("convert", 10, work)
    started.wait(5)
    m.stop(j.id)
    assert j.state in ("stopping", "stopped")
    wait(j)
    assert j.state == "stopped" and j.error is None


def test_errors_are_captured_not_raised():
    m = JobManager()

    def work(rep, cancel):
        raise ValueError("boum")
    j = wait(m.start("convert", 1, work))
    assert j.state == "error" and "boum" in j.error


def test_snapshot_is_json_friendly_and_can_be_polled_from_an_index():
    m = JobManager()

    def work(rep, cancel):
        for i in range(5):
            rep.step("lecture", f"p{i}")
            rep.finish_item(f"p{i}", "converti")
    j = wait(m.start("analyze", 5, work))
    snap = j.snapshot(since=3)
    assert snap["state"] == "done" and snap["total_events"] == len(j.events)
    assert len(snap["events"]) == len(j.events) - 3 and snap["last"]["index"] == 5
    import json
    json.dumps(snap)
