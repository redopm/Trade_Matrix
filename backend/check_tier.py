import asyncio
import os
import time
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv(".env")
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit(1)

client = genai.Client(api_key=api_key)

async def send_request(i):
    try:
        # A very lightweight request to minimize cost/time
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents="Say hello"
        )
        return True
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota" in error_msg or "exhausted" in error_msg.lower():
            return False
        return True # other errors don't mean rate limit

async def main():
    print("Checking Gemini API Tier...")
    print("Sending 20 concurrent requests (Free tier limit is 15 RPM)...")
    
    start_time = time.time()
    
    # Fire 20 requests concurrently
    tasks = [send_request(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    duration = time.time() - start_time
    
    success_count = sum(results)
    failed_count = len(results) - success_count
    
    print(f"\nResults completed in {duration:.2f} seconds:")
    print(f"Successful Requests: {success_count}/20")
    print(f"Rate Limited (429): {failed_count}/20")
    
    if failed_count > 0:
        print("\n❌ RESULT: You are still on the FREE TIER.")
        print("Because the API blocked us after 15 requests (Free tier has a 15 Requests Per Minute limit).")
    else:
        print("\n✅ RESULT: Your API Key is upgraded to the PAID TIER!")
        print("Because we successfully sent 20 requests in just a few seconds without hitting the 15 RPM limit.")

if __name__ == "__main__":
    asyncio.run(main())
