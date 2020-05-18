import requests
res = requests.post('http://localhost:5000/nlp', json={"text":"i actually dont like this product"})
if res.ok:
    print(res.json())