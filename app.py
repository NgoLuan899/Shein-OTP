import requests
import json
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup


app = FastAPI()
class EmailRequest(BaseModel):
    client_id: str
    refresh_token: str

def get_new_token(client_id, refresh_token):
    url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    payload = {
        'client_id': client_id,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
        'scope': 'offline_access https://graph.microsoft.com/Mail.ReadWrite'
    }
    response = requests.post(url, data=payload)
    return response.json()

def clean_text(text):
    text = text.encode('utf-8').decode('unicode_escape')
    text = text.replace("\u200c", "").replace("\u00a0", " ").strip()
    return text

def extract_otp(text):
    otp_match = re.search(r'\b\d{5}\b', text)
    if otp_match:
        return otp_match.group(0)
    return None

def get_messages(token, folder='inbox'):
    url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages"
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    messages = response.json()

    if '@odata.context' in messages:
        del messages['@odata.context']

    filtered_messages = []
    for message in messages.get('value', []):
        from_email = message['from']['emailAddress']['address']
        subject = message['subject']
        
        if from_email == 'noreply@sheinemail.com' and 'Verify' in subject:
            body_content = message['body']['content']
            soup = BeautifulSoup(body_content, 'html.parser')
            plain_text_body = soup.get_text()

            plain_text_body = clean_text(plain_text_body)

            otp = extract_otp(plain_text_body)

            if otp:
                filtered_messages.append({
                    'subject': subject,
                    'from': from_email,
                    'otp': otp
                })

    return filtered_messages

@app.post("/get_otp/")
async def get_otp(request: EmailRequest):
    token_response = get_new_token(request.client_id, request.refresh_token)
    access_token = token_response.get('access_token')

    if access_token:
        inbox_messages = get_messages(access_token, 'inbox')
        if inbox_messages:
            return {"messages": inbox_messages}
        else:
            raise HTTPException(status_code=404, detail="No matching emails found.")
    else:
        raise HTTPException(status_code=400, detail="Error getting access token.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
