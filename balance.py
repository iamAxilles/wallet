import warnings

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning,
)

from ankr import AnkrWeb3
from ankr.types import GetAccountBalanceRequest
import os
from dotenv import load_dotenv
load_dotenv()

ankr_w3 = AnkrWeb3(os.environ.get("k"))
wallet = os.environ.get("w")

balance_generator = ankr_w3.token.get_account_balance(
    request=GetAccountBalanceRequest(
        walletAddress=wallet,
        blockchain=["polygon"]
    )
)

balances_list = []
for asset in balance_generator:
    balances_list.append(vars(asset))

from fastapi import FastAPI

import transfers

app = FastAPI()
app.include_router(transfers.transf)
import psycopg2
connect = psycopg2.connect(os.environ.get("baza"))

@app.on_event("startup")
def create_table():
    with connect:
        with connect.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id SERIAL PRIMARY KEY,
                    token_name TEXT NOT NULL,
                    balance NUMERIC(30, 18) NOT NULL DEFAULT 0,

                    CONSTRAINT tokens_token_name_unique
                    UNIQUE (token_name)
                );
            """)


@app.get("/balance")
def balance():
    with connect:
        with connect.cursor() as cursor:

            for i in range(len(balances_list)):
                tokenName = balances_list[i]["tokenName"]
                balance = balances_list[i]["balance"]

                cursor.execute("""
                    INSERT INTO tokens (token_name, balance)
                    VALUES (%s, %s)
                    ON CONFLICT (token_name)
                    DO UPDATE SET
                        balance = EXCLUDED.balance;
                """, (
                    tokenName,
                    balance,
                ))

                cursor.execute("""
                    SELECT token_name, balance
                    FROM tokens
                    ORDER BY id;
                """)

                rows = []
                for token_name, balance in cursor.fetchall():
                    rows.append({
                        token_name,
                        balance,
                    })

    return rows

