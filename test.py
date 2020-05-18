import requests
res = requests.post('https://nlp-sentiment-app.herokuapp.com/nlp', json={"text":"i actually dont like this product"})
if res.ok:
    print(res.json())