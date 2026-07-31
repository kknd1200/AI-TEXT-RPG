from krflow.models import FlowRow
from krflow.ranking import rank, totals


def row(code, market="kospi", f_val=0.0, i_val=0.0, f_qty=0.0, i_qty=0.0):
    return FlowRow(
        code=code,
        name=f"종목{code}",
        market=market,
        foreign_value=f_val,
        inst_value=i_val,
        foreign_qty=f_qty,
        inst_qty=i_qty,
    )


ROWS = [
    row("000001", f_val=500, i_val=100),  # both 600
    row("000002", f_val=-800, i_val=900),  # both 100
    row("000003", f_val=200, i_val=-50),  # both 150
    row("000004", f_val=-300, i_val=-400),  # both -700
    row("000005", market="kosdaq", f_val=1000, i_val=-100),  # both 900
]


def test_both_value_is_sum():
    assert ROWS[1].both_value == 100
    assert ROWS[1].metric("both", "value") == 100


def test_buy_side_sorted_desc_and_excludes_net_sellers():
    got = rank(ROWS, investor="both", metric="value", side="buy", top=10)
    assert [r.code for r in got] == ["000005", "000001", "000003", "000002"]


def test_sell_side_sorted_most_negative_first():
    got = rank(ROWS, investor="both", metric="value", side="sell", top=10)
    assert [r.code for r in got] == ["000004"]


def test_foreign_only_ranking_differs_from_both():
    got = rank(ROWS, investor="foreign", metric="value", side="buy", top=3)
    assert [r.code for r in got] == ["000005", "000001", "000003"]


def test_inst_sell_ranking():
    got = rank(ROWS, investor="inst", metric="value", side="sell", top=10)
    assert [r.code for r in got] == ["000004", "000005", "000003"]


def test_market_filter():
    got = rank(ROWS, investor="foreign", metric="value", side="buy", top=10, market="kosdaq")
    assert [r.code for r in got] == ["000005"]


def test_top_limit():
    assert len(rank(ROWS, investor="both", metric="value", side="buy", top=2)) == 2


def test_min_abs_filters_small_flows():
    got = rank(ROWS, investor="both", metric="value", side="buy", top=10, min_abs=200)
    assert [r.code for r in got] == ["000005", "000001"]


def test_exclude_codes():
    got = rank(
        ROWS, investor="both", metric="value", side="buy", top=10, exclude_codes={"000005"}
    )
    assert "000005" not in [r.code for r in got]


def test_qty_metric_uses_qty_fields():
    rows = [row("A", f_qty=10, i_qty=5, f_val=-999), row("B", f_qty=1, i_qty=1, f_val=999)]
    got = rank(rows, investor="both", metric="qty", side="buy", top=5)
    assert [r.code for r in got] == ["A", "B"]


def test_totals_sums_displayed_rows():
    got = totals(ROWS[:2])
    assert got["foreign_value"] == -300
    assert got["inst_value"] == 1000
    assert got["both_value"] == 700
