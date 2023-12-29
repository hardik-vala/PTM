import browser_cookie3
import requests

cj = browser_cookie3.chrome(domain_name="workflowy.com")

r = requests.get(
    "https://workflowy.com/get_tree_data",
    cookies=cj,
    headers={"Accept": "application/json"},
)

print(r.json())
