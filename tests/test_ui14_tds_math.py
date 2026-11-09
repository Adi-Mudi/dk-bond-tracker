from src.phase4 import tds_breakdown


def test_ui14_toggle_on_derives_gross_7033_and_tds_703_from_net_6330():
    assert tds_breakdown(6330, True) == {"net": 6330, "tds": 703, "gross": 7033}


def test_ui14_gross_is_net_divided_by_point_nine():
    assert tds_breakdown(6330)["gross"] == round(6330 / 0.9) == 7033


def test_ui14_tds_is_net_divided_by_nine_not_ten_percent_of_net():
    assert tds_breakdown(6330)["tds"] == round(6330 / 9) == 703
    assert tds_breakdown(6330)["tds"] != round(6330 * 0.10)


def test_ui14_toggle_off_returns_gross_equal_to_net_and_zero_tds():
    assert tds_breakdown(6330, False) == {"net": 6330, "tds": 0, "gross": 6330}


def test_ui14_rounds_to_nearest_whole_rupee_rounding_down_case():
    assert tds_breakdown(6330) == {"net": 6330, "tds": 703, "gross": 7033}


def test_ui14_rounds_to_nearest_whole_rupee_rounding_up_case():
    assert tds_breakdown(6350) == {"net": 6350, "tds": 706, "gross": 7056}


def test_ui14_gross_always_equals_net_plus_tds():
    for net in (100, 999, 4500, 6330, 6350, 12345, 100000):
        result = tds_breakdown(net)
        assert result["gross"] == result["net"] + result["tds"]


def test_ui14_accepts_string_net_from_form_input():
    assert tds_breakdown("6330") == {"net": 6330, "tds": 703, "gross": 7033}
