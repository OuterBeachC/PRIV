import requests
from requests.auth import HTTPBasicAuth

user_id = "92a81cf13c494a06a92fd"
password = "Twist8191!!!"

response = requests.get(
    "https://api.finra.org/data/group/dataset",
    auth=HTTPBasicAuth(user_id, password),
    headers={"Accept": "application/json"}
)

print(response.json())