import requests
import json

# Configuration
# IMPORTANT: Update this URL to the one provided by your 'asia-northeast1' deployment!
BASE_URL = "https://dimentai-engine-861471329897.asia-northeast1.run.app"
SECRET_TOKEN = "DimentAI_Secure_2026"   # The token from Task 1.2

def send_to_fortress(transcription_text):
    process_url = f"{BASE_URL}/process"
    headers = {
        "Content-Type": "application/json",
        "X-DimentAI-Token": SECRET_TOKEN
    }
    
    payload = {
        "user_id": "akshay_yelne",
        "source": "local_slm_edge",
        "data": transcription_text
    }

    print(f"🚀 Initializing POST request to DimentAI Clinical Engine: {process_url}")
    try:
        response = requests.post(process_url, headers=headers, json=payload)
        if response.status_code == 200:
            res_data = response.json()
            doc_id = res_data.get("doc_id")
            print(f"✅ Handover Successful! Doc ID: {doc_id}")
            
            # Step 2: Test Summarization
            print(f"Requesting summary for {doc_id}...")
            summary_url = f"{BASE_URL}/summarize/{doc_id}"
            summary_res = requests.get(summary_url, headers=headers)
            
            if summary_res.status_code == 200:
                print("📊 Summary Analysis Result:")
                print(json.dumps(summary_res.json(), indent=2))
            else:
                print(f"❌ Summary Failed. Status: {summary_res.status_code}")
        else:
            print(f"❌ Handover Failed. Status: {response.status_code}")
            print("Error:", response.text)
    except Exception as e:
        print(f"⚠️ Connection Error: {str(e)}")

if __name__ == "__main__":
    # Test with your Soulora mission statement text
    sample_text = (
        "Your wellness data is fragmented. Solora maps your daily insights. "
        "Solora helps you understand your wellness better by connecting fragmented data."
    )
    send_to_fortress(sample_text)