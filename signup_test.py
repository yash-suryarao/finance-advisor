import requests, json
url = 'http://127.0.0.1:8000/users/signup/'
payload = {
    'username': 'testuser6',
    'email': 'test6@example.com',
    'password': 'TestPassword123!',
    'phone_no': '5551234567'
}
resp = requests.post(url, json=payload)
print('Status:', resp.status_code)
print('Response:', resp.text)
