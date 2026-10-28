from decimal import Decimal
from datetime import date
import pytest
import duckdb
from wealthfolio_converter.trowe import tr_map_activity_types, tr_map_funds, TR_FUNDS, TRowe
from wealthfolio_converter.internal import WFLogger, CommonConfig


class TestTRowe:
    @pytest.mark.parametrize('line,expected_action', [
        ('Contribution', 'TRANSFER IN'),
        ('Misc. Receipt', 'TRANSFER IN'),
        ('Exchange In', 'BUY'),
        ('In Plan Roth Rollover In', 'BUY'),
        ('Exchange Out', 'SELL'),
        ('In Plan Roth Rollover Out', 'SELL'),
        ('Withdrawal', 'TRANSFER OUT'),
        ('Other', 'OTHER'),
    ])
    def test_tr_map_activity_types(self, line, expected_action: str):
        assert tr_map_activity_types(line) == expected_action

    def test_tr_map_funds(self):
        for fund in TR_FUNDS:
            assert tr_map_funds(fund) == TR_FUNDS[fund]
        assert tr_map_funds('FOO') == 'FOO'

    def test_reshape(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""FROM,01/01/1991,To,01/31/1991,

Date,Activity Type,Investment,Source,Amount,Shares,Price,

01/01/1991,Fee,AMERICAN FUNDS EUPAC R6,ROTH,$4.00,0.0720,$55.55,
01/20/1991,Contribution,AMERICAN FUNDS EUPAC R6,ROTH,$475.00,8.6129,$55.15,
""")
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        tr_instance = TRowe(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ))
        log.info(tr_instance)
        tr_instance.pre_process()
        tr_instance.import_csv()
        reshaped = tr_instance.reshape()
        assert len(reshaped.fetchall()) == 2
        assert reshaped.select("amount").fetchall() == [(
            Decimal('4'),), (Decimal('475'),)]
        assert reshaped.select("date").fetchall() == [(
            date(1991, 1, 1),), (date(1991, 1, 20),)]
        assert reshaped.select("symbol").fetchall() == [(
            'RERGX',), ('RERGX',)]
        assert reshaped.select("instrumentType").fetchall() == [(
            'EQUITY',), ('EQUITY',)]
        assert reshaped.select("quantity").fetchall() == [(
            Decimal(72)/1000,), (Decimal(8613)/1000,)]
        assert reshaped.select("activityType").fetchall() == [(
            'FEE',), ('TRANSFER IN',),]
        assert reshaped.select("currency").fetchall() == [(
            'USD',), ('USD',)]
        assert reshaped.select("amount").fetchall() == [(
            Decimal(4),), (Decimal(475),)]
        assert reshaped.select("comment").fetchall() == [(
            'ROTH',), ('ROTH',)]
