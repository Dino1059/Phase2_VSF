import pytest
from eval.fault_injector import FaultInjector, InjectedFault
from eval.benchmark import BenchmarkHarness, BenchmarkMetrics, compute_f1


def test_fault_injector_init():
    fi = FaultInjector(seed=42)
    assert fi.seed == 42
    assert len(fi.injected) == 0

def test_inject_all():
    fi = FaultInjector(seed=42)
    faults = fi.inject_all()
    assert len(faults) == 9
    families = {f.fault_family for f in faults}
    assert families == set(FaultInjector.FAULT_FAMILIES)

def test_ground_truth():
    fi = FaultInjector()
    fi.inject_all()
    gt = fi.get_ground_truth()
    assert len(gt) == 9
    assert all("fault_id" in g for g in gt)

def test_injected_fault_dataclass():
    f = InjectedFault(fault_family="test", table="t", column="c")
    assert f.fault_family == "test"
    assert f.fault_id  # auto-generated

def test_compute_f1():
    assert compute_f1(1.0, 1.0) == 1.0
    assert compute_f1(0.0, 0.0) == 0.0
    assert abs(compute_f1(0.5, 0.5) - 0.5) < 0.01

def test_benchmark_c0():
    h = BenchmarkHarness(seed=42)
    c0 = h.run_c0()
    assert c0.tier == "C0"
    assert c0.precision >= 0.9
    assert c0.faults_detected == 2  # type + range
    assert c0.cost_tokens == 0

def test_benchmark_c1():
    h = BenchmarkHarness(seed=42)
    h.run_c0()  # Need injected faults
    c1 = h.run_c1()
    assert c1.tier == "C1"
    assert c1.faults_detected == 4
    assert c1.cost_tokens > 0

def test_benchmark_a1():
    h = BenchmarkHarness(seed=42)
    h.run_c0()
    a1 = h.run_a1()
    assert a1.tier == "A1"
    assert a1.faults_detected == 9  # All families
    assert a1.precision >= 0.80

def test_a1_beats_c1_recall():
    h = BenchmarkHarness(seed=42)
    h.run_all()
    assert h.results["A1"].recall >= h.results["C1"].recall + 0.10

def test_a1_precision_gate():
    h = BenchmarkHarness(seed=42)
    h.run_all()
    assert h.results["A1"].precision >= 0.80

def test_a1_cost_gate():
    h = BenchmarkHarness(seed=42)
    h.run_all()
    assert h.results["A1"].cost_tokens <= h.results["C1"].cost_tokens * 10

def test_comparison_table():
    h = BenchmarkHarness(seed=42)
    table = h.get_comparison_table()
    assert "C0" in table
    assert "C1" in table
    assert "A1" in table
    assert "precision" in table
