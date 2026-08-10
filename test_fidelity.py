from decimal import Decimal
from datetime import date
import pytest
import duckdb
from .internal import CommonConfig, WFLogger
from .fidelity import (
    FD_FUNDS,
    Fidelity,
    fd_add_subtype,
    fd_coalesce_missing_unit_price,
    fd_map_activity_types,
    fd_map_exchange_activity,
    fd_map_funds,
)


class TestFidelity():
    def test_fd_map_funds(self):
        for fund in FD_FUNDS:
            assert fd_map_funds(fund) == FD_FUNDS[fund]
        assert fd_map_funds("UNDEFINED") == "UNDEFINED"

    @pytest.mark.parametrize(
        "line,expected_action",
        [
            ("FOREIGN TAX PAID", "TAX"),
            ("ADJUST FEE FOR", "FEE"),
            ("YOU BOUGHT SPAXX TWELVE", "BUY"),
            ("REINVESTMENT OF", "BUY"),
            ("EXCHANGED TO FIDXX", "BUY"),
            ("YOU SOLD FIFTEEN", "SELL"),
            ("DIVIDEND RECEIVED (", "DIVIDEND"),
            ("DIRECT DEPOSIT FROM", "DEPOSIT"),
            ("INTEREST EARNED FDIC INSURED DEPOSIT", "DEPOSIT"),
            ("ROLLOVER FROM", "TRANSFER IN"),
            ("TRANSFERRED FROM", "TRANSFER IN"),
            ("Contribution", "TRANSFER IN"),
            ("ELECTRONIC FUNDS TRANSFER RECEIVED", "TRANSFER IN"),
            ("REVENUE CREDIT", "TRANSFER IN"),
            ("ROLLOVER CASH DIRECT ROLLOVER FROM", "TRANSFER IN"),
            ("WITHDRAWALS", "WITHDRAWAL"),
            ("DIRECT DEBIT", "WITHDRAWAL"),
            ("DEBIT CARD PURCHASE", "WITHDRAWAL"),
            ("Electronic Funds Transfer Paid", "WITHDRAWAL"),
            ("CASH ADVANCE", "WITHDRAWAL"),
            ("TRANSFERRED TO", "TRANSFER OUT"),
            ("TRANSFER OF ASSETS ACAT", "TRANSFER OUT"),
        ]
    )
    def test_fd_map_activity_types(self, line: str, expected_action: str):
        assert fd_map_activity_types(line) == expected_action

    @pytest.mark.parametrize(
        "line,expected_action",
        [
            ("FOREIGN TAX PAID", ""),
            ("ADJUST FEE FOR", ""),
            ("YOU BOUGHT SPAXX TWELVE", ""),
            ("REINVESTMENT OF", "DRIP"),
            ("EXCHANGED TO FIDXX", ""),
            ("YOU SOLD FIFTEEN", ""),
            ("DIVIDEND RECEIVED (", ""),
            ("DIRECT DEPOSIT FROM", ""),
            ("INTEREST EARNED FDIC INSURED DEPOSIT", ""),
            ("ROLLOVER FROM", ""),
            ("TRANSFERRED FROM", ""),
            ("Contribution", ""),
            ("ELECTRONIC FUNDS TRANSFER RECEIVED", ""),
            ("REVENUE CREDIT", ""),
            ("ROLLOVER CASH DIRECT ROLLOVER FROM", ""),
            ("WITHDRAWALS", ""),
            ("DIRECT DEBIT", ""),
            ("DEBIT CARD PURCHASE", ""),
            ("Electronic Funds Transfer Paid", ""),
            ("CASH ADVANCE", ""),
            ("TRANSFERRED TO", ""),
            ("TRANSFER OF ASSETS ACAT", ""),
        ]
    )
    def test_fd_add_subtype(self, line: str, expected_action: str):
        assert fd_add_subtype(line) == expected_action

    @pytest.mark.parametrize(
        "amount,symbol,action,expected_action",
        [
            (Decimal(-1), "BROKERAGELINK", "Exchanges", "WITHDRAWAL"),
            (Decimal(1), "BROKERAGELINK", "Exchanges", "DEPOSIT"),
            (Decimal(-1), "SPAXX", "Exchanges", "BUY"),
            (Decimal(1), "SPAXX", "Exchanges", "SELL"),
            (Decimal(-1), "", "Realized", "WITHDRAWAL"),
            (Decimal(1), "", "Realized", "DEPOSIT"),
            (Decimal(-1), "VIVIX", "YOU BOUGHT VIVIX", "BUY"),
        ]
    )
    def test_fd_map_exchange_activity(self, amount: Decimal, symbol, action, expected_action: str):
        assert fd_map_exchange_activity(
            amount, symbol, action) == expected_action

    @pytest.mark.parametrize(
        "quantity,unit_price,amount,expected_unit_price",
        [
            (Decimal(0), Decimal(0), Decimal(17), Decimal(17)),
            (None, Decimal(0), Decimal(0), Decimal(1)),
            (Decimal(4), Decimal(0), Decimal(100), Decimal(25)),
            (Decimal(0), Decimal(0), None, None),
            (Decimal(12), Decimal(6), Decimal(15), Decimal(6)),
        ]
    )
    def test_fd_coalesce_missing_unit_price(self, quantity, unit_price, amount, expected_unit_price: Decimal):
        assert fd_coalesce_missing_unit_price(
            quantity, unit_price, amount) == expected_unit_price

    def test_reshape(self, tmp_path):
        tmp_file = tmp_path / "test.csv"
        tmp_file.write_text("""
Run Date,Account,Account Number,Action,Symbol,Description,Type,Exchange Quantity,Exchange Currency,Currency,Price,Quantity,Exchange Rate,Commission,Fees,Accrued Interest,Amount,Settlement Date
01/31/1991,Joint Brokerage (Taxable),12345678,DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash),SPAXX,FIDELITY GOVERNMENT MONEY MARKET,Cash,0,"",USD,"",0,0,"","","",2.25,""
01/31/1991,Joint Cash Management,12345678,REINVESTMENT FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash),SPAXX,FIDELITY GOVERNMENT MONEY MARKET,Cash,0,"",USD,1,0.07,0,"","","","-0.07",""
01/31/1991,Joint Cash Management,12345678,DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash),SPAXX,FIDELITY GOVERNMENT MONEY MARKET,Cash,0,"",USD,"",0,0,"","","",0.07,""

"The data and information in this spreadsheet is provided to you solely for your use and is not for distribution. The spreadsheet is provided for"
"informational purposes only, and is not intended to provide advice, nor should it be construed as an offer to sell, a solicitation of an offer to buy or a"
"recommendation for any security or insurance product by Fidelity or any third party. Data and information shown is based on information known to Fidelity as of the date it was"
"exported and is subject to change. It should not be used in place of your account statements or trade confirmations and is not intended for tax reporting"
"purposes. For more information on the data included in this spreadsheet, including any limitations thereof, go to Fidelity.com."

"Brokerage services are provided by Fidelity Brokerage Services LLC (FBS), 900 Salem Street, Smithfield, RI 02917. Custody and other services provided by National"
"Financial Services LLC (NFS). Both are Fidelity Investment companies and members SIPC, NYSE. Insurance products at Fidelity are distributed by"
"Fidelity Insurance Agency, Inc., and, for certain products, by Fidelity Brokerage Services, Member NYSE, SIPC." """)
        log = WFLogger("test", "DEBUG")
        log.init()
        conn = duckdb.connect(":memory:")
        fd_instance = Fidelity(common=CommonConfig(
            filename=str(tmp_file.resolve()),
            conn=conn,
            log=log,
        ))
        fd_instance.pre_process()
        fd_instance.import_csv()
        reshaped = fd_instance.reshape()
        print(reshaped.columns)
        assert len(reshaped.fetchall()) == 3
        assert reshaped.select("amount").fetchall() == [(
            Decimal('2.250'),), (Decimal('-0.070'),), (Decimal('0.070'),)]
        assert reshaped.select("account").fetchall() == [('12345678 Joint Brokerage (Taxable)',), (
            '12345678 Joint Cash Management',), ('12345678 Joint Cash Management',)]
        assert reshaped.select("date").fetchall() == [(
            date(1991, 1, 31),), (date(1991, 1, 31),), (date(1991, 1, 31),)]
        assert reshaped.select("symbol").fetchall() == [(
            'SPAXX',), ('SPAXX',), ('SPAXX',)]
        assert reshaped.select("instrumentType").fetchall() == [(
            'EQUITY',), ('EQUITY',), ('EQUITY',)]
        assert reshaped.select("quantity").fetchall() == [(
            Decimal(1),), (Decimal(7)/100,), (Decimal(1),)]
        assert reshaped.select("activityType").fetchall() == [(
           'DIVIDEND',), ('BUY',), ('DIVIDEND',)]
        assert reshaped.select("unitPrice").fetchall() == [(
            Decimal(2.250),), (Decimal(1),), (Decimal(7)/100,)]
        assert reshaped.select("currency").fetchall() == [(
           'USD',), ('USD',), ('USD',)]
        assert reshaped.select("fee").fetchall() == [(
           None,), (None,), (None,)]
        assert reshaped.select("amount").fetchall() == [(
            Decimal(2.250),), (-1*Decimal(7)/100,), (Decimal(7)/100,)]
        assert reshaped.select("comment").fetchall() == [(
           'FIDELITY GOVERNMENT MONEY MARKET',), ('FIDELITY GOVERNMENT MONEY MARKET',), ('FIDELITY GOVERNMENT MONEY MARKET',)]
        assert reshaped.select("subtype").fetchall() == [(
           '',), ('DRIP',), ('',)]
