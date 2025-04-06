import os
import pyupbit  
from dotenv import load_dotenv

load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
upbit = pyupbit.Upbit(access_key, secret_key)

balance = upbit.get_balances()
print(balance)