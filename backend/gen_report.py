"""Generate and download report for the working investigation."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"

def post(path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

inv_id = "214c9afc-2aeb-4365-8a9c-bb998377fda6"
result = post(f"/investigations/{inv_id}/reports", {"format": "html"})
print(f"Report generated: {result['download_url']}")
print(f"File size: {result['file_size']} bytes")
print(f"\nOpen in browser:")
print(f"http://127.0.0.1:8000{result['download_url']}/download")
