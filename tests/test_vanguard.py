from decimal import Decimal
from pathlib import Path
from datetime import date
import pytest
import duckdb
from wealthfolio_converter.vanguard import vg_coalesce_missing_unit_price, vg_map_activity_types, Vanguard
from wealthfolio_converter.internal import WFLogger, CommonConfig


class TestVanguard:
    @pytest.mark.parametrize("_,quantity,unit_price,amount,expected", [
        ("quantity_and_price_zero", Decimal(0),
         Decimal(0), Decimal(17), Decimal(17)),
        ("quantity_and_price_none", None, None, Decimal(17), Decimal(17)),
        ("quantity_zero", Decimal(0), Decimal(12), Decimal(34), Decimal(12)),
        ("quantity_none", None, Decimal(12), Decimal(34), Decimal(12)),
        ("amount_zero", Decimal(12), Decimal(4), Decimal(0), Decimal(4)),
        ("amount_none", Decimal(12), Decimal(4), None, Decimal(4)),
        ("unit_price_zero", Decimal(12), Decimal(0), Decimal(3), Decimal(25)/100),
        ("unit_price_none", Decimal(12), None, Decimal(3), Decimal(25)/100),
    ])
    def test_vg_coalesce_missing_unit_price(self, _, quantity, unit_price, amount, expected):
        assert vg_coalesce_missing_unit_price(
            quantity, unit_price, amount) == expected

    @pytest.mark.parametrize("_,action,quantity,return_action", [
        ("buy_buy", "Buy some things", Decimal(1), "BUY"),
        ("buy_reinvestment", "Reinvestment in something", Decimal(1), "BUY"),
        ("buy_cap_gain", "Capital gain realized in", Decimal(1), "BUY"),
        ("sell", "Sell shares in", Decimal(1), "SELL"),
        ("exchange_buy", "Exchange X shares of", Decimal(1), "BUY"),
        ("exchange_sell", "Exchange X shares of", Decimal(-1), "SELL"),
        ("exchange_zero_case", "Exchange X shares of", Decimal(0), "SELL"),
        ("xfer_in_conversion", "Conversion (incoming) of", Decimal(1), "TRANSFER IN"),
        ("xfer_in_funds_received", "Funds Received to", Decimal(1), "TRANSFER IN"),
        ("xfer_in_xfer_incoming", "Transfer (incoming)", Decimal(1), "TRANSFER IN"),
        ("xfer_in_rollover_incoming", "Rollover (incoming)", Decimal(1), "TRANSFER IN"),
        ("xfer_out_xfer_to", "Transfer To XXX account", Decimal(1), "TRANSFER OUT"),
        ("xfer_out_rollover_to", "Rollover To XXX account", Decimal(1), "TRANSFER OUT"),
        ("xfer_out_xfer_outgoing", "Transfer (Outgoing)", Decimal(1), "TRANSFER OUT"),
        ("xfer_out_conversion_outgoing",
         "Conversion (Outgoing)", Decimal(1), "TRANSFER OUT"),
        ("tax", "Withholding of foreign", Decimal(1), "TAX"),
        ("deposit", "Contribution", Decimal(1), "DEPOSIT"),
        ("withdrawal", "Distribution", Decimal(1), "WITHDRAWAL"),
        ("split", "Stock split", Decimal(1), "SPLIT"),
        ("silliness", "Supercalifragilistic", Decimal(1), "Supercalifragilistic"),
    ])
    def test_vg_map_activity_types(self, _, action: str, quantity: Decimal, return_action: str):
        assert vg_map_activity_types(action, quantity) == return_action

    def test_xlsx_to_csv_and_reshape(self):
        tmp_file = Path("tests") / "example_account.xlsx"
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")

        tr_instance = Vanguard(common=CommonConfig(
            filename=str(tmp_file.absolute()),
            conn=conn,
            log=log,
        ))

        tr_instance.xlsx_to_csv()
        tr_instance.pre_process()
        tr_instance.import_csv()

        reshaped = tr_instance.reshape()
        reshaped.select('comment').show()
        assert len(reshaped) == 4
        assert reshaped.select('date').fetchall() == [
            (date(1998, 10, 4),),
            (date(1998, 10, 5),),
            (date(1998, 10, 6),),
            (date(1998, 10, 7),),
        ]
        assert reshaped.select('symbol').fetchall() == [
            ('VMMXX',),
            ('VFIFX',),
            (None,),
            (None,),
        ]
        assert reshaped.select('instrumentType').fetchall() == [
            ('EQUITY',),
            ('EQUITY',),
            ('EQUITY',),
            ('EQUITY',),
        ]
        assert reshaped.select('quantity').fetchall() == [
            (Decimal(-6000),),
            (Decimal(3391) / 1000,),
            (Decimal(1),),
            (Decimal(1),),
        ]
        assert reshaped.select('activityType').fetchall() == [
            ('SELL',),
            ('BUY',),
            ('DEPOSIT',),
            ('DEPOSIT',),
        ]
        assert reshaped.select('unitPrice').fetchall() == [
            (Decimal(1),),
            (Decimal(3391) / 100,),
            (Decimal(150) / 1000,),
            (Decimal(110) / 1000,),
        ]
        assert reshaped.select('currency').fetchall() == [
            ('USD',),
            ('USD',),
            ('USD',),
            ('USD',),
        ]
        assert reshaped.select('fee').fetchall() == [
            (None,),
            (None,),
            (None,),
            (None,),
        ]
        assert reshaped.select('amount').fetchall() == [
            (Decimal(6000),),
            (Decimal(-115),),
            (Decimal(150) / 1000,),
            (Decimal(110) / 1000,),
        ]
        assert reshaped.select('comment').fetchall() == [
            ('Vanguard Cash Reserves Federal Money Market Fund',),
            ('Vanguard Target Retirement 2050 Fund',),
            ('CASH',),
            ('CASH',),
        ]
