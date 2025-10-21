import httpx

response = httpx.post(
    "https://api.avito.ru/token",
    data={
        "grant_type": "client_credentials",
        "client_id": "hT3IQ-wMwDNy4351yLAJ",
        "client_secret": "KgxtrTAvrmeMPAYUp2zpXwsdY-Kf0tmdq7Wgd8eu"
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)

print(response.json())