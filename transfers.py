import os
import json
import requests
import psycopg2
from psycopg2.extras import execute_values

from fastapi import APIRouter
from fastapi.responses import Response

transf = APIRouter()


from dotenv import load_dotenv
load_dotenv()
RPC = os.environ.get("RPC")
wallet = os.environ.get("w")

def tr():
    payload = {
        "jsonrpc": "2.0",
        "method": "ankr_getTokenTransfers",
        "params": {
            "address": wallet,
            "blockchain": "polygon"
        },
        "id": 1
    }
    response = requests.post(
    RPC,
    json=payload,
    timeout=60
    )

    response.raise_for_status()
    data = response.json()

    filtered_transfers = [
    {
        "tokenName": transfer.get("tokenName"),
        "fromAddress": transfer.get("fromAddress"),
        "toAddress": transfer.get("toAddress"),
        "value": transfer.get("value"),
        "logIndex": transfer.get("logIndex"),
        "transactionHash": transfer.get("transactionHash")
    }
    for transfer in data["result"]["transfers"]
    ]
    return filtered_transfers

filtered_transfers = tr()



from typing import Annotated
from fastapi import Depends
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor


baza_connect_pool = psycopg2.pool.SimpleConnectionPool(minconn=1,maxconn=10,
    dsn=os.environ.get("baza"),
    cursor_factory=RealDictCursor)

def cycle():
    c = baza_connect_pool.getconn()
    try:
        yield c
    except Exception:
        c.rollback()
        raise
    finally:
        baza_connect_pool.putconn(c)

from psycopg2.extensions import connection
ConnectionDependency = Annotated[ connection, Depends(cycle) ]

@transf.on_event("startup")
def create_table():
    # connect = cycle()
    connect = baza_connect_pool.getconn()
    with connect:
        with connect.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_transfers (
                    id SERIAL PRIMARY KEY,
                    token_name TEXT NOT NULL,
                    value NUMERIC(30, 18) NOT NULL DEFAULT 0,
                    _from TEXT NOT NULL,
                    to_ TEXT NOT NULL,
                    log_index INTEGER NOT NULL,
                    transaction_hash VARCHAR(66) NOT NULL,

                    CONSTRAINT unique_blockchain_transfer
                    UNIQUE (transaction_hash, log_index)
                );
            """)

from fastapi.encoders import jsonable_encoder

@transf.get('/transfers')
def getf(connect: ConnectionDependency):
    rows = [
    (
        transfer["tokenName"],
        transfer["value"],
        transfer["fromAddress"],
        transfer["toAddress"],
        transfer["logIndex"],
        transfer["transactionHash"]
    )
    for transfer in filtered_transfers
]
    try:
        with connect:
                with connect.cursor() as cursor:

                    execute_values(
                        cursor,
                        """
                        INSERT INTO token_transfers
                            (token_name, value, _from, to_, log_index, transaction_hash)
                        VALUES %s
                        ON CONFLICT (transaction_hash, log_index)
                        DO NOTHING
                        """,
                        rows
                    )

                    cursor.execute("""
                        SELECT token_name, value, _from, to_, log_index, transaction_hash
                        FROM token_transfers
                        ORDER BY log_index;
                    """)
     
                    rs = cursor.fetchall()

        pretty = jsonable_encoder(rs)
        return Response(
            content=json.dumps(
                pretty,
                indent=4,
                # ensure_ascii=False,
            ),
            media_type="application/json",
        )
    finally:
        connect.close()



