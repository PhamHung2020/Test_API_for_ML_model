import requests

login_response = requests.post(
    "http://127.0.0.1:3000/auth/login",
    {
            "email": "phammanhhung1@gmail.com",
            "password": "PhamHung"
    }
)

if login_response.status_code == 202:
    login_response_json = login_response.json()
    print(login_response_json['token'])
