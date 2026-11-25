# ==== A. Header ===================================================================
# Testbench:     test_counter4d (cocotb)
# Project:       counter4d
# SAD:           spec/counter4d/sad.md section 3.1
# Risk:          LOW: line, branch, toggle, FSM and functional 100 % (riskmap.yaml)
# Testplan:      verif/counter4d/testplan.yaml @v1.0
# Author:        Dayo
# PURPOSE:       One directed test per VPS scenario and one seeded random test; a monitor
#                feeds every rising edge to a scoreboard built on a model of REQ-3.1.1 to
#                REQ-3.1.6, and the scoreboard samples the covergroups.
# DEBUG NOTES:   Read the first MISMATCH line. Add to the waveform, in order: rst_n, en, count.
# KNOWN GOTCHAS: Clock starts low; inputs change only after a falling edge (R1 of IDD-COUNT_IF),
#                never in a rising-edge timestep. Reset is synchronous: it needs a rising edge.
#                The same harness later runs unchanged on the gate-level netlist.
"""cocotb harness for counter4d."""

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge
from cocotb_coverage.coverage import CoverPoint, coverage_db

# ==== B. Interface layer ==========================================================
CLK_PERIOD_NS = 10  # clocks.yaml: clk at 100 MHz
RESET_EDGES = 2  # clocks.yaml rst_n is synchronous (REQ-3.1.1): held 0 for 2 rising edges
COUNT_MAX = 15  # REQ-3.1.3: the value that wraps to 0
RANDOM_EDGES = 600  # REQ-3.1.2 REQ-3.1.4 (VPS-03): random run length, many wraps
PERCENT = 100  # REQ-3.1.5 (VPS-05): constraint_model odds are percentages
EN_ONE_PCT = 67  # testplan constraint_model: en 1 about 2 edges in 3
RST_ZERO_PCT = 8  # testplan constraint_model: rst_n 0 about 1 edge in 12
LOG = logging.getLogger("test_counter4d")


@dataclass(frozen=True)
class CountSample:
    """One rising edge: the inputs it acted on and count after it."""

    rst_n: int
    en: int
    count: int


def count_read(handle, name: str) -> int:
    """A port's value as an int; X or Z is a failure (MQ-TBS-004)."""
    value = handle.value
    if not value.is_resolvable:
        raise AssertionError(f"UNKNOWN signal={name} observed={value}: an X or Z at a port")
    return int(value)


class CountDriver:
    """Drives en and rst_n only after a falling edge (R1). It only drives."""

    def __init__(self, dut) -> None:
        self.clk = dut.clk
        self.dut = dut
        self.en = dut.en
        self.rst_n = dut.rst_n

    def power_up(self) -> None:
        self.en.value = 0
        self.rst_n.value = 0  # in reset from power-up
        for name in ("test_mode", "scan_mode", "scan_en", "scan_in"):
            if hasattr(self.dut, name):
                getattr(self.dut, name).value = 0

    async def drive(self, rst_n: int, en: int) -> None:
        await FallingEdge(self.clk)
        self.rst_n.value = rst_n
        self.en.value = en


class CountMonitor:
    """Observes every rising edge: inputs before it, count after ReadOnly. Only observes."""

    def __init__(self, dut, on_sample: Callable[[CountSample], None]) -> None:
        self.dut = dut
        self.on_sample = on_sample

    async def run(self) -> None:
        dut = self.dut
        while True:
            await RisingEdge(dut.clk)
            rst_n = count_read(dut.rst_n, "rst_n")
            en = count_read(dut.en, "en")
            await ReadOnly()
            self.on_sample(CountSample(rst_n, en, count_read(dut.count, "count")))


class CountReset:
    """The reset sequence (DAYO-TBS-021): rst_n active low, synchronous (clocks.yaml)."""

    def __init__(self, dut) -> None:
        self.clk = dut.clk
        self.rst_n = dut.rst_n

    async def release(self) -> None:
        for _ in range(RESET_EDGES):
            await RisingEdge(self.clk)
        await FallingEdge(self.clk)
        self.rst_n.value = 1


# ==== C. Stimulus =================================================================
class CountEnv:
    """One test's harness: components, model, coverage, one seed."""

    def __init__(self, dut, test: str, vps: str, req: str) -> None:
        self.seed = cocotb.RANDOM_SEED
        self.rng = random.Random(self.seed)
        LOG.info("SEED=%d test=%s harness=test_counter4d dut=counter4d", self.seed, test)
        self.dut = dut
        self.test = test
        self.driver = CountDriver(dut)
        self.reset = CountReset(dut)
        self.scoreboard = CountScoreboard(test, self.seed, vps, req)
        self.monitor = CountMonitor(dut, self.scoreboard.observe)

    async def start(self) -> None:
        self.driver.power_up()  # every input driven before the clock starts
        Clock(self.dut.clk, CLK_PERIOD_NS, unit="ns").start(start_high=False)
        cocotb.start_soon(self.monitor.run())
        await self.reset.release()

    async def step(self, rst_n: int, en: int) -> None:
        """One input pair at a falling edge; count must not move before the rising edge."""
        await FallingEdge(self.dut.clk)
        got = count_read(self.dut.count, "count")
        exp = self.scoreboard.model.count_exp
        if got != exp:
            raise AssertionError(
                f"MISMATCH {self.scoreboard.vps} REQ-3.1.6 signal=count_off_edge "
                f"expected={exp} observed={got} test={self.test} seed={self.seed}"
            )
        self.dut.rst_n.value = rst_n
        self.dut.en.value = en

    async def steps(self, n: int, rst_n: int, en: int) -> None:
        for _ in range(n):
            await self.step(rst_n, en)

    async def finish(self) -> None:
        await RisingEdge(self.dut.clk)
        await FallingEdge(self.dut.clk)
        assert self.scoreboard.edges > 0, "no edge was checked"
        count_cov_export()


@cocotb.test(timeout_time=20, timeout_unit="us")
async def test_vps_01_reset(dut) -> None:
    """VPS-01: reset from zero at power-up, and from a nonzero count."""
    env = CountEnv(dut, "test_vps_01_reset", "VPS-01", "REQ-3.1.1")
    await env.start()
    await env.steps(2, 0, 0)  # reset from zero
    await env.steps(6, 1, 1)  # count up to a nonzero value
    await env.steps(3, 0, 1)  # reset: 0 after the edge and while low
    await env.steps(2, 1, 1)
    await env.steps(2, 0, 0)
    await env.finish()


@cocotb.test(timeout_time=20, timeout_unit="us")
async def test_vps_02_hold(dut) -> None:
    """VPS-02: en 0 for several cycles at a nonzero count."""
    env = CountEnv(dut, "test_vps_02_hold", "VPS-02", "REQ-3.1.4")
    await env.start()
    await env.steps(5, 1, 1)
    await env.steps(6, 1, 0)
    await env.steps(2, 1, 1)
    await env.steps(3, 1, 0)
    await env.finish()


@cocotb.test(timeout_time=20, timeout_unit="us")
async def test_vps_03_increment(dut) -> None:
    """VPS-03: en 1 for several cycles after reset."""
    env = CountEnv(dut, "test_vps_03_increment", "VPS-03", "REQ-3.1.2")
    await env.start()
    await env.steps(8, 1, 1)
    await env.finish()


@cocotb.test(timeout_time=20, timeout_unit="us")
async def test_vps_04_wrap(dut) -> None:
    """VPS-04: en 1 from count 0 through 16 edges."""
    env = CountEnv(dut, "test_vps_04_wrap", "VPS-04", "REQ-3.1.3")
    await env.start()
    await env.steps(18, 1, 1)
    await env.finish()


@cocotb.test(timeout_time=20, timeout_unit="us")
async def test_vps_05_reset_priority(dut) -> None:
    """VPS-05: rst_n 0 with en 1 at a nonzero count."""
    env = CountEnv(dut, "test_vps_05_reset_priority", "VPS-05", "REQ-3.1.5")
    await env.start()
    await env.steps(7, 1, 1)
    await env.steps(4, 0, 1)
    await env.steps(3, 1, 1)
    await env.steps(1, 0, 1)
    await env.finish()


@cocotb.test(timeout_time=100, timeout_unit="us")
async def test_random_seeded(dut) -> None:
    """Constrained-random en and rst_n from the testplan's constraint model, one seed."""
    env = CountEnv(dut, "test_random_seeded", "VPS-03", "REQ-3.1.2")
    await env.start()
    for _ in range(RANDOM_EDGES):
        rst_n = 0 if env.rng.randrange(PERCENT) < RST_ZERO_PCT else 1
        en = 1 if env.rng.randrange(PERCENT) < EN_ONE_PCT else 0
        await env.step(rst_n, en)
    await env.finish()


# ==== D. Reference model and scoreboard ===========================================
class CountModel:
    """REQ-3.1.1 to REQ-3.1.5 at the ports, from the specification alone."""

    def __init__(self) -> None:
        self.count_exp = 0

    def apply(self, rst_n: int, en: int) -> int:
        if not rst_n:
            self.count_exp = 0  # REQ-3.1.1, REQ-3.1.5
        elif en:
            self.count_exp = 0 if self.count_exp == COUNT_MAX else self.count_exp + 1  # 3.1.2/3
        return self.count_exp  # REQ-3.1.4: held when en is 0


@dataclass(frozen=True)
class CountMatch:
    """One checked edge, as the scoreboard hands it to the coverage model."""

    vps: str
    count_before: int
    sample: CountSample


class CountScoreboard:
    """Compares every edge with the model: one MISMATCH line per difference (DAYO-TBS-032)."""

    def __init__(self, test: str, seed: int, vps: str, req: str) -> None:
        self.test = test
        self.seed = seed
        self.vps = vps
        self.req = req
        self.model = CountModel()
        self.count_before = 0
        self.edges = 0
        self.listeners: list[Callable[[CountMatch], None]] = []

    def observe(self, sample: CountSample) -> None:
        before = self.model.count_exp
        expected = self.model.apply(sample.rst_n, sample.en)
        if sample.count != expected:
            raise AssertionError(
                f"MISMATCH {self.vps} {self.req} signal=count expected={expected} "
                f"observed={sample.count} test={self.test} seed={self.seed}"
            )
        self.edges += 1
        match = CountMatch(self.vps, before, sample)
        for vps, group in COUNT_COVERGROUPS.items():
            if COUNT_FILTERS[vps](sample):
                group(match)
        self.count_before = sample.count


# ==== E. Coverage model ===========================================================
def count_class(value: int, with_max: bool) -> str:
    """zero, max (15) or mid (1 to 14) for the classes the VPS distinguishes."""
    if value == 0:
        return "zero"
    return "max" if with_max and value == COUNT_MAX else "mid"


@CoverPoint("cg_vps_01.count_at", xf=lambda m: count_class(m.count_before, False),
            bins=["zero", "mid"])
def cg_vps_01(m: CountMatch) -> None:
    """VPS-01: the count held when the reset came."""


@CoverPoint("cg_vps_02.count_at", xf=lambda m: count_class(m.count_before, False),
            bins=["mid"])
def cg_vps_02(m: CountMatch) -> None:
    """VPS-02: the count held while en is 0."""


@CoverPoint("cg_vps_03.count_at", xf=lambda m: count_class(m.count_before, False),
            bins=["zero", "mid"])
def cg_vps_03(m: CountMatch) -> None:
    """VPS-03: the count an increment starts from."""


@CoverPoint("cg_vps_04.count_at", xf=lambda m: count_class(m.count_before, True),
            bins=["max", "zero"])
def cg_vps_04(m: CountMatch) -> None:
    """VPS-04: the wrap from max, and the count 0 after it."""


@CoverPoint("cg_vps_05.count_at", xf=lambda m: count_class(m.count_before, False),
            bins=["mid"])
def cg_vps_05(m: CountMatch) -> None:
    """VPS-05: the count when rst_n 0 and en 1 arrive together."""


COUNT_COVERGROUPS: dict[str, Callable[[CountMatch], None]] = {
    "VPS-01": cg_vps_01,
    "VPS-02": cg_vps_02,
    "VPS-03": cg_vps_03,
    "VPS-04": cg_vps_04,
    "VPS-05": cg_vps_05,
}

# Which edges each scenario samples (the scenario's intent).
COUNT_FILTERS: dict[str, Callable[[CountSample], bool]] = {
    "VPS-01": lambda s: s.rst_n == 0,
    "VPS-02": lambda s: s.rst_n == 1 and s.en == 0,
    "VPS-03": lambda s: s.rst_n == 1 and s.en == 1,
    "VPS-04": lambda s: s.rst_n == 1 and s.en == 1,
    "VPS-05": lambda s: s.rst_n == 0 and s.en == 1,
}


def count_cov_export() -> None:
    """This process's coverage, for cocotb_sim to collect (DAYO-TBS-044)."""
    coverage_db.export_to_xml(filename="coverage.xml")


# ==== F. Properties ===============================================================
# None: the risk map requires no formal property for counter4d.

# ==== G. Regression manifest ======================================================
# verif/seeds.yaml: locked seeds written by cocotb_sim (DAYO-TBS-034).
