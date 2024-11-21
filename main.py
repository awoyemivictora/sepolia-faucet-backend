from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from dotenv import load_dotenv
import os
import time
import redis
import requests

# Load environment variables from .env file
load_dotenv()

# Get values from .env
INFURA_URL = os.getenv("INFURA_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

print(os.getenv("INFURA_URL"))
print(os.getenv("PRIVATE_KEY"))


# Log the loaded values (for debugging only)
print(f"Using Infura URL: {INFURA_URL}")
print(f"Using Private Key: {PRIVATE_KEY[:6]}... (truncated for security)")

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Test connection
if not w3.is_connected():
    raise Exception("Unable to connect to Sepolia network")
else:
    print("Connected to Sepolia network")



# Wallet setup
faucet_account = w3.eth.account.from_key(PRIVATE_KEY)

# FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins, change as necessary for production
    allow_credentials=True,
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# Initialize Redis client to store the wallet request time even after the app restarts
r = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Google reCAPTCHA secret key
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

# In-memory store for tracking the last request time for each wallet addrerss
last_request_time = {}


class FaucetRequest(BaseModel):
    address: str
    captcha_response: str # CAPTCHA response sent by frontend


# Function to verify reCAPTCHA response
def verify_recaptcha(captcha_response: str) -> bool:
    payload = {
        'secret': RECAPTCHA_SECRET_KEY,
        'response': captcha_response
    }
    response = requests.post("https://www.google.com/recaptcha/api/siteverify", data=payload)
    result = response.json()
    return result.get('success', False)


@app.post("/faucet")
async def send_eth(request: FaucetRequest):
    # Verify reCAPTCHA response
    if not verify_recaptcha(request.captcha_response):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")
    
    # Validate Ethereum address
    if not w3.is_address(request.address):
        raise HTTPException(status_code=400, detail="Invalid Ethereum address")
    
    current_time = time.time() # Get current time in seconds

    # Check if the wallet address has made a request in the last 24 hours
    last_time = r.get(request.address)
    if last_time:
        time_since_last_request = current_time - float(last_time)
        if time_since_last_request < 24 * 60 * 60: # 24 hours in seconds
            raise HTTPException(status_code=429, detail="You can only request once every 24 hours.")
        
    # Amount to send (e.g., 0.01 ETH)
    amount = w3.to_wei(0.01, "ether")

    # Create a transaction
    tx = {
        "to": request.address,
        "value": amount,
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(faucet_account.address),
        "chainId": 11155111, # Sepolia chain ID
    }

    # Sign and send the transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    # Update the last request time in Redis for this wallet address
    r.set(request.address, current_time)


    return {"success": True, "transaction_hash": tx_hash.hex()}

